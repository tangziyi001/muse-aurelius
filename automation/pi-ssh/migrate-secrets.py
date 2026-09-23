#!/usr/bin/env python3
"""One-time migration: Google Doc -> /config/ftp-runner/secrets/ (chmod 600).

Fetches the Dreamstime and 123RF FTP passwords from the user's Google Doc
in process memory only, writes each to /config/ftp-runner/secrets/<name>
with mode 600, and verifies the write by byte length. The plaintext password
is NEVER printed, logged, or passed on any command line.

After this runs successfully, the runner reads secrets from local files and
the Google Doc is no longer used by the pipeline.
"""
import os
import stat
import urllib.request

DOC_URL = ("https://docs.google.com/document/d/"
           "10l1QXgg3pSm-M-_YkIBRpfN9ZwRfbnt2voND0kJeEj4/export?format=txt")
SECRETS_DIR = "/config/ftp-runner/secrets"
# doc section header (lowercased) -> secret file name
SERVICES = {"dreamstime": "dreamstime", "123rf": "123rf"}


def fetch_all():
    req = urllib.request.Request(
        DOC_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8-sig", errors="replace")
    lines = [l.strip() for l in text.splitlines()]
    found = {}
    for i, line in enumerate(lines):
        key = line.lower()
        if key in SERVICES and key not in found:
            for nxt in lines[i + 1:]:
                if nxt:
                    found[key] = nxt
                    break
    return found


def main():
    secrets = fetch_all()
    missing = [k for k in SERVICES if k not in secrets or not secrets[k]]
    if missing:
        raise SystemExit("missing passwords in doc for: " + ",".join(missing))

    os.makedirs(SECRETS_DIR, exist_ok=True)
    os.chmod(SECRETS_DIR, 0o700)

    for key, fname in SERVICES.items():
        pw = secrets[key]
        path = os.path.join(SECRETS_DIR, fname)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(pw)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        with open(path) as f:
            back = f.read()
        len_ok = len(back.encode("utf-8")) == len(pw.encode("utf-8")) > 0
        mode_ok = stat.S_IMODE(os.stat(path).st_mode) == 0o600
        print("%s: wrote %d bytes, length_match=%s, mode_600=%s"
              % (fname, len(back.encode("utf-8")), len_ok, mode_ok))
        if not (len_ok and mode_ok):
            raise SystemExit("verification failed for " + fname)
        secrets[key] = ""  # drop from memory ASAP

    print("migration complete: 2 secret files written, doc no longer needed")


if __name__ == "__main__":
    main()
