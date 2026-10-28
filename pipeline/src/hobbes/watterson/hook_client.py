"""The command Claude Code runs for each Hobbes hook (DEC-010).

Hands the hook's JSON input (stdin) to the Hobbes session that installed the
hook, over the Unix socket named in ``argv[1]``, and prints the answer.
Standard library only, run as ``python -I -S hook_client.py SOCKET`` so it
starts fast. If Hobbes cannot be reached it prints nothing and exits 0: no
opinion, so the harness's own checks decide.
"""

import socket
import sys

#: Seconds to wait for Hobbes; below the hook's own timeout in ``hobbes.watterson.hooks``.
TIMEOUT = 8.0


def main(argv: list[str]) -> int:
    data = sys.stdin.buffer.read()
    if len(argv) < 2:
        return 0
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(TIMEOUT)
            conn.connect(argv[1])
            conn.sendall(data)
            conn.shutdown(socket.SHUT_WR)
            reply = b"".join(iter(lambda: conn.recv(65536), b""))
    except OSError:
        return 0
    sys.stdout.buffer.write(reply)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
