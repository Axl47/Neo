import os
import requests
import subprocess
import sys
from pathlib import Path

from config import SigningConfig
from constants import SCRAPER_HEADERS

_scraper = None


def get_scraper():
    global _scraper
    if _scraper is None:
        import cloudscraper

        _scraper = cloudscraper.create_scraper()
        _scraper.headers.update(SCRAPER_HEADERS)
    return _scraper


def panic(message: str):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def download(link, out, headers=None, use_scraper=False):
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"{output_path} already exists; skipping download")
        return

    if use_scraper:
        print(f"Downloading with scraper: {link}")

    session = get_scraper() if use_scraper else requests

    with session.get(link, stream=True, headers=headers, timeout=300) as r:
        r.raise_for_status()
        with output_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def merge_apk(apkeditor_path: Path, path: Path) -> Path:
    subprocess.run(
        [
            "java",
            "-jar",
            str(apkeditor_path),
            "m",
            "-extractNativeLibs",
            "true",
            "-i",
            str(path),
        ],
        check=True,
        cwd=path.parent,
    )
    return path.with_name(f"{path.stem}_merged.apk")


def ensure_signing_keystore(signing: SigningConfig) -> Path:
    if signing.keystore_path.exists():
        return signing.keystore_path

    signing.keystore_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "keytool",
            "-genkeypair",
            "-keystore",
            str(signing.keystore_path),
            "-storetype",
            "JKS",
            "-storepass",
            signing.keystore_password,
            "-alias",
            signing.key_alias,
            "-keypass",
            signing.key_password,
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            "36500",
            "-dname",
            "CN=Neo Local, OU=Neo, O=Neo, L=Local, ST=Local, C=US",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return signing.keystore_path


def sign_apk(apk_signer_path: Path, apk_path: Path, signing: SigningConfig) -> Path:
    ensure_signing_keystore(signing)
    subprocess.run(
        [
            "java",
            "-jar",
            str(apk_signer_path),
            "--apks",
            str(apk_path),
            "--ks",
            str(signing.keystore_path),
            "--ksAlias",
            signing.key_alias,
            "--ksPass",
            signing.keystore_password,
            "--ksKeyPass",
            signing.key_password,
            "--overwrite",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return apk_path


def patch_apk(
    cli: Path,
    patches: Path,
    apk: Path,
    apk_signer: Path,
    signing: SigningConfig,
    includes: list[str] | None = None,
    excludes: list[str] | None = None,
    out: Path | None = None,
) -> Path:
    ensure_signing_keystore(signing)
    target_output = out or apk.with_name(f"{apk.stem}-patched.apk")
    if target_output.exists():
        target_output.unlink()

    command = [
        "java",
        "-jar",
        str(cli),
        "patch",
        "-p",
        str(patches),
        "--unsigned",
        "-o",
        str(target_output),
    ]

    if includes is not None:
        for i in includes:
            command.append("-e")
            command.append(i)

    if excludes is not None:
        for e in excludes:
            command.append("-d")
            command.append(e)

    command.append(str(apk))

    subprocess.run(command, check=True)
    sign_apk(apk_signer, target_output, signing)
    return target_output
