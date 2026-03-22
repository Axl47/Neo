from pathlib import Path
import os
import re
import shutil
import subprocess
import sys

from neo.build.apk_tools import ensure_directory
from neo.config import default_build_config
from neo.integrations.github_api import GitHubApiError, resolve_repo_slug


def parse_java_major(version_output: str) -> int | None:
    first_line = version_output.splitlines()[0] if version_output else ""
    match = re.search(r"(\d+)", first_line)
    if match is None:
        return None
    return int(match.group(1))


def assert_writable_directory(path: Path) -> None:
    ensure_directory(path)
    probe = path / ".doctor-write-test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()


def doctor_command(target: str = "build") -> None:
    build_config = default_build_config()
    checks: list[str] = []
    errors: list[str] = []

    if sys.version_info < (3, 13):
        errors.append("Python 3.13 or newer is required")
    else:
        checks.append(
            f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )

    uv_path = shutil.which("uv")
    if uv_path is None:
        errors.append("uv is not installed or not on PATH")
    else:
        checks.append(f"uv detected at {uv_path}")

    java_version = subprocess.run(
        ["java", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if java_version.returncode != 0:
        errors.append("Java 17 or newer is required")
    else:
        java_major = parse_java_major(java_version.stdout)
        if java_major is None or java_major < 17:
            errors.append(f"Java 17 or newer is required; found: {java_version.stdout.strip()}")
        else:
            checks.append(java_version.stdout.splitlines()[0])

    for directory in [
        build_config.cache_dir,
        build_config.source_dir,
        build_config.tool_cache.root_dir,
        build_config.dist_dir,
    ]:
        try:
            assert_writable_directory(directory)
            checks.append(f"Writable: {directory}")
        except OSError as exc:
            errors.append(f"{directory} is not writable: {exc}")

    try:
        repo_slug = resolve_repo_slug()
        checks.append(f"Repository slug: {repo_slug}")
    except GitHubApiError as exc:
        errors.append(str(exc))

    if target == "release" and not os.environ.get("GITHUB_TOKEN"):
        errors.append("GITHUB_TOKEN is required for release mode")

    for check in checks:
        print(f"[ok] {check}")

    if errors:
        for error in errors:
            print(f"[error] {error}", file=sys.stderr)
        raise RuntimeError("Doctor checks failed")

    print("Doctor checks passed")
