#!/usr/bin/env python3
"""Run the house-model read-only QA checks with bounded keep-going diagnostics."""

from __future__ import annotations

import argparse
from collections import deque
import fcntl
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

HEAD_LINES = 80
TAIL_LINES = 40


def display_log(path: Path, verbose: bool) -> None:
    if verbose:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                print(line, end="")
        return
    head: list[str] = []
    tail: deque[str] = deque(maxlen=TAIL_LINES)
    count = 0
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            count += 1
            (head if len(head) < HEAD_LINES else tail).append(line)
    for line in head:
        print(line, end="")
    if count > HEAD_LINES + TAIL_LINES:
        print(f"... {count - HEAD_LINES - TAIL_LINES} line(s) omitted; use VERBOSE=1 to recover complete output ...")
    for line in tail:
        print(line, end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--semasvg", required=True)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    var = Path("var")
    if var.is_symlink() or (var.exists() and not var.is_dir()):
        print("ERROR qa: var must be a non-symlink directory")
        return 2
    # This suite owns only this fixed ignored subtree, never caller-selected paths.
    root = var / "qa"
    latest = root / "latest"
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        print("ERROR qa: var/qa must be a non-symlink directory")
        return 2
    try:
        root.mkdir(parents=True, exist_ok=True)
        if (root / ".lock").is_symlink():
            print("ERROR qa: var/qa/.lock must not be a symlink")
            return 2
        lock_handle = (root / ".lock").open("w")
    except OSError as error:
        print(f"ERROR qa: cannot prepare var/qa: {error}")
        return 2
    with lock_handle as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            print(f"ERROR qa: cannot lock var/qa/.lock: {error}")
            return 2
        if latest.is_symlink() or (latest.exists() and not latest.is_dir()):
            print("ERROR qa: var/qa/latest must be a non-symlink directory")
            return 2
        try:
            if latest.exists():
                shutil.rmtree(latest)
            latest.mkdir()
        except OSError as error:
            print(f"ERROR qa: cannot prepare var/qa/latest: {error}")
            return 2
        active: set[subprocess.Popen[bytes]] = set()
        active_lock = threading.Lock()
        stopped = threading.Event()
        interrupted_status: int | None = None

        def stop(signum: int, _frame: object) -> None:
            nonlocal interrupted_status
            stopped.set()
            if interrupted_status is None:
                interrupted_status = 130 if signum == signal.SIGINT else 143
            with active_lock:
                processes = tuple(active)
            # Children run in their own groups so descendants cannot survive an interrupted suite.
            for process in processes:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            for process in processes:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        commands = (
            ("validate", [args.semasvg, "validate", "model"]),
            ("format", [args.semasvg, "format", "model", "--check"]),
            ("labels", [args.semasvg, "materialize-labels", "model", "--check"]),
            ("graph", [args.semasvg, "inspect-graph", "model"]),
        )

        def run(item: tuple[str, list[str]]) -> tuple[str, int | None, str | None]:
            name, command = item
            try:
                if stopped.is_set():
                    return name, None, "QA run was interrupted"
                with (latest / f"{name}.log").open("wb") as log:
                    with active_lock:
                        if stopped.is_set():
                            return name, None, "QA run was interrupted"
                        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                        active.add(process)
                    try:
                        status = process.wait()
                    finally:
                        with active_lock:
                            active.discard(process)
                return name, status, None
            except OSError as error:
                return name, None, str(error)

        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            results = list(executor.map(run, commands))
        errors = failures = False
        for name, status, error in results:
            if error is not None:
                errors = True
                print(f"ERROR {name}: {error}")
            elif status == 0:
                print(f"PASS {name}")
            else:
                failures = True
                print(f"FAIL {name} (exit {status})")
                display_log(latest / f"{name}.log", args.verbose)
        if interrupted_status is not None:
            return interrupted_status
        return 2 if errors else 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
