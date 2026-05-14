from __future__ import annotations

import unittest

from aemo_forecast.market_notice import parse_market_notice


SAMPLE_NOTICE = """-------------------------------------------------------------------
                           MARKET NOTICE
-------------------------------------------------------------------

From :              AEMO
To   :              NEMITWEB1
Creation Date :     15/05/2026     01:40:14

-------------------------------------------------------------------

Notice ID               :         144082
Notice Type ID          :         NON-CONFORMANCE
Notice Type Description :         Details of Non-conformance/Conformance
Issue Date              :         15/05/2026
External Reference      :         NON-CONFORMANCE Region NSW1 Friday, 15 May 2026

-------------------------------------------------------------------

Reason :

AEMO ELECTRICITY MARKET NOTICE

NON-CONFORMANCE NSW1 Region Friday, 15 May 2026

Unit:      BW04
Amount:     -28 MW

-------------------------------------------------------------------
END OF REPORT
-------------------------------------------------------------------
"""


class MarketNoticeTests(unittest.TestCase):
    def test_parses_notice_fields(self) -> None:
        result = parse_market_notice(SAMPLE_NOTICE, "https://example.test/notice")

        self.assertEqual("144082", result["notice_id"])
        self.assertEqual("2026-05-15", result["issue_date"])
        self.assertIn("BW04", result["reason_text"])
        self.assertEqual("https://example.test/notice", result["source_url"])


if __name__ == "__main__":
    unittest.main()

