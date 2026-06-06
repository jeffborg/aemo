from __future__ import annotations

import unittest
from subprocess import CalledProcessError
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from aemo_forecast import nemweb


class NemwebTests(unittest.TestCase):
    def test_fetch_bytes_retries_after_403_and_eventually_succeeds(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"ok"
        forbidden = HTTPError("https://example.test/file.zip", 403, "Forbidden", None, None)

        with (
            patch("aemo_forecast.nemweb.urllib.request.urlopen", side_effect=[forbidden, response]) as mock_urlopen,
            patch("aemo_forecast.nemweb.subprocess.run", side_effect=[CalledProcessError(22, ["curl"]), MagicMock(stdout=b"")]) as mock_curl,
            patch("aemo_forecast.nemweb.time.sleep") as mock_sleep,
        ):
            payload = nemweb.fetch_bytes("https://example.test/file.zip")

        self.assertEqual(b"ok", payload)
        self.assertEqual(2, mock_urlopen.call_count)
        self.assertEqual(1, mock_curl.call_count)
        mock_sleep.assert_called_once_with(1)

    def test_fetch_bytes_does_not_retry_non_403_http_errors(self) -> None:
        server_error = HTTPError("https://example.test/file.zip", 500, "Server Error", None, None)

        with (
            patch("aemo_forecast.nemweb.urllib.request.urlopen", side_effect=server_error),
            patch("aemo_forecast.nemweb.subprocess.run") as mock_curl,
        ):
            with self.assertRaises(HTTPError):
                nemweb.fetch_bytes("https://example.test/file.zip")

        mock_curl.assert_not_called()


if __name__ == "__main__":
    unittest.main()
