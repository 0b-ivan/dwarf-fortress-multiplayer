#!/usr/bin/env python3
"""Advertise dwarf.local and client.dwarf.local on macOS across network changes."""
import argparse
import os
from pathlib import Path
import plistlib
import re
import signal
import subprocess
import sys
import time

LABEL = "org.dwarf-fortress.bonjour"
PLIST = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
SCRIPT = Path(__file__).resolve()
SERVICES = [("Dwarf Fortress Admin", "dwarf.local."),
            ("Dwarf Fortress Multiplayer", "client.dwarf.local.")]


def address(interface):
    result = subprocess.run(
        ["/sbin/ifconfig", interface], capture_output=True, text=True
    )
    if result.returncode or "status: active" not in result.stdout:
        return None
    match = re.search(r"\binet (\d+\.\d+\.\d+\.\d+)\b", result.stdout)
    return match.group(1) if match else None


def stop(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def advertise(interface):
    children = []
    previous = None

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        while True:
            current = address(interface)
            if current != previous or (current and (not children or any(
                    child.poll() is not None for child in children))):
                for child in children:
                    stop(child)
                children = []
                if current:
                    for title, host in SERVICES:
                        print(f"Advertising http://{host.rstrip('.')} -> {current} ({interface})", flush=True)
                        children.append(subprocess.Popen([
                            "/usr/bin/dns-sd", "-P", title, "_http._tcp",
                            "local.", "80", host, current, "path=/",
                        ]))
                else:
                    print(f"Waiting for IPv4 on {interface}", flush=True)
                previous = current
            time.sleep(15)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            stop(child)


def install(interface):
    # Per-user agent: starts at login without renaming the Mac or requiring sudo.
    logs = SCRIPT.parent.parent / "data/lan"
    logs.mkdir(parents=True, exist_ok=True)
    config = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(SCRIPT), "run", "--interface", interface],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 15,
        "StandardOutPath": str(logs / "bonjour.log"),
        "StandardErrorPath": str(logs / "bonjour-error.log"),
    }
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    if PLIST.exists():
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(PLIST)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    PLIST.write_bytes(plistlib.dumps(config))
    result = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(PLIST)])
    if result.returncode:
        raise SystemExit(
            f"Login agent written to {PLIST}, but launchctl could not start it. "
            "Run make lan-bonjour from a normal macOS Terminal to activate it."
        )
    print(f"Installed {PLIST}; http://dwarf.local (interface {interface})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "install", "uninstall", "status"])
    parser.add_argument("--interface", default="en0", help="macOS LAN interface (default: en0)")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This helper requires macOS. See docs/lan.md for Linux hosts.")
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9]*", args.interface):
        parser.error("Invalid interface name")
    if args.command == "run":
        advertise(args.interface)
    elif args.command == "install":
        install(args.interface)
    elif args.command == "uninstall":
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(PLIST)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        PLIST.unlink(missing_ok=True)
        print("Bonjour login agent removed")
    else:
        print(f"{args.interface}: {address(args.interface) or 'no active IPv4 address'}")
        subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"], check=True)


if __name__ == "__main__":
    main()
