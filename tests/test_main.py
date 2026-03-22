import unittest

import main


class ParseArgsTests(unittest.TestCase):
    def test_no_args_defaults_to_build(self) -> None:
        args = main.parse_args([])

        self.assertEqual(args.command, "build")
        self.assertIsNone(args.version)

    def test_build_args_include_version(self) -> None:
        args = main.parse_args(["build", "--version", "11.3.0-release.0"])

        self.assertEqual(args.command, "build")
        self.assertEqual(args.version, "11.3.0-release.0")
        self.assertIsNone(args.source_file)

    def test_build_args_accept_local_source_file(self) -> None:
        args = main.parse_args(
            ["build", "--version", "11.3.0-release.0", "--source-file", "/tmp/x.apkm"]
        )

        self.assertEqual(args.command, "build")
        self.assertEqual(args.version, "11.3.0-release.0")
        self.assertEqual(args.source_file, "/tmp/x.apkm")

    def test_release_args_include_manifest_and_repo(self) -> None:
        args = main.parse_args(
            ["release", "--manifest", "dist/manifest.json", "--repo", "owner/repo"]
        )

        self.assertEqual(args.command, "release")
        self.assertEqual(args.manifest, "dist/manifest.json")
        self.assertEqual(args.repo, "owner/repo")

    def test_doctor_args_default_to_build_target(self) -> None:
        args = main.parse_args(["doctor"])

        self.assertEqual(args.command, "doctor")
        self.assertEqual(args.doctor_target, "build")


class JavaVersionTests(unittest.TestCase):
    def test_parse_java_major_from_modern_output(self) -> None:
        self.assertEqual(main.parse_java_major("openjdk 21.0.2 2024-01-16\n"), 21)

    def test_parse_java_major_from_legacy_output(self) -> None:
        self.assertEqual(main.parse_java_major('java version "17.0.10"\n'), 17)
