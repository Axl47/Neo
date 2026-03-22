from pathlib import Path

from apkmirror import Version
from config import BuildConfig, merged_apk_path
from utils import patch_apk


def build_apks(build_config: BuildConfig, latest_version: Version) -> list[Path]:
    apk = merged_apk_path(build_config, latest_version.version)
    patches = build_config.tool_cache.patches_path
    cli = build_config.tool_cache.morphe_cli_path

    common_includes = [
        "Enable app downgrading",
        "Hide FAB",
        "Disable chirp font",
        "Add ability to copy media link",
        "Hide Banner",
        "Hide promote button",
        "Hide Community Notes",
        "Delete from database",
        "Customize Navigation Bar items",
        "Remove premium upsell",
        "Control video auto scroll",
        "Force enable translate",
    ]

    common_excludes = []

    outputs = [
        build_config.dist_dir / f"x-piko-material-you-v{latest_version.version}.apk",
        build_config.dist_dir / f"x-piko-v{latest_version.version}.apk",
        build_config.dist_dir / f"twitter-piko-material-you-v{latest_version.version}.apk",
        build_config.dist_dir / f"twitter-piko-v{latest_version.version}.apk",
    ]

    patch_apk(
        cli,
        patches,
        apk,
        build_config.tool_cache.uber_apk_signer_path,
        build_config.signing,
        includes=["Dynamic color"] + common_includes,
        excludes=common_excludes,
        out=outputs[0],
    )

    patch_apk(
        cli,
        patches,
        apk,
        build_config.tool_cache.uber_apk_signer_path,
        build_config.signing,
        includes=common_includes,
        excludes=["Dynamic color"] + common_excludes,
        out=outputs[1],
    )

    patch_apk(
        cli,
        patches,
        apk,
        build_config.tool_cache.uber_apk_signer_path,
        build_config.signing,
        includes=["Bring back twitter", "Dynamic color"] + common_includes,
        excludes=common_excludes,
        out=outputs[2],
    )

    patch_apk(
        cli,
        patches,
        apk,
        build_config.tool_cache.uber_apk_signer_path,
        build_config.signing,
        includes=["Bring back twitter"] + common_includes,
        excludes=["Dynamic color"] + common_excludes,
        out=outputs[3],
    )

    return outputs
