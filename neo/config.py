from dataclasses import dataclass
from pathlib import Path
import re


ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ToolCacheConfig:
    root_dir: Path
    apkeditor_path: Path
    morphe_cli_path: Path
    patches_path: Path
    uber_apk_signer_path: Path


@dataclass(frozen=True)
class SigningConfig:
    keystore_path: Path
    keystore_password: str
    key_alias: str
    key_password: str


@dataclass(frozen=True)
class BuildConfig:
    root_dir: Path
    cache_dir: Path
    dist_dir: Path
    source_dir: Path
    manifest_path: Path
    tool_cache: ToolCacheConfig
    signing: SigningConfig


@dataclass(frozen=True)
class ReleaseConfig:
    root_dir: Path
    manifest_path: Path
    repo: str | None = None


def default_tool_cache_config(root_dir: Path = ROOT_DIR) -> ToolCacheConfig:
    tool_root = root_dir / ".cache" / "tools"
    return ToolCacheConfig(
        root_dir=tool_root,
        apkeditor_path=tool_root / "apkeditor.jar",
        morphe_cli_path=tool_root / "morphe-cli.jar",
        patches_path=tool_root / "patches.mpp",
        uber_apk_signer_path=tool_root / "uber-apk-signer.jar",
    )


def default_build_config(root_dir: Path = ROOT_DIR) -> BuildConfig:
    cache_dir = root_dir / ".cache"
    source_dir = cache_dir / "source"
    dist_dir = root_dir / "dist"
    signing_dir = cache_dir / "signing"
    return BuildConfig(
        root_dir=root_dir,
        cache_dir=cache_dir,
        dist_dir=dist_dir,
        source_dir=source_dir,
        manifest_path=dist_dir / "manifest.json",
        tool_cache=default_tool_cache_config(root_dir),
        signing=SigningConfig(
            keystore_path=signing_dir / "neo-local.jks",
            keystore_password="neo-local",
            key_alias="neo-local",
            key_password="neo-local",
        ),
    )


def default_release_config(
    root_dir: Path = ROOT_DIR,
    manifest_path: Path | None = None,
    repo: str | None = None,
) -> ReleaseConfig:
    build_config = default_build_config(root_dir)
    return ReleaseConfig(
        root_dir=root_dir,
        manifest_path=manifest_path or build_config.manifest_path,
        repo=repo,
    )


def version_slug(version: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", version)


def source_bundle_path(build_config: BuildConfig, version: str) -> Path:
    return build_config.source_dir / f"x-{version_slug(version)}.apkm"


def merged_apk_path(build_config: BuildConfig, version: str) -> Path:
    bundle_path = source_bundle_path(build_config, version)
    return bundle_path.with_name(f"{bundle_path.stem}_merged.apk")
