from __future__ import annotations

import unittest

from aemo_forecast.pipeline import (
    REGIONS,
    build_region_charts,
    filter_predispatch_rows,
    horizon_for_interval,
    merge_for_charting,
    normalize_interconnector_imports,
    normalize_predispatch_regions,
    predispatch_window_end,
)


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
        import_rows = []
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
                        "demand10_mw": demand - 300.0,
                        "demand50_mw": demand,
                        "demand90_mw": demand + 300.0,
                        "aggregate_capacity_available_mw": available,
                        "calculated_lor1_level_mw": 9500.0,
                        "calculated_lor2_level_mw": 9800.0,
                        "ss_solar_uigf_mw": 1000.0,
                        "ss_wind_uigf_mw": 1200.0,
                        "total_intermittent_generation_mw": 2200.0,
                    }
                )
        import_rows.extend(
            [
                {
                    "region_id": "NSW1",
                    "interval_datetime": "2026-05-16T00:00:00",
                    "net_import_mw": 150.0,
                },
                {
                    "region_id": "NSW1",
                    "interval_datetime": "2026-05-16T06:00:00",
                    "net_import_mw": -50.0,
                },
            ]
        )

        charts = build_region_charts(price_rows, adequacy_rows, import_rows)

        self.assertIn("Demand P10-P90", charts["nsw1_adequacy.svg"])
        self.assertIn("Available capacity", charts["nsw1_adequacy.svg"])
        self.assertIn("Import support", charts["nsw1_adequacy.svg"])
        self.assertIn('fill="#a855f7"', charts["nsw1_adequacy.svg"])
        self.assertIn("Solar UIGF", charts["nsw1_renewables.svg"])
        self.assertIn("Wind UIGF", charts["nsw1_renewables.svg"])
        self.assertIn("Demand P50", charts["nsw1_renewables.svg"])
        self.assertIn('fill="#f59e0b"', charts["nsw1_renewables.svg"])

    def test_normalize_interconnector_imports_rolls_up_to_regions(self) -> None:
        normalized = normalize_interconnector_imports(
            [
                {
                    "RUN_DATETIME": "2026/05/15 07:30:00",
                    "INTERVAL_DATETIME": "2026/05/15 07:30:00",
                    "INTERCONNECTORID": "NSW1-QLD1",
                    "MWFLOW": "100",
                },
                {
                    "RUN_DATETIME": "2026/05/15 07:30:00",
                    "INTERVAL_DATETIME": "2026/05/15 07:30:00",
                    "INTERCONNECTORID": "V-SA",
                    "MWFLOW": "-50",
                },
            ],
            "https://example.com/pd7day.zip",
        )

        by_region = {row["region_id"]: row["net_import_mw"] for row in normalized}
        self.assertEqual(-100.0, by_region["NSW1"])
        self.assertEqual(100.0, by_region["QLD1"])
        self.assertEqual(50.0, by_region["VIC1"])
        self.assertEqual(-50.0, by_region["SA1"])

    def test_normalize_predispatch_regions_reads_pdregion_rows(self) -> None:
        normalized = normalize_predispatch_regions(
            [
                {
                    "PREDISPATCHSEQNO": "2026/05/15 11:30:00",
                    "REGIONID": "NSW1",
                    "PERIODID": "2026/05/15 12:00:00",
                    "RRP": "85.2",
                    "TOTALDEMAND": "7000",
                    "DISPATCHABLEGENERATION": "7600",
                    "DISPATCHABLELOAD": "300",
                    "NETINTERCHANGE": "150",
                    "EXCESSGENERATION": "0",
                }
            ],
            "https://example.com/predispatch.zip",
        )

        self.assertEqual("PREDISPATCH", normalized[0]["dataset"])
        self.assertEqual("2026-05-15T11:30:00", normalized[0]["run_datetime"])
        self.assertEqual("2026-05-15T12:00:00", normalized[0]["interval_datetime"])
        self.assertEqual(7000.0, normalized[0]["total_demand_mw"])
        self.assertEqual(150.0, normalized[0]["net_interchange_mw"])

    def test_predispatch_window_end_flips_after_1230(self) -> None:
        self.assertEqual("2026-05-16T04:00:00", predispatch_window_end("2026-05-15T12:00:00"))
        self.assertEqual("2026-05-17T04:00:00", predispatch_window_end("2026-05-15T12:30:00"))

    def test_filter_predispatch_rows_keeps_latest_run_window(self) -> None:
        filtered = filter_predispatch_rows(
            [
                {
                    "run_datetime": "2026-05-15T12:30:00",
                    "interval_datetime": "2026-05-16T04:00:00",
                    "region_id": "NSW1",
                },
                {
                    "run_datetime": "2026-05-15T12:30:00",
                    "interval_datetime": "2026-05-17T04:00:00",
                    "region_id": "NSW1",
                },
                {
                    "run_datetime": "2026-05-15T12:00:00",
                    "interval_datetime": "2026-05-16T04:00:00",
                    "region_id": "NSW1",
                },
            ]
        )

        self.assertEqual(2, len(filtered))
        self.assertTrue(all(row["run_datetime"] == "2026-05-15T12:30:00" for row in filtered))


if __name__ == "__main__":
    unittest.main()
