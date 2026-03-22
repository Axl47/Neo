import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import apkmirror
from apkmirror import Variant, Version
from build_variants import build_apks
from config import (
    BuildConfig,
    ReleaseConfig,
    default_build_config,
    default_release_config,
    merged_apk_path,
    source_bundle_path,
)
from download_bins import (
    download_apkeditor,
    download_morphe_cli,
    download_release_asset,
    download_uber_apk_signer,
)
from github_api import GitHubApiError, ReleaseAlreadyExists, publish_release, resolve_repo_slug
from manifest import (
    build_manifest_payload,
    load_manifest,
    render_release_notes,
    resolve_manifest_outputs,
    write_manifest,
)
from utils import ensure_directory, merge_apk


APKMIRROR_TWITTER_URL = "https://www.apkmirror.com/apk/x-corp/twitter/"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Neo APK builder")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build", help="Build patched APKs")
    build_parser.add_argument("--version", help="Build a specific APKMirror version")
    build_parser.add_argument(
        "--source-file",
        default=None,
        help="Local .apk or .apkm file to build from instead of downloading from APKMirror",
    )

    release_parser = subparsers.add_parser("release", help="Publish the built APKs")
    release_parser.add_argument(
        "--manifest",
        default=None,
        help="Manifest path. Defaults to dist/manifest.json",
    )
    release_parser.add_argument("--repo", default=None, help="GitHub repository slug")

    doctor_parser = subparsers.add_parser("doctor", help="Validate the local environment")
    doctor_parser.add_argument(
        "--for",
        dest="doctor_target",
        choices=["build", "release"],
        default="build",
        help="Validation target",
    )

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if not effective_argv:
        effective_argv = ["build"]
    return create_parser().parse_args(effective_argv)


def get_latest_release(versions: list[Version]) -> Version | None:
    for version in versions:
        if "release" in version.version:
            return version
    return None


def version_link(version: str) -> str:
    return f"https://www.apkmirror.com/apk/x-corp/twitter/x-{version.replace('.', '-')}-release"


def resolve_target_version(version: str | None) -> Version:
    if version:
        return Version(link=version_link(version), version=version)

    versions = apkmirror.get_versions(APKMIRROR_TWITTER_URL)
    latest_version = get_latest_release(versions)
    if latest_version is None:
        raise RuntimeError("Could not find the latest release on APKMirror")
    return latest_version


def select_bundle_variant(variants: list[Variant]) -> Variant:
    for variant in variants:
        if variant.is_bundle and variant.architecture == "universal":
            return variant

    bundle_variants = [variant for variant in variants if variant.is_bundle]
    if not bundle_variants:
        raise RuntimeError("Bundle variant not found")

    fallback = next(
        (variant for variant in bundle_variants if variant.architecture == "arm64-v8a"),
        None,
    )
    selected_variant = fallback or bundle_variants[0]
    print(f"Universal bundle not found, falling back to {selected_variant.architecture}")
    return selected_variant


def prepare_build_directories(build_config: BuildConfig) -> None:
    ensure_directory(build_config.cache_dir)
    ensure_directory(build_config.source_dir)
    ensure_directory(build_config.tool_cache.root_dir)
    ensure_directory(build_config.signing.keystore_path.parent)
    ensure_directory(build_config.dist_dir)


def download_tooling(build_config: BuildConfig) -> dict[str, str]:
    apkeditor_release = download_apkeditor(build_config.tool_cache.root_dir)
    morphe_release = download_morphe_cli(
        build_config.tool_cache.root_dir,
        include_prereleases=True,
    )
    signer_release = download_uber_apk_signer(build_config.tool_cache.root_dir)
    patches_release = download_release_asset(
        "crimera/piko",
        r"^patches.*mpp$",
        build_config.tool_cache.root_dir,
        "patches.mpp",
        include_prereleases=True,
    )

    return {
        "apkeditor": apkeditor_release.tag_name,
        "morphe_cli": morphe_release.tag_name,
        "piko_patches": patches_release.tag_name,
        "uber_apk_signer": signer_release.tag_name,
    }


