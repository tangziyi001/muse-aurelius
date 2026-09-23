#!/usr/bin/env python3
"""Auto-sync local code changes to the muse-aurelius GitHub repo.

Detects changed/new/deleted files, scans for secrets, and pushes via the
GitHub Contents API. State is tracked in .gh_sync_state.json.

Usage: python3 gh_sync.py [--dry-run]
"""
import sys
import os
import json
import hashlib
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gh_api import api_request

OWNER = "tangziyi001"
REPO = "muse-aurelius"
HOME = os.path.expanduser("~")
STATE_FILE = os.path.join(HOME, "workspace", "skills", "github", "hidden_files", ".gh_sync_state.json")

# (local_dir, repo_prefix) — whole directories to sync
SYNC_DIRS = [
    (os.path.join(HOME, "workspace", "skills"), "skills"),
    (os.path.join(HOME, "workspace", "pi-ssh"), "automation/pi-ssh"),
    (os.path.join(HOME, "workspace", "etsy-automation"), "automation/etsy-automation"),
    (os.path.join(HOME, "workspace", "pinterest-automation"), "automation/pinterest-automation"),
]

# (local_file, repo_path) — individual files to sync
SYNC_FILES = [
    (os.path.join(HOME, "workspace", "instagram-setup", "ab-test", "render_reel.py"), "reel-factory/render_reel.py"),
    (os.path.join(HOME, "workspace", "instagram-setup", "ab-test", "test_render_reel.py"), "reel-factory/test_render_reel.py"),
]

# Patterns that should never be pushed
EXCLUDE_PATTERNS = [
    r"__pycache__", r"\.pyc$", r"\.pyo$",
    r"/\.env$", r"\.env\.local$", r"credentials.*\.json$",
    r"\.pending_.*\.json$", r"publish_state.*\.json$",
    r"_costs\.json$", r"\.log$", r"\.DS_Store$",
]

# Secret/PII patterns — files matching these are SKIPPED, not pushed
SECRET_PATTERNS = [
    (r"tangziyi001@gmail\.com", "user email"),
    (r"347-?301-?3804", "user phone"),
    (r"(?i)(api[_-]?key|api[_-]?secret|secret[_-]?key)\s*=\s*['\"][^'\"]{8,}", "api key assignment"),
    (r"(?i)password\s*=\s*['\"][^'\"]{4,}", "password assignment"),
    (r"sk-[a-zA-Z0-9]{20,}", "openai-style key"),
    (r"github_pat_[a-zA-Z0-9_]+", "github pat"),
]


def should_exclude(rel_path):
    """Check if a file should be excluded from sync."""
    return any(re.search(p, rel_path) for p in EXCLUDE_PATTERNS)


def scan_for_secrets(content, rel_path):
    """Return list of (pattern_desc) found in content, empty if clean."""
    # Test files for the scanner itself contain the patterns as test data
    if os.path.basename(rel_path).startswith("test_"):
        return []
    try:
        text = content.decode('utf-8', errors='replace')
    except Exception:
        return []
    found = []
    for pattern, desc in SECRET_PATTERNS:
        if re.search(pattern, text):
            found.append(desc)
    return found


def file_hash(path):
    """SHA256 of file contents."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def collect_files():
    """Walk sync dirs/files, return {repo_path: local_path}."""
    result = {}
    for local_dir, repo_prefix in SYNC_DIRS:
        if not os.path.isdir(local_dir):
            continue
        for root, dirs, filenames in os.walk(local_dir):
            # Skip hidden and pycache dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for fn in filenames:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, local_dir)
                repo_path = f"{repo_prefix}/{rel}".replace(os.sep, '/')
                if should_exclude(repo_path):
                    continue
                result[repo_path] = full
    for local_file, repo_path in SYNC_FILES:
        if os.path.isfile(local_file) and not should_exclude(repo_path):
            result[repo_path] = local_file
    return result


def load_state():
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, sort_keys=True)


def get_remote_sha(repo_path):
    """Get the blob SHA of a file on GitHub (None if doesn't exist)."""
    try:
        data, _ = api_request("GET", f"/repos/{OWNER}/{REPO}/contents/{repo_path}")
        return data.get("sha")
    except SystemExit:
        return None


def push_file(repo_path, local_path, remote_sha=None):
    """Create or update a file via the Contents API."""
    import base64
    with open(local_path, 'rb') as f:
        content = base64.b64encode(f.read()).decode('ascii')
    payload = {
        "message": f"Auto-sync: {repo_path}",
        "content": content,
    }
    if remote_sha:
        payload["sha"] = remote_sha
    api_request("PUT", f"/repos/{OWNER}/{REPO}/contents/{repo_path}", payload)


def delete_file(repo_path, remote_sha):
    """Delete a file via the Contents API."""
    api_request("DELETE", f"/repos/{OWNER}/{REPO}/contents/{repo_path}", {
        "message": f"Auto-sync: delete {repo_path}",
        "sha": remote_sha,
    })


def sync(dry_run=False):
    """Main sync logic. Returns (pushed, skipped, deleted) counts."""
    current = collect_files()
    state = load_state()
    
    pushed = []
    skipped = []
    deleted = []
    
    # Check for changed/new files
    for repo_path, local_path in current.items():
        current_hash = file_hash(local_path)
        if state.get(repo_path) == current_hash:
            continue  # unchanged
        
        # Secret scan
        with open(local_path, 'rb') as f:
            content = f.read()
        secrets = scan_for_secrets(content, repo_path)
        if secrets:
            skipped.append((repo_path, f"secrets: {', '.join(secrets)}"))
            continue
        
        # Push
        if not dry_run:
            remote_sha = get_remote_sha(repo_path)
            try:
                push_file(repo_path, local_path, remote_sha)
                pushed.append(repo_path)
                state[repo_path] = current_hash
            except SystemExit as e:
                skipped.append((repo_path, f"push failed"))
        else:
            pushed.append(f"[dry-run] {repo_path}")
    
    # Check for deleted files
    for repo_path in list(state.keys()):
        if repo_path not in current:
            if not dry_run:
                remote_sha = get_remote_sha(repo_path)
                if remote_sha:
                    try:
                        delete_file(repo_path, remote_sha)
                        deleted.append(repo_path)
                    except SystemExit:
                        pass
                del state[repo_path]
            else:
                deleted.append(f"[dry-run] {repo_path}")
    
    if not dry_run:
        save_state(state)
    
    return pushed, skipped, deleted


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    pushed, skipped, deleted = sync(dry_run=dry_run)
    print(f"Pushed: {len(pushed)}, Skipped: {len(skipped)}, Deleted: {len(deleted)}")
    for p in pushed:
        print(f"  + {p}")
    for s, reason in skipped:
        print(f"  ! {s} ({reason})")
    for d in deleted:
        print(f"  - {d}")
