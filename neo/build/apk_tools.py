from pathlib import Path
import subprocess

from neo.config import SigningConfig


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
        for include in includes:
            command.append("-e")
            command.append(include)

    if excludes is not None:
        for exclude in excludes:
            command.append("-d")
            command.append(exclude)

    command.append(str(apk))

    subprocess.run(command, check=True)
    sign_apk(apk_signer, target_output, signing)
    return target_output
