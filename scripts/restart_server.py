#!/usr/bin/env python3
"""Restart MCP demo server — auto-kill if port is occupied.

Usage:
    python scripts/restart_server.py
    python scripts/restart_server.py --port 8066
    python scripts/restart_server.py --port 9000 --db-host 192.168.1.100
"""

import argparse
import os
import sys
import subprocess
import socket
import time
import signal

def find_pid_on_port(port: int) -> list:
    """Find PIDs listening on the given port (Windows + Linux)."""
    pids = []
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        try:
                            pids.append(int(parts[-1]))
                        except ValueError:
                            pass
        else:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().splitlines():
                try:
                    pids.append(int(line.strip()))
                except ValueError:
                    pass
    except Exception as e:
        print(f"  Warning: could not check port {port}: {e}")
    return list(set(pids))


def kill_pid(pid: int):
    """Kill a process by PID."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "//F", "//PID", str(pid)],
                           capture_output=True, timeout=5)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        print(f"  Killed PID {pid}")
    except Exception as e:
        print(f"  Warning: could not kill PID {pid}: {e}")


def is_port_open(port: int) -> bool:
    """Check if port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    parser = argparse.ArgumentParser(description="Restart Foggy MCP Server")
    parser.add_argument("--port", type=int, default=8066)
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", type=int, default=13306)
    parser.add_argument("--db-user", default="foggy")
    parser.add_argument("--db-password", default="foggy_test_123")
    parser.add_argument("--db-name", default="foggy_test")
    args = parser.parse_args()

    print(f"[1/3] Checking port {args.port}...")
    pids = find_pid_on_port(args.port)
    if pids:
        print(f"  Port {args.port} occupied by PID(s): {pids}")
        for pid in pids:
            kill_pid(pid)
        time.sleep(2)
        if is_port_open(args.port):
            print(f"  ERROR: Port {args.port} still in use after kill. Aborting.")
            sys.exit(1)
        print(f"  Port {args.port} freed.")
    else:
        print(f"  Port {args.port} is free.")

    print(f"[2/3] Starting server on :{args.port} → {args.db_host}:{args.db_port}/{args.db_name}")

    # Change to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    # Build command
    cmd = [
        sys.executable, "-m", "foggy.demo.run_demo",
        "--port", str(args.port),
        "--db-host", args.db_host,
        "--db-port", str(args.db_port),
        "--db-user", args.db_user,
        "--db-password", args.db_password,
        "--db-name", args.db_name,
    ]

    print(f"  Command: {' '.join(cmd)}")
    print()

    # Run (foreground — Ctrl+C to stop)
    try:
        proc = subprocess.Popen(cmd)
        print(f"[3/3] Server started (PID {proc.pid}). Press Ctrl+C to stop.")
        proc.wait()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        proc.terminate()
        proc.wait(timeout=5)
        print("  Server stopped.")


if __name__ == "__main__":
    main()
