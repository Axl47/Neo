from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from neo.integrations.http import download


class DownloadCacheTests(unittest.TestCase):
    def test_download_reuses_cached_file_without_network_call(self) -> None:
        with TemporaryDirectory() as temp_dir:
            cached_file = Path(temp_dir) / "cached.jar"
            cached_file.write_text("cached", encoding="utf-8")

            with patch("neo.integrations.http.requests.get") as mock_get:
                download("https://example.com/tool.jar", cached_file)

            mock_get.assert_not_called()
