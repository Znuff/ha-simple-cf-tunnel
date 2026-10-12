"""Logging and child-process helpers shared by both tunnels."""

import subprocess


def log(message):
    print(f"[controller] {message}", flush=True)


def pump(proc, name, tail):
    """Forward a child's output to the add-on log, keeping the last lines in `tail`."""
    for line in proc.stdout:
        line = line.rstrip()
        print(f"[{name}] {line}", flush=True)
        tail.append(line)


def terminate(proc):
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
