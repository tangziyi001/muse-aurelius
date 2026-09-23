#!/usr/bin/env python3
"""SSH ProxyCommand: tunnel through the runtime CONNECT proxy (tailnet port 3130).

Relay uses raw fd I/O + select only. Never use socket.makefile() here: its
buffered reads swallow the SSH banner on this proxy.
"""
import socket, base64, os, sys, urllib.parse, select, fcntl

TAILNET_PROXY_PORT = 3130

def main():
    host, port = sys.argv[1], int(sys.argv[2])
    pu = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
    u = urllib.parse.urlparse(pu)
    user = urllib.parse.unquote(u.username or '')
    pwd = urllib.parse.unquote(u.password or '')
    auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    infos = socket.getaddrinfo(u.hostname, TAILNET_PROXY_PORT,
                               socket.AF_INET6, socket.SOCK_STREAM)
    af, st, proto, canon, sa = infos[0]
    s = socket.socket(af, st, proto)
    s.settimeout(30)
    s.connect(sa)
    s.sendall(
        f"CONNECT {host}:{port} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Proxy-Authorization: Basic {auth}\r\n\r\n".encode()
    )
    resp = b""
    while b"\r\n\r\n" not in resp:
        chunk = s.recv(4096)
        if not chunk:
            sys.stderr.write("proxy closed during CONNECT\n")
            return 1
        resp += chunk
    head, _, leftover = resp.partition(b"\r\n\r\n")
    if b" 200 " not in head.split(b"\r\n")[0]:
        sys.stderr.write("proxy refused: " +
                         head.decode(errors="replace").split("\r\n")[0] + "\n")
        return 1
    if leftover:
        os.write(1, leftover)

    # Raw fd relay: fd 0 = ssh -> us, fd 1 = us -> ssh, s = tunnel socket.
    for fd in (0, 1):
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    s.setblocking(False)

    stdin_eof = False
    while True:
        rlist = [s] if stdin_eof else [0, s]
        try:
            r, _, _ = select.select(rlist, [], [], 120)
        except Exception:
            break
        if not r:
            continue
        if 0 in r:
            try:
                d = os.read(0, 65536)
            except BlockingIOError:
                d = None
            except OSError:
                d = b""
            if d is None:
                pass
            elif not d:
                stdin_eof = True
                try:
                    s.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
            else:
                # Blocking-style send: loop on writability until all
                # bytes are out. Never drop data (bulk scp stalls otherwise).
                view = memoryview(d)
                while view:
                    _, w, _ = select.select([], [s], [], 120)
                    if not w:
                        break
                    try:
                        n = s.send(view)
                    except BlockingIOError:
                        continue
                    except OSError:
                        stdin_eof = True
                        view = None
                        break
                    view = view[n:]
        if s in r:
            try:
                d = s.recv(65536)
            except BlockingIOError:
                continue
            except OSError:
                break
            if not d:
                break
            # blocking-style write to fd 1 with select for writability
            view = memoryview(d)
            while view:
                _, w, _ = select.select([], [1], [], 120)
                if not w:
                    break
                try:
                    n = os.write(1, view)
                except BlockingIOError:
                    continue
                except OSError:
                    return 0
                view = view[n:]
    return 0

sys.exit(main())
