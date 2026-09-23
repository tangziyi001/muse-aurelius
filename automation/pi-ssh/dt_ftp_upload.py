#!/usr/bin/env python3
"""Dreamstime FTP upload via HTTP CONNECT proxy (port 3128).

Password is fetched at runtime from the user's Google Doc ("FTP信息") and
kept in memory only. Never printed, logged, or written to disk.
"""
import socket, base64, os, sys, urllib.parse, re

DOC_ID = "10l1QXgg3pSm-M-_YkIBRpfN9ZwRfbnt2voND0kJeEj4"
FTP_HOST = "upload.dreamstime.com"
FTP_USER = "61389332"  # numeric account ID is the FTP username (Tangziyi001 fails with 530)

def get_proxy():
    u = urllib.parse.urlparse(os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY'))
    auth = base64.b64encode(
        f"{urllib.parse.unquote(u.username)}:{urllib.parse.unquote(u.password)}".encode()
    ).decode()
    return u.hostname, u.port, auth

def connect_tunnel(target_host, target_port, timeout=20):
    ph, pp, auth = get_proxy()
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((ph, pp, 0, 0))
    s.sendall(
        f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
        f"Host: {target_host}:{target_port}\r\n"
        f"Proxy-Authorization: Basic {auth}\r\n\r\n".encode()
    )
    resp = b""
    while b"\r\n\r\n" not in resp:
        c = s.recv(4096)
        if not c:
            raise RuntimeError("proxy closed during CONNECT")
        resp += c
    if b" 200 " not in resp.split(b"\r\n")[0]:
        raise RuntimeError("proxy refused: " + resp.split(b"\r\n")[0].decode(errors="replace"))
    return s

def ftp_get_password():
    """Fetch the Google Doc and extract the Dreamstime password (memory only)."""
    url = f"https://docs.google.com/document/d/{DOC_ID}/export?format=txt"
    import subprocess
    # Use curl with the proxy env (doc is link-readable, no auth needed)
    out = subprocess.run(
        ["curl", "-sL", "--max-time", "25", url],
        capture_output=True, text=True, timeout=30,
    )
    text = out.stdout
    if not text:
        raise RuntimeError("empty doc response: " + out.stderr[:200])
    # Find the Dreamstime section and extract a password-like value.
    # Heuristic: locate 'dreamstime' (case-insensitive), then look for
    # password/pass/pwd/密码 nearby, capture the value after ':' or '='.
    lines = [l.strip() for l in text.splitlines()]
    for i, line in enumerate(lines):
        if "dreamstime" in line.lower():
            for nxt in lines[i+1:]:
                if nxt:
                    return nxt
    raise RuntimeError("could not parse Dreamstime password from doc")

class FTPOverProxy:
    def __init__(self):
        self.sock = None
        self.buf = b""

    def connect(self):
        self.sock = connect_tunnel(FTP_HOST, 21)
        self.sock.settimeout(30)
        print("S:", self._readline().decode(errors="replace").strip(), flush=True)

    def _readline(self):
        while b"\r\n" not in self.buf:
            c = self.sock.recv(4096)
            if not c:
                raise RuntimeError("FTP control connection closed")
            self.buf += c
        line, self.buf = self.buf.split(b"\r\n", 1)
        return line

    def cmd(self, command, mask=False):
        self.sock.sendall(command.encode() + b"\r\n")
        resp = self._readline().decode(errors="replace")
        # Handle multiline responses (e.g., 230- ... 230 )
        code = resp[:3]
        while len(resp) > 3 and resp[3] == "-":
            cont = self._readline().decode(errors="replace")
            resp += "\n" + cont
            if cont.startswith(code + " "):
                break
        shown = command.split(" ")[0] + " ***" if mask and " " in command else command
        print(f"C: {shown}\nS: {resp.split(chr(10))[0].strip()}", flush=True)
        return resp

    def login(self, user, password):
        r = self.cmd(f"USER {user}")
        if r.startswith("331"):
            r = self.cmd(f"PASS {password}", mask=True)
        if not r.startswith("230"):
            raise RuntimeError("login failed")
        self.cmd("TYPE I")
        try:
            self.cmd("OPTS UTF8 ON")
        except Exception:
            pass

    def pasv_tunnel(self):
        r = self.cmd("PASV")
        m = re.search(r"\((\d+,\d+,\d+,\d+,\d+,\d+)\)", r)
        if not m:
            raise RuntimeError("PASV parse failed: " + r[:100])
        nums = list(map(int, m.group(1).split(",")))
        ip = ".".join(map(str, nums[:4]))
        port = nums[4] * 256 + nums[5]
        print(f"PASV -> {ip}:{port}", flush=True)
        return connect_tunnel(ip, port, timeout=25)

    def stor(self, local_path, remote_name):
        data_sock = self.pasv_tunnel()
        r = self.cmd(f"STOR {remote_name}")
        if not (r.startswith("150") or r.startswith("125")):
            data_sock.close()
            raise RuntimeError("STOR rejected: " + r[:120])
        with open(local_path, "rb") as f:
            total = 0
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                data_sock.sendall(chunk)
                total += len(chunk)
        data_sock.close()
        r = self._readline().decode(errors="replace")
        print(f"S: {r.strip()} ({total} bytes sent)", flush=True)
        if not r.startswith("226"):
            raise RuntimeError("transfer not completed: " + r[:120])
        return total

    def size(self, remote_name):
        r = self.cmd(f"SIZE {remote_name}")
        m = re.search(r"213\s+(\d+)", r)
        return int(m.group(1)) if m else -1

    def quit(self):
        try:
            self.cmd("QUIT")
        except Exception:
            pass
        self.sock.close()

def main():
    local = sys.argv[1]
    remote = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(local)
    password = ftp_get_password()
    print(f"password acquired (len={len(password)}), connecting...", flush=True)
    ftp = FTPOverProxy()
    ftp.connect()
    ftp.login(FTP_USER, password)
    print("login OK", flush=True)
    sent = ftp.stor(local, remote)
    remote_size = ftp.size(remote)
    print(f"REMOTE SIZE: {remote_size} (local sent {sent})", flush=True)
    ftp.quit()
    if remote_size != sent or sent == 0:
        print("VERIFY FAILED", flush=True)
        return 1
    print("UPLOAD VERIFIED", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
