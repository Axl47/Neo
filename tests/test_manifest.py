from pathlib import Path
import unittest

from manifest import build_manifest_payload, render_release_notes


class ManifestTests(unittest.TestCase):
    def test_build_manifest_payload_uses_repo_relative_outputs(self) -> None:
        root_dir = Path("/tmp/repo")
        outputs = [
            root_dir / "dist" / "x-piko-v1.apk",
            root_dir / "dist" / "twitter-piko-v1.apk",
        ]

        payload = build_manifest_payload(
            root_dir=root_dir,
            version="1.0.0-release.0",
            source_url="https://example.com/source",
            outputs=outputs,
            tool_releases={
                "apkeditor": "v1",
                "morphe_cli": "v2",
                "piko_patches": "v3",
                "uber_apk_signer": "v4",
            },
            built_at="2026-03-21T00:00:00+00:00",
        )

        self.assertEqual(payload["version"], "1.0.0-release.0")
        self.assertEqual(payload["source_url"], "https://example.com/source")
        self.assertEqual(
            payload["outputs"],
            ["dist/x-piko-v1.apk", "dist/twitter-piko-v1.apk"],
        )
        self.assertEqual(payload["tool_releases"]["apkeditor"], "v1")
        self.assertEqual(payload["built_at"], "2026-03-21T00:00:00+00:00")

    def test_release_notes_include_tool_release_versions(self) -> None:
        notes = render_release_notes(
            {
                "source_url": "https://example.com/source",
                "tool_releases": {
                    "apkeditor": "apkeditor-v1",
                    "morphe_cli": "morphe-v2",
                    "piko_patches": "patches-v3",
                    "uber_apk_signer": "signer-v4",
                },
            }
        )

        self.assertIn("Source APK: https://example.com/source", notes)
        self.assertIn("- APKEditor: apkeditor-v1", notes)
        self.assertIn("- Morphe CLI: morphe-v2", notes)
        self.assertIn("- Piko patches: patches-v3", notes)
        self.assertIn("- Uber APK Signer: signer-v4", notes)
