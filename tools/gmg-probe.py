#!/usr/bin/env python3
"""Probe a Green Mountain Grills controller and report how it answers.

For grills the integration cannot find or connect to. It sends only read-only
queries (serial, firmware, status) - never a command that changes anything on
the grill - and prints a report to paste into a GitHub issue. The serial number
in the report is masked.

Before running: the grill plugged in and on Wi-Fi (it does not need to be
cooking), the GMG app closed on every phone, and this computer on the same
network as the grill. Then, with the grill's IP address from your router:

    macOS / Linux:  python3 gmg-probe.py 192.168.1.50
    Windows:        python gmg-probe.py 192.168.1.50

Standard library only, Python 3.9+ (the python3 that ships with macOS). Nothing to install.
"""

from __future__ import annotations

import argparse
import platform
import socket
import sys

# The integration speaks UDP 8080. Newer firmware has been reported with other
# ports open (80, 8081), so try the neighbors too.
UDP_PORTS = [8080, 8081, 8181, 80]
TCP_PORTS = [80, 443, 1883, 8080, 8081, 8181, 8443]

# Read-only queries. UL! is the serial, UN! the firmware, UR001! the status.
QUERIES = [(b"UL!", "serial"), (b"UN!", "firmware"), (b"UR001!", "status")]


def mask_serial(data: bytes) -> str:
    """Show a serial reply's shape without publishing the serial itself."""
    text = data.decode("ascii", "replace")
    return f"{text[:4]}{'*' * max(len(text) - 4, 0)} ({len(data)} bytes)"


def describe(label: str, data: bytes) -> str:
    if label == "serial":
        return mask_serial(data)
    if label == "firmware":
        return f"{data.decode('ascii', 'replace')!r} ({len(data)} bytes)"
    head = data[:12].hex(" ")
    return f"{len(data)} bytes, starts {head}" + (
        f", API byte (offset 8) = {data[8]}" if len(data) > 8 else ""
    )


def udp_query(host: str, port: int, message: bytes, timeout: float) -> bytes | None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.sendto(message, (host, port))
            data, _ = sock.recvfrom(1024)
        except socket.timeout:  # noqa: UP041 - not TimeoutError on 3.9 (stock macOS)
            return None
        except OSError as err:
            return f"error: {err}".encode()
        return data


def udp_broadcast(port: int, timeout: float) -> list[str]:
    found = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        try:
            sock.sendto(b"UL!", ("255.255.255.255", port))
            while True:
                _, (address, _) = sock.recvfrom(1024)
                found.append(address)
        except socket.timeout:  # noqa: UP041 - not TimeoutError on 3.9 (stock macOS)
            pass
        except OSError as err:
            found.append(f"error: {err}")
    return found


def tcp_check(host: str, port: int, timeout: float) -> str:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            if port in (443, 1883, 8443):
                return "open"
            sock.settimeout(timeout)
            sock.sendall(f"GET / HTTP/1.0\r\nHost: {host}\r\n\r\n".encode())
            try:
                reply = sock.recv(512).decode("latin-1", "replace")
            except socket.timeout:  # noqa: UP041 - not TimeoutError on 3.9 (stock macOS)
                return "open, no HTTP reply"
            lines = reply.splitlines()
            first = lines[0] if lines else "(empty reply)"
            server = next((ln for ln in lines if ln.lower().startswith("server:")), "")
            return f"open, {first}" + (f", {server}" if server else "")
    except socket.timeout:  # noqa: UP041 - not TimeoutError on 3.9 (stock macOS)
        return "no answer (filtered or closed)"
    except ConnectionRefusedError:
        return "closed"
    except OSError as err:
        return f"error: {err}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("host", help="the grill's IP address")
    parser.add_argument("--timeout", type=float, default=2.0, help="seconds per try")
    parser.add_argument("--tries", type=int, default=8, help="attempts per port")
    args = parser.parse_args()

    print("Probing the grill - this can take up to two minutes...", file=sys.stderr)
    report = [
        (
            f"gmg-probe  host={args.host}  python={platform.python_version()}"
            f"  os={platform.system()}"
        ),
        "",
        "UDP queries (the integration uses 8080):",
    ]
    answered = False
    for port in UDP_PORTS:
        # A grill answers one client at a time and often drops a query, so a
        # single silence proves nothing. Ask for the serial until it answers.
        print(f"  checking UDP port {port}...", file=sys.stderr)
        data, tries = None, 0
        for tries in range(1, args.tries + 1):
            data = udp_query(args.host, port, b"UL!", args.timeout)
            if data is not None:
                break
        if data is None:
            report.append(f"  udp {port:<5} no reply in {args.tries} tries")
            continue
        if data.startswith(b"error: "):
            report.append(f"  udp {port:<5} {data.decode()}")
            continue
        answered = True
        report.append(
            f"  udp {port:<5} UL!     {describe('serial', data)}, try {tries}"
        )
        for message, label in QUERIES[1:]:
            reply = None
            for _ in range(args.tries):
                reply = udp_query(args.host, port, message, args.timeout)
                if reply is not None:
                    break
            result = "no reply" if reply is None else describe(label, reply)
            report.append(f"  udp {port:<5} {message.decode():<7} {result}")

    print("  checking broadcast discovery...", file=sys.stderr)
    report += ["", "UDP broadcast discovery (UL!):"]
    for port in UDP_PORTS[:2]:
        found: list[str] = []
        for _ in range(args.tries):
            found = udp_broadcast(port, args.timeout)
            if found:
                break
        report.append(f"  udp {port:<5} {', '.join(found) if found else 'no replies'}")

    print("  checking TCP ports...", file=sys.stderr)
    report += ["", "TCP ports:"]
    for port in TCP_PORTS:
        report.append(f"  tcp {port:<5} {tcp_check(args.host, port, args.timeout)}")

    print("\nDone. Copy everything from the first ``` to the last ``` below:\n")
    print("```")
    print("\n".join(report))
    print("```")
    if not answered:
        print(
            "\nThe grill did not answer on any UDP port. A likely cause "
            "is Server Mode: turn it off in the GMG app's Wi-Fi settings and run "
            "this again. Either way, please paste the report into the issue."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
