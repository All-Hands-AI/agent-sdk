import shlex
import subprocess
import sys

from openhands.sdk.logger import get_logger


logger = get_logger(__name__)


def execute_command(
    cmd: list[str] | str,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    timeout: float | None = None,
    print_output: bool = True,
) -> subprocess.CompletedProcess:
    # For string commands, use shell=True to handle shell operators properly
    if isinstance(cmd, str):
        cmd_to_run = cmd
        use_shell = True
        logger.info("$ %s", cmd)
    else:
        cmd_to_run = cmd
        use_shell = False
        logger.info("$ %s", " ".join(shlex.quote(c) for c in cmd))

    proc = subprocess.Popen(
        cmd_to_run,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        shell=use_shell,
    )
    if proc is None:
        raise RuntimeError("Failed to start process")

    # Read line by line, echo to parent stdout/stderr
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    if proc.stdout is None or proc.stderr is None:
        raise RuntimeError("Failed to capture stdout/stderr")

    for line in proc.stdout:
        if print_output:
            sys.stdout.write(line)
        stdout_lines.append(line)
    for line in proc.stderr:
        if print_output:
            sys.stderr.write(line)
        stderr_lines.append(line)

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return subprocess.CompletedProcess(
            cmd_to_run,
            -1,  # Indicate timeout with -1 exit code
            "".join(stdout_lines),
            "".join(stderr_lines),
        )

    return subprocess.CompletedProcess(
        cmd_to_run,
        proc.returncode,
        "".join(stdout_lines),
        "".join(stderr_lines),
    )
