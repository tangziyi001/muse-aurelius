#!/usr/bin/env python3
"""FTP outbox runner — runs on the Home Assistant Pi.

Triggered by an HA automation every 15 minutes (and on HA start).
Scans /config/ftp-runner/outbox/<service>/ for new .jpg files, uploads them
to each service via FTP, and verifies each with SIZE.

Services:
  dreamstime — upload.dreamstime.com:21, user 61389332 (numeric account ID;
               the website username does NOT work), uploads to login dir.
  123rf      — ftp.123rf.com:21, user ziyitang, uploads to the "AI images"
               remote directory (AI-generated content must go there).

Security: FTP passwords live in /config/ftp-runner/secrets/<service>
(chmod 600, written once by a separate migration script). The runner reads
them into process memory only: they are never printed, never logged, and
never appear in command lines. Log lines are scrubbed of every secret.
If a secret file is missing or unreadable, that service is skipped
(fail closed) and an error is logged; nothing is uploaded.
"""
import fcntl
import ftplib
import json
import logging
import os
import socket
import sys
import time

BASE = "/config/ftp-runner"
SECRETS_DIR = os.path.join(BASE, "secrets")
LOG_FILE = os.path.join(BASE, "logs", "runner.log")
LOCK_FILE = os.path.join(BASE, "runner.lock")

MAX_ATTEMPTS = 3
BACKOFF_SECS = [10, 30, 90]

SERVICES = {
    "dreamstime": {
        "outbox": os.path.join(BASE, "outbox", "dreamstime"),
        "state_file": os.path.join(BASE, "state", "dreamstime.json"),
        "ftp_host": "upload.dreamstime.com",
        "ftp_user": "61389332",  # numeric account ID
        "remote_dir": None,       # upload to the login directory
    },
    "123rf": {
        "outbox": os.path.join(BASE, "outbox", "123rf"),
        "state_file": os.path.join(BASE, "state", "123rf.json"),
        "ftp_host": "ftp.123rf.com",
        "ftp_user": "ziyitang",
        "remote_dir": "AI images",  # AI content must land in this dir
    },
}

_secrets = []  # retrieved passwords; memory only


class ScrubFilter(logging.Filter):
    def filter(self, record):
        for s in _secrets:
            if not s:
                continue

            def scrub(v):
                return v.replace(s, "***") if isinstance(v, str) else v

            record.msg = scrub(record.msg)
            if record.args:
                record.args = tuple(scrub(a) for a in record.args)
        return True


def setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logger = logging.getLogger("ftp-runner")
    logger.setLevel(logging.INFO)
    h = logging.FileHandler(LOG_FILE)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    h.addFilter(ScrubFilter())
    logger.addHandler(h)
    return logger


def read_secret(name, log):
    """Read the FTP password for `name` from the local secret file.

    Fail closed: raises RuntimeError if the file is missing, unreadable,
    or empty. The secret is kept in memory only and registered with the
    log scrubber; it is never printed or logged.
    """
    path = os.path.join(SECRETS_DIR, name)
    try:
        with open(path) as f:
            pw = f.read()
    except OSError as e:
        raise RuntimeError("secret file unreadable: %s" % e)
    if not pw:
        raise RuntimeError("secret file empty: " + path)
    log.info("secret loaded for %s (%d chars)", name, len(pw))
    _secrets.append(pw)
    return pw


def load_state(state_file):
    try:
        with open(state_file) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"uploaded": {}, "failed": {}}


def save_state(state_file, state):
    tmp = state_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, state_file)


def upload_one(ftp, local_path, log):
    """STOR one file (in the current remote dir) and verify via SIZE."""
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


def pending_files(outbox):
    try:
        files = sorted(
            f for f in os.listdir(outbox)
            if f.lower().endswith(".jpg")
            and os.path.isfile(os.path.join(outbox, f)))
    except OSError:
        return []
    return files


def run_service(name, cfg, log):
    """Upload pending files for one service. Returns (ok, failed)."""
    outbox = cfg["outbox"]
    sent_dir = os.path.join(outbox, "sent")
    os.makedirs(sent_dir, exist_ok=True)
    os.makedirs(os.path.dirname(cfg["state_file"]), exist_ok=True)

    state = load_state(cfg["state_file"])
    pending = [f for f in pending_files(outbox) if f not in state["uploaded"]]
    if not pending:
        log.info("[%s] outbox empty, nothing to do", name)
        return 0, 0

    log.info("[%s] run started: %d file(s) pending", name, len(pending))
    try:
        secret = read_secret(name, log)
    except Exception as e:  # noqa: BLE001
        log.error("[%s] secret unavailable, skipping (fail closed): %s: %s",
                  name, type(e).__name__, e)
        return 0, len(pending)

    ok, failed = 0, 0
    try:
        ftp = ftplib.FTP(cfg["ftp_host"], timeout=60)
        try:
            ftp.login(cfg["ftp_user"], secret)
            log.info("[%s] FTP login ok as %s", name, cfg["ftp_user"])
            if cfg["remote_dir"]:
                ftp.cwd(cfg["remote_dir"])
                log.info("[%s] remote dir: %s (pwd=%s)",
                         name, cfg["remote_dir"], ftp.pwd())
            for fname in pending:
                path = os.path.join(outbox, fname)
                try:
                    size = upload_one(ftp, path, log)
                    state["uploaded"][fname] = {
                        "size": size,
                        "at": time.strftime("%FT%TZ", time.gmtime())}
                    state["failed"].pop(fname, None)
                    os.replace(path, os.path.join(sent_dir, fname))
                    ok += 1
                except Exception as e:  # noqa: BLE001
                    state["failed"][fname] = {
                        "error": str(e)[:300],
                        "at": time.strftime("%FT%TZ", time.gmtime())}
                    log.error("[%s] FAILED %s: %s", name, fname, str(e)[:200])
                    failed += 1
        finally:
            try:
                ftp.quit()
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001
        log.error("[%s] FTP connection/login failed: %s: %s",
                  name, type(e).__name__, e)
        return 0, len(pending)
    finally:
        save_state(cfg["state_file"], state)
    log.info("[%s] run finished: %d uploaded, %d failed", name, ok, failed)
    return ok, failed


def main():
    log = setup_logging()

    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log.info("another run in progress, exiting")
        return 0

    socket.setdefaulttimeout(60)
    total_ok, total_failed = 0, 0
    try:
        for name, cfg in SERVICES.items():
            ok, failed = run_service(name, cfg, log)
            total_ok += ok
            total_failed += failed
    finally:
        _secrets.clear()  # drop passwords from memory as soon as possible
    log.info("run finished: %d uploaded, %d failed (all services)",
             total_ok, total_failed)
    return 0 if total_failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
