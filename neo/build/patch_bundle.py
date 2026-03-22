from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import zipfile


SHOW_SENSITIVE_MEDIA_METHOD = re.compile(
    r"\.method public static showSensitiveMedia\(\)Z\n.*?\.end method",
    re.DOTALL,
)

FORCED_SHOW_SENSITIVE_MEDIA_METHOD = """\
.method public static showSensitiveMedia()Z
    .locals 1

    const/4 v0, 0x1

    return v0
.end method"""

TWEETVIEW_SENSITIVE_MEDIA_METHOD = re.compile(
    r"\.method public static final a\(Lcom/twitter/model/core/e;ZLcom/twitter/tweetview/core/x\$a;\)Z\n.*?\.end method",
    re.DOTALL,
)


def _replace_zip_entry(
    archive_path: Path,
    entry_name: str,
    replacement_bytes: bytes,
    *,
    strip_signature_files: bool = False,
) -> None:
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        rebuilt_archive = temp_dir / archive_path.name

        with zipfile.ZipFile(archive_path) as source_archive:
            if entry_name not in source_archive.namelist():
                raise RuntimeError(f"Could not find {entry_name} in {archive_path.name}")

            with zipfile.ZipFile(rebuilt_archive, "w") as destination_archive:
                for source_info in source_archive.infolist():
                    if strip_signature_files and (
                        source_info.filename.startswith("META-INF/")
                        and source_info.filename.endswith((".MF", ".SF", ".RSA", ".DSA", ".EC"))
                    ):
                        continue

                    if source_info.filename == entry_name:
                        destination_archive.writestr(entry_name, replacement_bytes)
                        continue

                    destination_archive.writestr(
                        source_info,
                        source_archive.read(source_info.filename),
                    )

        shutil.move(rebuilt_archive, archive_path)


def force_show_sensitive_media_in_smali(smali: str) -> str:
    match = SHOW_SENSITIVE_MEDIA_METHOD.search(smali)
    if match is None:
        raise RuntimeError("Could not find Piko Pref.showSensitiveMedia()Z method")

    current_method = match.group(0)
    if current_method == FORCED_SHOW_SENSITIVE_MEDIA_METHOD:
        return smali

    return SHOW_SENSITIVE_MEDIA_METHOD.sub(
        FORCED_SHOW_SENSITIVE_MEDIA_METHOD,
        smali,
        count=1,
    )


def force_show_all_sensitive_tweet_media_in_smali(smali: str) -> str:
    match = TWEETVIEW_SENSITIVE_MEDIA_METHOD.search(smali)
    if match is None:
        raise RuntimeError(
            "Could not find Twitter tweetview sensitive media visibility method"
        )

    current_method = match.group(0)
    locals_match = re.search(r"^    \.locals \d+$", current_method, re.MULTILINE)
    if locals_match is None:
        raise RuntimeError("Could not rewrite Twitter tweetview sensitive media method")

    forced_method = (
        f"{current_method[:locals_match.start()]}"
        "    .locals 1\n\n"
        "    const/4 v0, 0x0\n\n"
        "    return v0\n"
        ".end method"
    )
    if current_method == forced_method:
        return smali

    return f"{smali[:match.start()]}{forced_method}{smali[match.end():]}"


