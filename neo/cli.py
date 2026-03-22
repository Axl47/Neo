import argparse
import sys

from neo.commands.build import build_command
from neo.commands.doctor import doctor_command
from neo.commands.release import release_command
from neo.integrations.github_api import ReleaseAlreadyExists


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Neo APK builder")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build", help="Build patched APKs")
    build_parser.add_argument("--version", help="Build a specific APKMirror version")
    build_parser.add_argument(
        "--source-file",
        default=None,
        help="Local .apk or .apkm file to build from instead of downloading from APKMirror",
    )

    release_parser = subparsers.add_parser("release", help="Publish the built APKs")
    release_parser.add_argument(
        "--manifest",
        default=None,
        help="Manifest path. Defaults to dist/manifest.json",
    )
    release_parser.add_argument("--repo", default=None, help="GitHub repository slug")

    doctor_parser = subparsers.add_parser("doctor", help="Validate the local environment")
    doctor_parser.add_argument(
        "--for",
        dest="doctor_target",
        choices=["build", "release"],
        default="build",
        help="Validation target",
    )

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if not effective_argv:
        effective_argv = ["build"]
    return create_parser().parse_args(effective_argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        if args.command == "build":
            build_command(version=args.version, source_file=args.source_file)
        elif args.command == "release":
            release_command(manifest_path=args.manifest, repo=args.repo)
        elif args.command == "doctor":
            doctor_command(target=args.doctor_target)
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")
    except ReleaseAlreadyExists as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0
