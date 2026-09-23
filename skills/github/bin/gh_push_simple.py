#!/usr/bin/env python3
"""Push a local directory to a GitHub repo using the Contents API (works on empty repos).

Usage: python3 gh_push_simple.py <owner> <repo> <local_dir> [--message MSG]
"""
import sys
import os

sys.path.insert(0, os.path.expanduser("~/workspace/skills/github/bin"))
from gh_api import cmd_create_file


def push_directory(owner, repo, local_dir, message="Initial commit"):
    files = []
    for root, dirs, filenames in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d != '.git']
        for fn in filenames:
            full_path = os.path.join(root, fn)
            rel_path = os.path.relpath(full_path, local_dir)
            files.append((rel_path, full_path))
    
    print(f"Pushing {len(files)} files...")
    for i, (rel_path, full_path) in enumerate(files):
        try:
            cmd_create_file(owner, repo, rel_path, full_path, message=f"{message}: {rel_path}")
        except SystemExit as e:
            print(f"Failed: {rel_path}", file=sys.stderr)
            # Continue with next file
        if (i + 1) % 10 == 0:
            print(f"  Pushed {i+1}/{len(files)}...")
    
    print(f"\nDone! https://github.com/{owner}/{repo}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    owner, repo, local_dir = sys.argv[1:4]
    message = "Add files"
    if "--message" in sys.argv:
        message = sys.argv[sys.argv.index("--message") + 1]
    push_directory(owner, repo, local_dir, message=message)