def apply_neo_bundle_customizations(apkeditor_path: Path, patches_path: Path) -> None:
    if not patches_path.exists():
        raise RuntimeError(f"Piko patch bundle not found: {patches_path}")

    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        extracted_dir = temp_dir / "patches"

        with zipfile.ZipFile(patches_path) as archive:
            archive.extractall(extracted_dir)

        twitter_extension_dex = extracted_dir / "extensions" / "twitter.mpe"
        if not twitter_extension_dex.exists():
            raise RuntimeError("Piko twitter extension dex not found in patches.mpp")

        wrapper_apk = temp_dir / "twitter-extension-wrapper.apk"
        with zipfile.ZipFile(wrapper_apk, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(twitter_extension_dex, "classes.dex")

        decoded_dir = temp_dir / "decoded"
        subprocess.run(
            [
                "java",
                "-jar",
                str(apkeditor_path),
                "d",
                "-i",
                str(wrapper_apk),
                "-o",
                str(decoded_dir),
                "-f",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        pref_smali_path = (
            decoded_dir
            / "smali"
            / "classes"
            / "app"
            / "morphe"
            / "extension"
            / "twitter"
            / "Pref.smali"
        )
        if not pref_smali_path.exists():
            raise RuntimeError("Decoded Piko Pref.smali not found while customizing patches")

        original_smali = pref_smali_path.read_text(encoding="utf-8")
        updated_smali = force_show_sensitive_media_in_smali(original_smali)
        if updated_smali == original_smali:
            return

        pref_smali_path.write_text(updated_smali, encoding="utf-8")

        rebuilt_wrapper_apk = temp_dir / "twitter-extension-wrapper-patched.apk"
        subprocess.run(
            [
                "java",
                "-jar",
                str(apkeditor_path),
                "b",
                "-i",
                str(decoded_dir),
                "-o",
                str(rebuilt_wrapper_apk),
                "-f",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        with zipfile.ZipFile(rebuilt_wrapper_apk) as archive:
            with archive.open("classes.dex") as source, twitter_extension_dex.open("wb") as destination:
                shutil.copyfileobj(source, destination)

        rebuilt_bundle = temp_dir / "patches-customized.mpp"
        with zipfile.ZipFile(rebuilt_bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(extracted_dir.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(extracted_dir))

        shutil.move(rebuilt_bundle, patches_path)


def apply_neo_apk_customizations(apkeditor_path: Path, apk_path: Path) -> None:
    if not apk_path.exists():
        raise RuntimeError(f"Merged APK not found: {apk_path}")

    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        source_dex = temp_dir / "classes8.dex"

        with zipfile.ZipFile(apk_path) as archive:
            try:
                with archive.open("classes8.dex") as source, source_dex.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
            except KeyError as exc:
                raise RuntimeError(
                    "Could not find classes8.dex in merged Twitter APK while customizing build"
                ) from exc

        wrapper_apk = temp_dir / "twitter-core-wrapper.apk"
        with zipfile.ZipFile(wrapper_apk, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(source_dex, "classes.dex")

        decoded_dir = temp_dir / "decoded"
        subprocess.run(
            [
                "java",
                "-jar",
                str(apkeditor_path),
                "d",
                "-i",
                str(wrapper_apk),
                "-o",
                str(decoded_dir),
                "-f",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        tweetview_smali_path = (
            decoded_dir
            / "smali"
            / "classes"
            / "com"
            / "twitter"
            / "tweetview"
            / "core"
            / "n.smali"
        )
        if not tweetview_smali_path.exists():
            raise RuntimeError(
                "Decoded Twitter tweetview core n.smali not found while customizing merged APK"
            )

        original_smali = tweetview_smali_path.read_text(encoding="utf-8")
        updated_smali = force_show_all_sensitive_tweet_media_in_smali(original_smali)
        if updated_smali == original_smali:
            return

        tweetview_smali_path.write_text(updated_smali, encoding="utf-8")

        rebuilt_wrapper_apk = temp_dir / "twitter-core-wrapper-patched.apk"
        subprocess.run(
            [
                "java",
                "-jar",
                str(apkeditor_path),
                "b",
                "-i",
                str(decoded_dir),
                "-o",
                str(rebuilt_wrapper_apk),
                "-f",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        with zipfile.ZipFile(rebuilt_wrapper_apk) as archive:
            replacement_classes8 = archive.read("classes.dex")

        _replace_zip_entry(
            apk_path,
            "classes8.dex",
            replacement_classes8,
            strip_signature_files=True,
        )
