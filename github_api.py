from dataclasses import dataclass
from pathlib import Path
import mimetypes
import os
import re
import subprocess
from typing import Any, Mapping
from urllib.parse import urlencode

import requests

from constants import GITHUB_API_BASE_URL


@dataclass(frozen=True)
class Asset:
    browser_download_url: str
    name: str


@dataclass(frozen=True)
class GitHubRelease:
    tag_name: str
    html_url: str
    upload_url: str
    assets: list[Asset]


class GitHubApiError(RuntimeError):
    pass


class ReleaseAlreadyExists(GitHubApiError):
    pass


def github_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_release(payload: Mapping[str, Any]) -> GitHubRelease:
    assets = [
        Asset(
            browser_download_url=asset["browser_download_url"],
            name=asset["name"],
        )
        for asset in payload.get("assets", [])
    ]
    return GitHubRelease(
        tag_name=payload["tag_name"],
        html_url=payload["html_url"],
        upload_url=payload.get("upload_url", "").split("{", 1)[0],
        assets=assets,
    )


def get_release_by_tag(
    repo_url: str,
    tag: str,
    token: str | None = None,
) -> GitHubRelease | None:
    url = f"{GITHUB_API_BASE_URL}/repos/{repo_url}/releases/tags/{tag}"
    response = requests.get(url, headers=github_headers(token), timeout=30)

    if response.status_code == 200:
        return parse_release(response.json())
    if response.status_code == 404:
        return None

    raise GitHubApiError(
        f"GitHub release lookup failed for {repo_url}@{tag}: "
        f"{response.status_code} {response.text}"
    )


def build_create_release_payload(tag: str, title: str, body: str) -> dict[str, Any]:
    return {
        "tag_name": tag,
        "name": title,
        "body": body,
        "draft": False,
        "prerelease": False,
        "make_latest": "true",
    }


def create_release(
    repo_url: str,
    token: str,
    tag: str,
    title: str,
    body: str,
) -> GitHubRelease:
    url = f"{GITHUB_API_BASE_URL}/repos/{repo_url}/releases"
    response = requests.post(
        url,
        headers=github_headers(token),
        json=build_create_release_payload(tag, title, body),
        timeout=30,
    )

    if response.status_code == 201:
        return parse_release(response.json())

    raise GitHubApiError(
        f"Failed to create GitHub release {repo_url}@{tag}: "
        f"{response.status_code} {response.text}"
    )


def upload_release_asset(
    upload_url: str,
    asset_path: Path,
    token: str,
) -> Asset:
    content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
    upload_target = f"{upload_url}?{urlencode({'name': asset_path.name})}"

    with asset_path.open("rb") as asset_file:
        response = requests.post(
            upload_target,
            headers={
                **github_headers(token),
                "Content-Type": content_type,
            },
            data=asset_file,
            timeout=300,
        )

    if response.status_code == 201:
        payload = response.json()
        return Asset(
            browser_download_url=payload["browser_download_url"],
            name=payload["name"],
        )

    raise GitHubApiError(
        f"Failed to upload {asset_path.name}: {response.status_code} {response.text}"
    )


def publish_release(
    repo_url: str,
    token: str,
    tag: str,
    title: str,
    body: str,
    files: list[Path],
) -> GitHubRelease:
    existing_release = get_release_by_tag(repo_url, tag, token=token)
    if existing_release is not None:
        raise ReleaseAlreadyExists(f"Release {repo_url}@{tag} already exists")

    release = create_release(repo_url, token, tag, title, body)
    uploaded_assets = [
        upload_release_asset(release.upload_url, file_path, token) for file_path in files
    ]
    return GitHubRelease(
        tag_name=release.tag_name,
        html_url=release.html_url,
        upload_url=release.upload_url,
        assets=uploaded_assets,
    )


def parse_repo_slug_from_remote(remote_url: str) -> str | None:
    match = re.search(r"github\.com[:/](?P<slug>[^/]+/[^/]+?)(?:\.git)?$", remote_url)
    if match is None:
        return None
    return match.group("slug")


def get_origin_remote_url() -> str | None:
    command = ["git", "config", "--get", "remote.origin.url"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None

    remote_url = result.stdout.strip()
    return remote_url or None


def resolve_repo_slug(
    explicit_repo: str | None = None,
    env: Mapping[str, str] | None = None,
    remote_url: str | None = None,
) -> str:
    if explicit_repo:
        return explicit_repo

    environment = env or os.environ
    github_repository = environment.get("GITHUB_REPOSITORY")
    if github_repository:
        return github_repository

    effective_remote = remote_url if remote_url is not None else get_origin_remote_url()
    if effective_remote:
        parsed_slug = parse_repo_slug_from_remote(effective_remote)
        if parsed_slug is not None:
            return parsed_slug

    raise GitHubApiError(
        "Unable to resolve the GitHub repository slug. "
        "Provide --repo, set GITHUB_REPOSITORY, or configure origin."
    )
