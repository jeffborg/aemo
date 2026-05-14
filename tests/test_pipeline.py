from __future__ import annotations

import unittest

from aemo_forecast.pipeline import horizon_for_interval, merge_for_charting


class PipelineTests(unittest.TestCase):
    def test_horizon_detection(self) -> None:
        self.assertEqual(
            "day_ahead",
            horizon_for_interval("2026/05/15 07:30:00", "2026/05/16 07:30:00"),
        )
        self.assertEqual(
            "seven_day",
            horizon_for_interval("2026/05/15 07:30:00", "2026/05/16 08:00:00"),
        )

    def test_merge_prefers_pdpasa(self) -> None:
        merged = merge_for_charting(
            [
                {"dataset": "STPASA", "region_id": "NSW1", "interval_datetime": "2026-05-16T00:00:00", "run_datetime": "2026-05-15T07:00:00"},
                {"dataset": "PDPASA", "region_id": "NSW1", "interval_datetime": "2026-05-16T00:00:00", "run_datetime": "2026-05-15T08:00:00"},
            ]
        )

        self.assertEqual("PDPASA", merged[0]["dataset"])


if __name__ == "__main__":
    unittest.main()
