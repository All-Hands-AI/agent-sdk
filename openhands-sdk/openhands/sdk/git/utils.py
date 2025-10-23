import subprocess
from pathlib import Path


def run(cmd: str, cwd: str | Path) -> str:
    result = subprocess.run(args=cmd, shell=True, cwd=cwd, capture_output=True)
    byte_content = result.stderr or result.stdout or b""

    if result.returncode != 0:
        raise RuntimeError(
            f"error_running_cmd:{cmd}:{result.returncode}:{byte_content.decode()}"
        )
    return byte_content.decode().strip()


def get_valid_ref(repo_dir: str | Path) -> str | None:
    refs = []
    try:
        current_branch = run("git --no-pager rev-parse --abbrev-ref HEAD", repo_dir)
        refs.append(f"origin/{current_branch}")
    except RuntimeError:
        pass

    try:
        default_branch = (
            run('git --no-pager remote show origin | grep "HEAD branch"', repo_dir)
            .split()[-1]
            .strip()
        )
        ref_non_default_branch = (
            '$(git --no-pager merge-base HEAD "$(git --no-pager rev-parse '
            '--abbrev-ref origin/{default_branch})")'
        )
        ref_default_branch = f"origin/{default_branch}"
        refs.append(ref_non_default_branch)
        refs.append(ref_default_branch)
    except RuntimeError:
        pass

    # compares with empty tree
    ref_new_repo = (
        "$(git --no-pager rev-parse --verify 4b825dc642cb6eb9a060e54bf8d69288fbee4904)"
    )
    refs.append(ref_new_repo)

    # Find a ref that exists...
    for ref in refs:
        try:
            result = run(f"git --no-pager rev-parse --verify {ref}", repo_dir)
            return result
        except RuntimeError:
            # invalid ref - try next
            continue

    return None
