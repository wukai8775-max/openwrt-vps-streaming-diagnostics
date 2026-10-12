#!/usr/bin/env python3
"""Bound, limited IPv4 HTTPS or STUN probes. No configuration changes."""
import argparse
import http.client
import ipaddress
import json
import math
import os
import signal
import socket
import ssl
import statistics
import struct
import sys
import threading
import time

COOKIE = 0x2112A442
BODY_LIMIT = 65536


def ipv4(value):
    return str(ipaddress.IPv4Address(value))


def unicast_ipv4(value):
    address = ipaddress.IPv4Address(value)
    if address.is_unspecified or address.is_multicast or int(address) == 0xffffffff:
        raise argparse.ArgumentTypeError("use a concrete unicast IPv4 address")
    return str(address)


def bind_socket(sock, source, interface=None):
    if interface:
        if sys.platform == "darwin":
            sock.setsockopt(socket.IPPROTO_IP, getattr(socket, "IP_BOUND_IF", 25),
                            socket.if_nametoindex(interface))
        elif sys.platform.startswith("linux"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE,
                            interface.encode() + b"\0")
        else:
            raise OSError("interface pinning unsupported; use source binding")
    sock.bind((source, 0))
    if sock.getsockname()[0] != source:
        raise OSError("source binding mismatch")


def stun_request():
    transaction = os.urandom(12)
    return struct.pack("!HHI12s", 1, 0, COOKIE, transaction), transaction


def parse_stun(packet, transaction):
    if len(packet) < 20:
        raise ValueError("short STUN header")
    kind, length, cookie, received = struct.unpack("!HHI12s", packet[:20])
    if cookie != COOKIE or received != transaction:
        raise ValueError("unmatched STUN transaction")
    if length % 4 or len(packet) != length + 20:
        raise ValueError("invalid STUN length")
    if kind == 0x0111:
        raise ValueError("STUN binding error response")
    if kind != 0x0101:
        raise ValueError("unexpected STUN response")
    position, addresses = 20, {}
    while position < len(packet):
        if position + 4 > len(packet):
            raise ValueError("truncated attribute header")
        attr, size = struct.unpack("!HH", packet[position:position + 4])
        end = position + 4 + size
        padded_end = end + (-size % 4)
        if padded_end > len(packet):
            raise ValueError("truncated attribute")
        value = packet[position + 4:end]
        if attr in (0x0001, 0x0020) and len(value) >= 2 and value[1] == 1:
            if size != 8:
                raise ValueError("invalid IPv4 mapping")
            port, address = struct.unpack("!HI", value[2:8])
            if attr == 0x0020:
                port ^= COOKIE >> 16
                address ^= COOKIE
            if not port:
                raise ValueError("invalid mapped port")
            addresses[attr] = (ipv4(address), port)
        position = padded_end
    chosen = 0x0020 if 0x0020 in addresses else 0x0001
    if chosen not in addresses:
        raise ValueError("missing IPv4 mapping")
    address, port = addresses[chosen]
    return {"exit_ipv4": address, "mapped_port": port}


class BoundHTTPS(http.client.HTTPSConnection):
    def __init__(self, args):
        super().__init__(args.host, port=args.port, context=ssl.create_default_context())
        self.args = args
        self.connections = 0

    def connect(self):
        # Assign before connect so the whole-transaction timer can close this socket.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        bind_socket(self.sock, self.args.source, self.args.interface)
        self.sock.settimeout(max(0.001, self.deadline - time.monotonic()))
        self.sock.connect((self.args.server_ip, self.args.port))
        if self.sock.getsockname()[0] != self.args.source:
            raise OSError("connected source mismatch")
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host,
                                             do_handshake_on_connect=False)
        self.sock.settimeout(max(0.001, self.deadline - time.monotonic()))
        self.sock.do_handshake()
        self.connections += 1


def https_probe(conn, args):
    began = time.monotonic()
    expired = threading.Event()
    opened = conn.sock is None
    conn.deadline = began + args.timeout
    row = {"phase": "cold" if opened else "warm", "ok": False}

    def expire():
        expired.set()
        sock = conn.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    timer = threading.Timer(args.timeout, expire)
    timer.daemon = True
    timer.start()
    try:
        if conn.sock is not None:
            conn.sock.settimeout(args.timeout)
        conn.request("GET", args.path, headers={"Connection": "keep-alive"})
        response = conn.getresponse()
        body = response.read(BODY_LIMIT + 1)
        if len(body) > BODY_LIMIT:
            raise ValueError("response body exceeds probe limit")
        if expired.is_set() or time.monotonic() >= conn.deadline:
            raise TimeoutError("whole transaction deadline")
        row.update(ok=response.status == args.status, http_status=response.status,
                   response_bytes=len(body), connections=conn.connections)
    except (OSError, http.client.HTTPException, ValueError) as error:
        row["error_type"] = "TimeoutError" if expired.is_set() else type(error).__name__
        conn.close()
    finally:
        timer.cancel()
        timer.join()
    row["elapsed_ms"] = round((time.monotonic() - began) * 1000, 3)
    return row


