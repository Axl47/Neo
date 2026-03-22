from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def build_manifest_payload(
    root_dir: Path,
    version: str,
    source_url: str,
    outputs: list[Path],
    tool_releases: dict[str, str],
    built_at: str | None = None,
) -> dict[str, Any]:
    return {
        "version": version,
        "source_url": source_url,
        "outputs": [str(output.relative_to(root_dir)) for output in outputs],
        "tool_releases": tool_releases,
        "built_at": built_at or datetime.now(timezone.utc).isoformat(),
    }


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_manifest_outputs(root_dir: Path, payload: dict[str, Any]) -> list[Path]:
    return [root_dir / Path(output) for output in payload["outputs"]]


def render_release_notes(payload: dict[str, Any]) -> str:
    tool_releases = payload["tool_releases"]
    return "\n".join(
        [
            "Built with Neo.",
            "",
            f"Source APK: {payload['source_url']}",
            "",
            "Tool releases:",
            f"- APKEditor: {tool_releases['apkeditor']}",
            f"- Morphe CLI: {tool_releases['morphe_cli']}",
            f"- Piko patches: {tool_releases['piko_patches']}",
            f"- Uber APK Signer: {tool_releases['uber_apk_signer']}",
        ]
    )
