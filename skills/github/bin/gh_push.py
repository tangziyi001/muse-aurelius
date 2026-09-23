#!/usr/bin/env python3
"""Push a local directory to a GitHub repo using the Git Data API.

Usage: python3 gh_push.py <owner> <repo> <local_dir> [--message MSG] [--branch BRANCH]
"""
import sys
import os
import json
import base64

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
sys.path.insert(0, os.path.expanduser("~/workspace/skills/github/bin"))
from gh_api import api_request


def push_directory(owner, repo, local_dir, message="Initial commit", branch="main"):
    # 1. Collect all files
    files = []
    for root, dirs, filenames in os.walk(local_dir):
        # Skip .git
        dirs[:] = [d for d in dirs if d != '.git']
        for fn in filenames:
            full_path = os.path.join(root, fn)
            rel_path = os.path.relpath(full_path, local_dir)
            files.append((rel_path, full_path))
    
    print(f"Found {len(files)} files to push")
    
    # 2. Create blobs for each file
    blobs = []
    for i, (rel_path, full_path) in enumerate(files):
        with open(full_path, 'rb') as f:
            content = f.read()
        # Use base64 for binary safety
        data, _ = api_request("POST", f"/repos/{owner}/{repo}/git/blobs", {
            "content": base64.b64encode(content).decode('ascii'),
            "encoding": "base64",
        })
        blobs.append({"path": rel_path, "sha": data["sha"], "mode": "100644", "type": "blob"})
        if (i + 1) % 20 == 0:
            print(f"  Created {i+1}/{len(files)} blobs...")
    
    print(f"Created {len(blobs)} blobs")
    
    # 3. Create tree
    tree_data, _ = api_request("POST", f"/repos/{owner}/{repo}/git/trees", {
        "tree": blobs,
    })
    tree_sha = tree_data["sha"]
    print(f"Created tree: {tree_sha[:8]}")
    
    # 4. Create commit (no parent for initial commit)
    commit_data, _ = api_request("POST", f"/repos/{owner}/{repo}/git/commits", {
        "message": message,
        "tree": tree_sha,
    })
    commit_sha = commit_data["sha"]
    print(f"Created commit: {commit_sha[:8]}")
    
    # 5. Create or update the branch ref
    try:
        # Try to get existing ref
        api_request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
        # Update existing
        api_request("PATCH", f"/repos/{owner}/{repo}/git/refs/heads/{branch}", {
            "sha": commit_sha,
            "force": False,
        })
        print(f"Updated branch: {branch}")
    except SystemExit:
        # Ref doesn't exist, create it
        api_request("POST", f"/repos/{owner}/{repo}/git/refs", {
            "ref": f"refs/heads/{branch}",
            "sha": commit_sha,
        })
        print(f"Created branch: {branch}")
    
    print(f"\nDone! https://github.com/{owner}/{repo}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    owner, repo, local_dir = sys.argv[1:4]
    message = "Initial commit"
    branch = "main"
    if "--message" in sys.argv:
        message = sys.argv[sys.argv.index("--message") + 1]
    if "--branch" in sys.argv:
        branch = sys.argv[sys.argv.index("--branch") + 1]
    push_directory(owner, repo, local_dir, message=message, branch=branch)
