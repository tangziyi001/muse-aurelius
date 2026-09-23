"""Credential + token storage for Pinterest automation. Mirrors etsy-automation/config.py."""
import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/pinterest-automation")
ENV_FILE = os.path.join(CONFIG_DIR, "env")            # KEY=VALUE, mode 600
TOKENS_FILE = os.path.join(CONFIG_DIR, "tokens.json")  # mode 600
APPROVAL_FLAG = os.path.join(CONFIG_DIR, "standard_approved")  # touch when Standard access granted


def _ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)


def load_env():
    _ensure_dir()
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def save_env(env):
    _ensure_dir()
    with open(ENV_FILE, "w") as f:
        for k, v in env.items():
            f.write(f"{k}={v}\n")
    os.chmod(ENV_FILE, 0o600)


def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        return None
    with open(TOKENS_FILE) as f:
        return json.load(f)


def save_tokens(tokens):
    _ensure_dir()
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=1)
    os.chmod(TOKENS_FILE, 0o600)


def is_standard_approved():
    return os.path.exists(APPROVAL_FLAG)