def udp_probe(sock, args):
    began = time.monotonic()
    deadline = began + args.timeout
    request, transaction = stun_request()
    ignored = 0
    row = {"ok": False}
    try:
        sock.send(request)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("STUN transaction deadline")
            sock.settimeout(remaining)
            packet = sock.recv(4096)
            # Late replies belong to earlier transactions, not this sample.
            if len(packet) < 20 or packet[8:20] != transaction:
                ignored += 1
                continue
            mapped = parse_stun(packet, transaction)
            row.update(mapped)
            row["ok"] = not args.expect_exit or mapped["exit_ipv4"] == args.expect_exit
            if not row["ok"]:
                row["error_type"] = "ExitMismatch"
            break
    except (OSError, ValueError) as error:
        row["error_type"] = type(error).__name__
    row.update(elapsed_ms=round((time.monotonic() - began) * 1000, 3),
               ignored_packets=ignored)
    return row


def summarize(rows):
    values = sorted(row["elapsed_ms"] for row in rows if row["ok"])
    result = {"attempts": len(rows), "successes": len(values),
              "failures": len(rows) - len(values),
              "timeouts": sum(r.get("error_type") == "TimeoutError" for r in rows)}
    if values:
        result.update(success_median_ms=statistics.median(values), success_max_ms=max(values))
        if len(values) >= 20:
            result["success_p95_ms"] = values[math.ceil(.95 * len(values)) - 1]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("https", "stun"))
    parser.add_argument("--source", required=True, type=unicast_ipv4)
    parser.add_argument("--interface", help="optional OS interface pin; Linux may require privilege")
    parser.add_argument("--server-ip", required=True, type=unicast_ipv4, help="fixed endpoint; skips DNS")
    parser.add_argument("--port", type=int)
    parser.add_argument("--host", help="HTTPS hostname used for TLS certificate verification")
    parser.add_argument("--path", default="/generate_204")
    parser.add_argument("--status", default=204, type=int)
    parser.add_argument("--expect-exit", type=unicast_ipv4, help="STUN exit guard only")
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.port is None:
        args.port = 443 if args.mode == "https" else 3478
    if (not 1 <= args.port <= 65535 or not 1 <= args.samples <= 600 or
            not .1 <= args.interval <= 30 or not .1 <= args.timeout <= 10 or
            args.samples * max(args.interval, args.timeout) > 1800):
        parser.error("invalid count/port/time budget (maximum worst-case 1800 seconds)")
    if args.mode == "https" and (not args.host or not args.path.startswith("/") or
                                  any(c in args.host + args.path for c in "\r\n") or
                                  not 100 <= args.status <= 599):
        parser.error("HTTPS requires --host and valid --path/--status")
    plan = {"type": "plan", "mode": args.mode, "source_ipv4": args.source,
            "server_ipv4": args.server_ip, "port": args.port,
            "samples": args.samples, "timeout_s": args.timeout,
            "worst_case_seconds": args.samples * max(args.interval, args.timeout),
            "dry_run": args.dry_run}
    print(json.dumps(plan), flush=True)
    if args.dry_run:
        return 0

    def cancel(_signal, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, cancel)
    conn = None
    rows = []
    interrupted = False
    try:
        if args.mode == "https":
            conn = BoundHTTPS(args)
        else:
            conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            bind_socket(conn, args.source, args.interface)
            conn.connect((args.server_ip, args.port))
            if conn.getsockname()[0] != args.source:
                raise OSError("connected source mismatch")
        for i in range(args.samples):
            began = time.monotonic()
            started = time.time()
            try:
                row = https_probe(conn, args) if args.mode == "https" else udp_probe(conn, args)
            except KeyboardInterrupt:
                row = {"ok": False, "error_type": "Cancelled",
                       "phase": "interrupted", "elapsed_ms": round((time.monotonic() - began) * 1000, 3)}
                interrupted = True
            if args.mode == "https" and row["phase"] == "cold" and i:
                row["phase"] = "cold_reconnect"
            row.update(type="probe", mode=args.mode, sample=i + 1, started_at=started,
                       ended_at=time.time(), source_ipv4=args.source)
            rows.append(row)
            print(json.dumps(row), flush=True)
            if interrupted:
                break
            if i + 1 < args.samples:
                time.sleep(max(0, args.interval - (time.monotonic() - began)))
    except KeyboardInterrupt:
        interrupted = True
    except OSError as error:
        print(json.dumps({"type": "collector_error", "error_type": type(error).__name__}), flush=True)
        return 2
    finally:
        if conn is not None:
            conn.close()
    summary = summarize(rows)
    summary.update(type="summary", mode=args.mode,
                   skipped=args.samples - len(rows), interrupted=interrupted,
                   note="probe timeouts are not video packet loss; synthetic completion is not live acceptance")
    print(json.dumps(summary), flush=True)
    return 130 if interrupted else (0 if summary["failures"] == 0 else 1)


if __name__ == "__main__":
    raise SystemExit(main())
