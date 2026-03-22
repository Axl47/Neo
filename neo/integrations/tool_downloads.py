from dataclasses import dataclass
from pathlib import Path
import re

import requests

from neo.constants import GITHUB_API_BASE_URL
from neo.integrations.http import download


@dataclass(frozen=True)
class ResolvedToolRelease:
    tag_name: str
    html_url: str
    asset_name: str
    asset_path: Path


def download_release_asset(
    repo: str,
    regex: str,
    out_dir: str | Path,
    filename: str | None = None,
    include_prereleases: bool = False,
    version: str | None = None,
) -> ResolvedToolRelease:
    url = f"{GITHUB_API_BASE_URL}/repos/{repo}/releases"

    response = requests.get(url, timeout=30)
    if response.status_code != 200:
        raise Exception("Failed to fetch github")

    releases = [r for r in response.json() if include_prereleases or not r["prerelease"]]

    if not releases:
        raise Exception(f"No releases found for {repo}")

    if version is not None:
        releases = [r for r in releases if r["tag_name"] == version]

    if not releases:
        raise Exception(f"No release found for version {version}")

    latest_release = releases[0]

    link = None
    matched_name = None
    for asset in latest_release["assets"]:
        name = asset["name"]
        if re.search(regex, name):
            link = asset["browser_download_url"]
            matched_name = name
            if filename is None:
                filename = name
            break

    if link is None:
        raise Exception(
            f"Failed to find asset matching {regex} on release {latest_release['tag_name']}"
        )

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    asset_path = output_dir / filename
    download(link, asset_path)

    return ResolvedToolRelease(
        tag_name=latest_release["tag_name"],
        html_url=latest_release["html_url"],
        asset_name=matched_name or filename,
        asset_path=asset_path,
    )


def download_apkeditor(out_dir: str | Path) -> ResolvedToolRelease:
    print("Downloading apkeditor")
    return download_release_asset("REAndroid/APKEditor", "APKEditor", out_dir, "apkeditor.jar")


def download_morphe_cli(
    out_dir: str | Path,
    include_prereleases: bool = False,
) -> ResolvedToolRelease:
    print("Downloading morphe cli")
    return download_release_asset(
        "MorpheApp/morphe-cli",
        r"^morphe-cli.*-all\.jar$",
        out_dir,
        "morphe-cli.jar",
        include_prereleases=include_prereleases,
    )


def download_uber_apk_signer(out_dir: str | Path) -> ResolvedToolRelease:
    print("Downloading uber-apk-signer")
    return download_release_asset(
        "patrickfav/uber-apk-signer",
        r"uber-apk-signer.*\.jar$",
        out_dir,
        "uber-apk-signer.jar",
    )
