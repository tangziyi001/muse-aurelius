---
name: "github"
description: "Use Github when the user asks for Github or this provider's API."
---

# Github

## Purpose
Use Github with the user-connected `custom.github` credential. Create repos, push code, manage files via the GitHub REST API.

## Tooling
CLIs under `~/workspace/skills/github/bin/`:
- `gh_api.py` — Low-level API: `get-user`, `create-repo <name> [--private]`, `create-file <owner> <repo> <path> <local_file>`
- `gh_push_simple.py` — Push a local directory to a repo (Contents API, works on empty repos): `gh_push_simple.py <owner> <repo> <local_dir>`
- `gh_sync.py` — Auto-sync: detects changed/new/deleted files, scans for secrets, pushes incrementally. State in `hidden_files/.gh_sync_state.json`. Run with `--dry-run` to preview.
- `test_gh_sync.py` — Unit tests for the sync logic (23 tests, pytest).

## Auto-sync
A cron job `github-auto-sync` runs `gh_sync.py` hourly. It syncs:
- `~/workspace/skills/` → `skills/`
- `~/workspace/pi-ssh/`, `etsy-automation/`, `pinterest-automation/` → `automation/`
- `instagram-setup/ab-test/render_reel.py`, `test_render_reel.py` → `reel-factory/`

Excludes `__pycache__/`, `.env`, credentials, state files, logs. Files matching secret patterns (email, phone, API keys) are skipped, never pushed.

Python CLIs must import `/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py` and use `add_surrogate_to_request(req, "custom.github", allowed_hosts=["api.github.com"])` before authenticated requests.

## Auth
The credential is already stored (custom.github); nothing here collects one. Never ask the user to paste a raw key in chat, set a secret environment variable, pass a secret flag, or write an auth file.

A 401 or 403 is a question about the request before it is a question about the key. Check that the credential was attached at all. Only once a request that did carry the credential is still rejected, call `credentials.request_api_access` with `reconnect` to replace it.

## Operating Rules
1. Use this skill when the user asks for Github or this provider's API.
2. Restrict authenticated requests to: api.github.com.
3. Do not print, log, or persist raw credentials.
4. Default to private repos unless user says public.
5. Before pushing code: scrub secrets (use env vars), add .gitignore, provide .env.example.
