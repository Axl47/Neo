from pathlib import Path
import shutil

from neo.build.apk_tools import ensure_directory, merge_apk
from neo.build.manifest import build_manifest_payload, write_manifest
from neo.build.patch_bundle import (
    apply_neo_apk_customizations,
    apply_neo_bundle_customizations,
)
from neo.build.variant_builder import build_apks
from neo.config import (
    BuildConfig,
    default_build_config,
    merged_apk_path,
    source_bundle_path,
)
from neo.integrations import apkmirror
from neo.integrations.apkmirror import Variant, Version
from neo.integrations.tool_downloads import (
    download_apkeditor,
    download_morphe_cli,
    download_release_asset,
    download_uber_apk_signer,
)


APKMIRROR_TWITTER_URL = "https://www.apkmirror.com/apk/x-corp/twitter/"


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
    apply_neo_bundle_customizations(
        effective_build_config.tool_cache.apkeditor_path,
        effective_build_config.tool_cache.patches_path,
    )

    if not merged_path.exists():
        bundle_path = source_bundle_path(effective_build_config, target_version.version)
        if not bundle_path.exists():
            raise RuntimeError(f"Expected source bundle at {bundle_path}")
        merge_apk(effective_build_config.tool_cache.apkeditor_path, bundle_path)
    else:
        print(f"{merged_path.name} already exists; skipping merge")

    if not merged_path.exists():
        raise RuntimeError(f"Expected merged APK at {merged_path}")

    apply_neo_apk_customizations(
        effective_build_config.tool_cache.apkeditor_path,
        merged_path,
    )

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
