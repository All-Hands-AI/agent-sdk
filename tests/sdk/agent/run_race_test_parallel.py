#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


DEFAULT_TEST_NODE = (
    "tests/sdk/agent/test_multiple_tool_calls_race.py::"
    "TestMultipleToolCallsRace::test_multiple_tool_calls_race_condition"
)


def run_one(
    idx: int, nodeid: str, use_uv: bool = True, extra_args: list[str] | None = None
) -> tuple[int, int, str]:
    cmd = []
    if use_uv and shutil.which("uv"):
        cmd.extend(["uv", "run"])  # prefer uv if available on PATH
    cmd.extend(["pytest", "-q", nodeid])
    if extra_args:
        cmd.extend(extra_args)

    env = os.environ.copy()
    start = datetime.now()
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=os.getcwd(),
        env=env,
        text=True,
    )
    duration = (datetime.now() - start).total_seconds()
    return (
        idx,
        proc.returncode,
        f"[run {idx:02d}] rc={proc.returncode} dur={duration:.2f}s\n"
        + (proc.stdout or ""),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run a flaky/race test many times in parallel"
    )
    parser.add_argument(
        "--nodeid", default=DEFAULT_TEST_NODE, help="Pytest node id of the test to run"
    )
    parser.add_argument("--runs", type=int, default=50, help="Total number of runs")
    parser.add_argument("--concurrency", type=int, default=50, help="Max parallel runs")
    parser.add_argument(
        "--no-uv",
        action="store_true",
        help="Run pytest directly instead of via 'uv run'",
    )
    parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        help="Additional args passed to pytest (after --)",
    )
    args = parser.parse_args()

    use_uv = not args.no_uv
    extra_args = args.pytest_args if args.pytest_args else []

    print(
        f"Running {args.nodeid} {args.runs} times with concurrency={args.concurrency} "
        f"(uv={use_uv})"
    )

    failures: list[tuple[int, int, str]] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [
            ex.submit(run_one, i + 1, args.nodeid, use_uv, extra_args)
            for i in range(args.runs)
        ]
        for fut in as_completed(futures):
            idx, rc, output = fut.result()
            status = "PASS" if rc == 0 else "FAIL"
            print(f"[run {idx:02d}] {status}")
            if rc != 0:
                failures.append((idx, rc, output))

    print("\nSummary:")
    print(
        "Total: {}, Passed: {}, Failed: {}".format(
            args.runs, args.runs - len(failures), len(failures)
        )
    )
    if failures:
        print("\n--- Failure outputs (first 3) ---")
        for idx, (_i, _rc, out) in enumerate(failures[:3], 1):
            print(f"\n[Failure {idx}]\n{out}")
        sys.exit(1)

    print("All runs passed ✅")


if __name__ == "__main__":
    main()