def copy_if_needed(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        print(f"{destination_path.name} already exists; skipping copy")
        return
    shutil.copy2(source_path, destination_path)


def prepare_local_source_file(
    build_config: BuildConfig,
    source_file: Path,
    version: str | None,
) -> tuple[Version, Path]:
    if version is None:
        raise RuntimeError("--version is required when using --source-file")

    if not source_file.exists():
        raise RuntimeError(f"Source file not found: {source_file}")

    suffix = source_file.suffix.lower()
    if suffix not in {".apk", ".apkm"}:
        raise RuntimeError("Only .apk and .apkm files are supported with --source-file")

    target_version = Version(link=source_file.resolve().as_uri(), version=version)
    bundle_path = source_bundle_path(build_config, version)
    merged_path = merged_apk_path(build_config, version)

    if suffix == ".apk":
        copy_if_needed(source_file, merged_path)
        return target_version, merged_path

    copy_if_needed(source_file, bundle_path)
    return target_version, merged_path


def build_command(
    version: str | None = None,
    source_file: str | Path | None = None,
    build_config: BuildConfig | None = None,
) -> Path:
    effective_build_config = build_config or default_build_config()
    prepare_build_directories(effective_build_config)
    source_descriptor: str

    if source_file is not None:
        source_path = Path(source_file).expanduser().resolve()
        target_version, merged_path = prepare_local_source_file(
            effective_build_config,
            source_path,
            version,
        )
        source_descriptor = source_path.as_uri()
    else:
        try:
            target_version = resolve_target_version(version)
            variants = apkmirror.get_variants(target_version)
            download_link = select_bundle_variant(variants)
            bundle_path = source_bundle_path(effective_build_config, target_version.version)
            merged_path = merged_apk_path(effective_build_config, target_version.version)
            apkmirror.download_apk(download_link, bundle_path)
        except Exception as exc:
            raise RuntimeError(
                "APKMirror blocked automated access. Download the source APK/APKM in your "
                "browser and rerun with --source-file /path/to/file --version <version>."
            ) from exc

        if not bundle_path.exists():
            raise RuntimeError("Failed to download the APK bundle")
        source_descriptor = target_version.link

    tool_releases = download_tooling(effective_build_config)

    if not merged_path.exists():
        bundle_path = source_bundle_path(effective_build_config, target_version.version)
        if not bundle_path.exists():
            raise RuntimeError(f"Expected source bundle at {bundle_path}")
        merge_apk(effective_build_config.tool_cache.apkeditor_path, bundle_path)
    else:
        print(f"{merged_path.name} already exists; skipping merge")

    if not merged_path.exists():
        raise RuntimeError(f"Expected merged APK at {merged_path}")

    outputs = build_apks(effective_build_config, target_version)
    manifest = build_manifest_payload(
        root_dir=effective_build_config.root_dir,
        version=target_version.version,
        source_url=source_descriptor,
        outputs=outputs,
        tool_releases=tool_releases,
    )
    write_manifest(effective_build_config.manifest_path, manifest)
    print(f"Wrote manifest to {effective_build_config.manifest_path}")
    return effective_build_config.manifest_path


def build_release_paths(
    release_config: ReleaseConfig,
    manifest: dict[str, object],
) -> list[Path]:
    outputs = resolve_manifest_outputs(release_config.root_dir, manifest)
    missing_outputs = [str(output) for output in outputs if not output.exists()]
    if missing_outputs:
        raise RuntimeError(f"Missing build outputs: {', '.join(missing_outputs)}")
    return outputs


def release_command(
    manifest_path: str | Path | None = None,
    repo: str | None = None,
    release_config: ReleaseConfig | None = None,
) -> str:
    effective_release_config = release_config or default_release_config(
        manifest_path=Path(manifest_path) if manifest_path is not None else None,
        repo=repo,
    )

    if not effective_release_config.manifest_path.exists():
        raise RuntimeError(
            f"Manifest not found at {effective_release_config.manifest_path}. Run build first."
        )

    token = os.environ.get("GITHUB_TOKEN")
    if token is None:
        raise RuntimeError("GITHUB_TOKEN is required for release publishing")

    repo_slug = resolve_repo_slug(effective_release_config.repo)
    manifest = load_manifest(effective_release_config.manifest_path)
    outputs = build_release_paths(effective_release_config, manifest)
    release = publish_release(
        repo_slug,
        token,
        manifest["version"],
        manifest["version"],
        render_release_notes(manifest),
        outputs,
    )
    print(f"Published release: {release.html_url}")
    return release.html_url


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
    prepare_build_directories(build_config)
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        if args.command == "build":
            build_command(version=args.version, source_file=args.source_file)
        elif args.command == "release":
            release_command(manifest_path=args.manifest, repo=args.repo)
        elif args.command == "doctor":
            doctor_command(target=args.doctor_target)
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")
    except ReleaseAlreadyExists as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
