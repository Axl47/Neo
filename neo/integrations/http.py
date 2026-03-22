from pathlib import Path

import requests

from neo.constants import SCRAPER_HEADERS

_scraper = None


def get_scraper():
    global _scraper
    if _scraper is None:
        import cloudscraper

        _scraper = cloudscraper.create_scraper()
        _scraper.headers.update(SCRAPER_HEADERS)
    return _scraper


def download(link, out, headers=None, use_scraper=False) -> None:
    output_path = Path(out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"{output_path} already exists; skipping download")
        return

    if use_scraper:
        print(f"Downloading with scraper: {link}")

    session = get_scraper() if use_scraper else requests

    with session.get(link, stream=True, headers=headers, timeout=300) as response:
        response.raise_for_status()
        with output_path.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    output_file.write(chunk)
