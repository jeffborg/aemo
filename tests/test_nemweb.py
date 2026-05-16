from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from aemo_forecast.nemweb import HTTP_CACHE_DIR_ENV, fetch_bytes


class NemwebTests(unittest.TestCase):
    def test_fetch_bytes_uses_disk_cache_when_enabled(self) -> None:
        response = mock.MagicMock()
        response.read.return_value = b"payload"
        urlopen = mock.MagicMock()
        urlopen.return_value.__enter__.return_value = response
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {HTTP_CACHE_DIR_ENV: tmpdir}, clear=False):
                with mock.patch("aemo_forecast.nemweb.urllib.request.urlopen", urlopen):
                    first = fetch_bytes("https://example.test/archive.zip")
                    second = fetch_bytes("https://example.test/archive.zip")

        self.assertEqual(b"payload", first)
        self.assertEqual(first, second)
        self.assertEqual(1, urlopen.call_count)

    def test_fetch_bytes_without_cache_hits_network_each_time(self) -> None:
        response = mock.MagicMock()
        response.read.return_value = b"payload"
        urlopen = mock.MagicMock()
        urlopen.return_value.__enter__.return_value = response
        with mock.patch.dict(os.environ, {HTTP_CACHE_DIR_ENV: ""}, clear=False):
            with mock.patch("aemo_forecast.nemweb.urllib.request.urlopen", urlopen):
                fetch_bytes("https://example.test/archive.zip")
                fetch_bytes("https://example.test/archive.zip")

        self.assertEqual(2, urlopen.call_count)


if __name__ == "__main__":
    unittest.main()
