import unittest

from github_api import build_create_release_payload, resolve_repo_slug


class RepoResolutionTests(unittest.TestCase):
    def test_explicit_repo_has_highest_precedence(self) -> None:
        resolved = resolve_repo_slug(
            explicit_repo="owner/explicit",
            env={"GITHUB_REPOSITORY": "owner/env"},
            remote_url="git@github.com:owner/remote.git",
        )

        self.assertEqual(resolved, "owner/explicit")

    def test_environment_repo_beats_remote(self) -> None:
        resolved = resolve_repo_slug(
            env={"GITHUB_REPOSITORY": "owner/env"},
            remote_url="https://github.com/owner/remote.git",
        )

        self.assertEqual(resolved, "owner/env")

    def test_remote_repo_is_used_as_final_fallback(self) -> None:
        resolved = resolve_repo_slug(
            env={},
            remote_url="https://github.com/owner/remote.git",
        )

        self.assertEqual(resolved, "owner/remote")


class ReleasePayloadTests(unittest.TestCase):
    def test_create_release_payload_has_expected_shape(self) -> None:
        payload = build_create_release_payload("v1.2.3", "v1.2.3", "notes")

        self.assertEqual(payload["tag_name"], "v1.2.3")
        self.assertEqual(payload["name"], "v1.2.3")
        self.assertEqual(payload["body"], "notes")
        self.assertFalse(payload["draft"])
        self.assertFalse(payload["prerelease"])
        self.assertEqual(payload["make_latest"], "true")
