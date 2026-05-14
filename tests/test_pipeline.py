from __future__ import annotations

import unittest

from aemo_forecast.pipeline import REGIONS, build_region_charts, horizon_for_interval, merge_for_charting


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

    def test_adequacy_chart_uses_available_capacity(self) -> None:
        price_rows = []
        adequacy_rows = []
        for region in REGIONS:
            for hour, rrp, demand, available in (
                ("2026-05-16T00:00:00", 100.0, 9000.0, 11000.0),
                ("2026-05-16T06:00:00", 120.0, 9400.0, 10800.0),
            ):
                price_rows.append(
                    {
                        "region_id": region,
                        "interval_datetime": hour,
                        "rrp": rrp,
                    }
                )
                adequacy_rows.append(
                    {
                        "dataset": "PDPASA",
                        "region_id": region,
                        "interval_datetime": hour,
                        "run_datetime": "2026-05-15T08:00:00",
                        "demand50_mw": demand,
                        "aggregate_capacity_available_mw": available,
                        "calculated_lor1_level_mw": 9500.0,
                        "calculated_lor2_level_mw": 9800.0,
                        "ss_solar_uigf_mw": 1000.0,
                        "ss_wind_uigf_mw": 1200.0,
                        "total_intermittent_generation_mw": 2200.0,
                    }
                )

        charts = build_region_charts(price_rows, adequacy_rows)

        self.assertIn("Available capacity", charts["nsw1_adequacy.svg"])


if __name__ == "__main__":
    unittest.main()
