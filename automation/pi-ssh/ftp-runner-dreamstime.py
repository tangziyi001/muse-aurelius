#!/usr/bin/env python3
"""Dreamstime FTP outbox runner — runs on the Home Assistant Pi.

Triggered by an HA automation every 15 minutes (and on HA start).
Scans /config/ftp-runner/outbox/dreamstime/ for new .jpg files, uploads them
to Dreamstime via FTP, and verifies each with SIZE.

Security: the FTP password is fetched at runtime from the user's Google Doc
and kept in process memory only. It is never written to disk, never printed,
never logged, and never appears in command lines. Log lines are scrubbed.
"""
import fcntl
import ftplib
import json
import logging
import os
import socket
import sys
import time
import urllib.request

BASE = "/config/ftp-runner"
OUTBOX = os.path.join(BASE, "outbox", "dreamstime")
SENT_DIR = os.path.join(OUTBOX, "sent")
STATE_FILE = os.path.join(BASE, "state", "dreamstime.json")
LOG_FILE = os.path.join(BASE, "logs", "runner.log")
LOCK_FILE = os.path.join(BASE, "runner.lock")

DOC_URL = ("https://docs.google.com/document/d/"
           "10l1QXgg3pSm-M-_YkIBRpfN9ZwRfbnt2voND0kJeEj4/export?format=txt")
FTP_HOST = "upload.dreamstime.com"
FTP_USER = "61389332"  # numeric account ID; the website username does NOT work
MAX_ATTEMPTS = 3
BACKOFF_SECS = [10, 30, 90]

_secret = ""  # the fetched password; memory only


class ScrubFilter(logging.Filter):
    def filter(self, record):
        if _secret:
            def scrub(v):
                return v.replace(_secret, "***") if isinstance(v, str) else v
            record.msg = scrub(record.msg)
            if record.args:
                record.args = tuple(scrub(a) for a in record.args)
        return True


def setup_logging():
    logger = logging.getLogger("ftp-runner")
    logger.setLevel(logging.INFO)
    h = logging.FileHandler(LOG_FILE)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    h.addFilter(ScrubFilter())
    logger.addHandler(h)
    return logger


def fetch_password(service, log):
    """Fetch the password for `service` from the Google Doc (memory only)."""
    req = urllib.request.Request(
        DOC_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8-sig", errors="replace")
    lines = [l.strip() for l in text.splitlines()]
    for i, line in enumerate(lines):
        if line.lower() == service.lower():
            for nxt in lines[i + 1:]:
                if nxt:
                    log.info("password retrieved for %s (%d chars)",
                             service, len(nxt))
                    return nxt
    raise RuntimeError("password not found in doc for service: " + service)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"uploaded": {}, "failed": {}}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, STATE_FILE)


def upload_one(ftp, local_path, log):
    """STOR one file and verify via SIZE. Retries with backoff."""
    name = os.path.basename(local_path)
    size_local = os.path.getsize(local_path)
    if size_local == 0:
        raise RuntimeError("local file is empty, refusing to upload")
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with open(local_path, "rb") as f:
                ftp.storbinary("STOR " + name, f)
            size_remote = ftp.size(name)
            if size_remote == size_local and size_remote > 0:
                log.info("OK %s (%d bytes, verified)", name, size_remote)
                return size_remote
            raise RuntimeError(
                "SIZE mismatch: local=%d remote=%s" % (size_local, size_remote))
        except Exception as e:  # noqa: BLE001 - retried below
            last_err = "%s: %s" % (type(e).__name__, e)
            log.warning("attempt %d/%d failed for %s: %s",
                        attempt, MAX_ATTEMPTS, name, last_err)
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECS[attempt - 1]
                           if attempt - 1 < len(BACKOFF_SECS) else 120)
    raise RuntimeError("all attempts failed: " + (last_err or "unknown"))


def main():
    global _secret
    os.makedirs(SENT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    log = setup_logging()

    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log.info("another run in progress, exiting")
        return 0

    state = load_state()
    try:
        files = sorted(
            f for f in os.listdir(OUTBOX)
            if f.lower().endswith(".jpg")
            and os.path.isfile(os.path.join(OUTBOX, f)))
    except OSError as e:
        log.error("cannot list outbox: %s", e)
        return 1
    pending = [f for f in files if f not in state["uploaded"]]
    if not pending:
        log.info("run finished: outbox empty, nothing to do")
        return 0

    log.info("run started: %d file(s) pending", len(pending))
    try:
        _secret = fetch_password("dreamstime", log)
    except Exception as e:  # noqa: BLE001
        log.error("password fetch failed: %s: %s", type(e).__name__, e)
        return 1

    socket.setdefaulttimeout(60)
    ok, failed = 0, 0
    try:
        ftp = ftplib.FTP(FTP_HOST, timeout=60)
        try:
            ftp.login(FTP_USER, _secret)
            log.info("FTP login ok as %s", FTP_USER)
            for name in pending:
                path = os.path.join(OUTBOX, name)
                try:
                    size = upload_one(ftp, path, log)
                    state["uploaded"][name] = {
                        "size": size, "at": time.strftime("%FT%TZ", time.gmtime())}
                    state["failed"].pop(name, None)
                    os.replace(path, os.path.join(SENT_DIR, name))
                    ok += 1
                except Exception as e:  # noqa: BLE001
                    state["failed"][name] = {
                        "error": str(e)[:300],
                        "at": time.strftime("%FT%TZ", time.gmtime())}
                    failed += 1
        finally:
            try:
                ftp.quit()
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001
        log.error("FTP connection/login failed: %s: %s", type(e).__name__, e)
        return 1
    finally:
        save_state(state)
        _secret = ""  # drop from memory as soon as possible
    log.info("run finished: %d uploaded, %d failed", ok, failed)
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
