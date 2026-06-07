from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from aemo_forecast import nemweb


class NemwebTests(unittest.TestCase):
    def test_fetch_bytes_retries_after_403_with_5s_backoff(self) -> None:
        forbidden = HTTPError("https://example.test/file.zip", 403, "Forbidden", None, None)
        success = MagicMock()
        success.__enter__ = MagicMock(return_value=success)
        success.__exit__ = MagicMock(return_value=False)
        success.read.return_value = b"ok"

        with (
            patch("aemo_forecast.nemweb.urllib.request.urlopen", side_effect=[forbidden, success]) as mock_urlopen,
            patch("aemo_forecast.nemweb.time.sleep") as mock_sleep,
        ):
            payload = nemweb.fetch_bytes("https://example.test/file.zip")

        self.assertEqual(b"ok", payload)
        self.assertEqual(2, mock_urlopen.call_count)
        mock_sleep.assert_called_once_with(nemweb.FETCH_403_RETRY_DELAY)

    def test_fetch_bytes_does_not_retry_non_403_http_errors(self) -> None:
        server_error = HTTPError("https://example.test/file.zip", 500, "Server Error", None, None)

        with (
            patch("aemo_forecast.nemweb.urllib.request.urlopen", side_effect=server_error),
        ):
            with self.assertRaises(HTTPError):
                nemweb.fetch_bytes("https://example.test/file.zip")

    def test_recent_market_notice_files_returns_empty_on_403(self) -> None:
        forbidden = HTTPError("https://nemweb.com.au/Reports/Current/Market_Notice/", 403, "Forbidden", None, None)

        with patch("aemo_forecast.nemweb.fetch_text", side_effect=forbidden):
            result = nemweb.recent_market_notice_files()

        self.assertEqual([], result)


if __name__ == "__main__":
    unittest.main()
