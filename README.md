# Neo

Neo is a local-first builder for patched Twitter/X APKs using `piko`.

## Requirements

- Java 17+
- `uv`

Optional:

- `nix` if you want to use the provided development shell
- `GITHUB_TOKEN` only when you want to publish a GitHub release

## Quick Start

Install dependencies:

```bash
uv sync --frozen
```

Build the latest release from APKMirror:

```bash
uv run main.py
```

Build a specific version:

```bash
uv run main.py build --version 11.3.0-release.0
```

If APKMirror blocks automated requests with a `403`, download the source `.apk` or `.apkm`
in your browser and build from the local file instead:

```bash
uv run main.py build --version 11.75.1-release.0 --source-file ~/Downloads/x.apkm
```

Run environment checks:

```bash
uv run main.py doctor
uv run main.py doctor --for release
```

## Release Publishing

Publishing is separate from building. The release command reads `dist/manifest.json` and uploads the already-built APKs to GitHub.

```bash
export GITHUB_TOKEN=your_token
uv run main.py release
```

If repository auto-detection is not enough, pass the repo explicitly:

```bash
uv run main.py release --repo owner/repo
```

## Output Layout

- `.cache/source/`: downloaded and merged upstream APK artifacts
- `.cache/tools/`: cached APKEditor, Morphe CLI, and `piko` patch bundles
- `.cache/signing/`: generated local signing keystore for repeat installs on your device
- `dist/`: final APKs and `manifest.json`

The build manifest contains:

- `version`
- `source_url`
- `outputs`
- `tool_releases`
- `built_at`

## Nix

If you use `direnv`, the repo already points at the flake:

```bash
nix develop
uv sync --frozen
uv run main.py build
```

## GitHub Actions

- `.github/workflows/build.yaml` builds APKs and uploads `dist/` as an artifact
- `.github/workflows/release.yaml` builds and publishes a GitHub release using only `GITHUB_TOKEN`

Telegram integration is intentionally not part of this repo anymore.

## Signing

Neo now generates a local signing keystore on first build under `.cache/signing/`.
That keeps repeat local builds installable as updates on the same machine.
