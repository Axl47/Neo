from pathlib import Path
import os

from neo.build.manifest import (
    load_manifest,
    render_release_notes,
    resolve_manifest_outputs,
)
from neo.config import ReleaseConfig, default_release_config
from neo.integrations.github_api import publish_release, resolve_repo_slug


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
