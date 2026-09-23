#!/usr/bin/env python3
"""GitHub API CLI using the stored custom.github credential.

Usage:
  python3 gh_api.py create-repo <name> [--private] [--description TEXT]
  python3 gh_api.py get-user
  python3 gh_api.py create-file <owner> <repo> <path> <local_file> [--message MSG]
"""
import sys
import os
import json
import base64

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    dynamic_credential_entry,
    add_surrogate_to_request,
    read_json_response,
)
import urllib.request


def get_auth_headers():
    """Get headers with the GitHub token surrogate."""
    # Use a dummy request to get the surrogate header via the helper
    req = urllib.request.Request("https://api.github.com/user")
    add_surrogate_to_request(req, "custom.github", allowed_hosts=["api.github.com"])
    # Extract the Authorization header value
    auth_val = req.get_header("Authorization")
    return {
        "Authorization": auth_val,
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "muse-aurelius/1.0",
    }


def api_request(method, path, data=None):
    """Make an authenticated GitHub API request."""
    url = f"https://api.github.com{path}"
    headers = get_auth_headers()
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return read_json_response(resp), resp.status
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        print(f"HTTP {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)


def cmd_get_user():
    data, _ = api_request("GET", "/user")
    print(f"Logged in as: {data['login']}")
    return data


def cmd_create_repo(name, private=True, description=""):
    data, status = api_request("POST", "/user/repos", {
        "name": name,
        "private": private,
        "description": description,
        "auto_init": False,
    })
    print(f"Created repo: {data['full_name']} (private={data['private']})")
    print(f"URL: {data['html_url']}")
    return data


def cmd_create_file(owner, repo, path, local_file, message="Add file"):
    with open(local_file, 'rb') as f:
        content = base64.b64encode(f.read()).decode('ascii')
    data, _ = api_request("PUT", f"/repos/{owner}/{repo}/contents/{path}", {
        "message": message,
        "content": content,
    })
    print(f"Created: {path}")
    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "get-user":
        cmd_get_user()
    elif cmd == "create-repo":
        name = sys.argv[2]
        private = "--private" in sys.argv or "--public" not in sys.argv
        desc = ""
        if "--description" in sys.argv:
            desc = sys.argv[sys.argv.index("--description") + 1]
        cmd_create_repo(name, private=private, description=desc)
    elif cmd == "create-file":
        owner, repo, path, local_file = sys.argv[2:6]
        msg = sys.argv[6] if len(sys.argv) > 6 else f"Add {path}"
        # Handle --message flag
        if "--message" in sys.argv:
            msg = sys.argv[sys.argv.index("--message") + 1]
        cmd_create_file(owner, repo, path, local_file, message=msg)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
