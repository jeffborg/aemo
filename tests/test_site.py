from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aemo_forecast.pipeline import BuildResult
from aemo_forecast.site import render_demand_page, render_index, render_next_day_page, render_seven_day_page, write_site


class SiteTests(unittest.TestCase):
    def _build(self) -> BuildResult:
        price_rows = []
        adequacy_rows = []
        interconnector_rows = []
        for region in ("NSW1", "QLD1", "SA1", "TAS1", "VIC1"):
            for interval, price, demand, available in (
                ("2026-05-15T00:00:00", 120.0, 9000.0, 11000.0),
                ("2026-05-15T06:00:00", 180.0, 9400.0, 11200.0),
            ):
                price_rows.append(
                    {
                        "region_id": region,
                        "interval_datetime": interval,
                        "horizon": "day_ahead",
                        "rrp": price,
                    }
                )
                adequacy_rows.append(
                    {
                        "dataset": "PDPASA",
                        "region_id": region,
                        "interval_datetime": interval,
                        "run_datetime": "2026-05-15T00:00:00",
                        "horizon": "day_ahead",
                        "demand10_mw": demand - 300.0,
                        "demand50_mw": demand,
                        "demand90_mw": demand + 300.0,
                        "demand_and_nonschedgen_mw": demand + 150.0,
                        "aggregate_capacity_available_mw": available,
                        "calculated_lor1_level_mw": 9600.0,
                        "calculated_lor2_level_mw": 9900.0,
                        "ss_solar_uigf_mw": 1000.0,
                        "ss_wind_uigf_mw": 1400.0,
                        "total_intermittent_generation_mw": 2400.0,
                    }
                )
                interconnector_rows.append(
                    {
                        "region_id": region,
                        "interval_datetime": interval,
                        "horizon": "day_ahead",
                        "net_import_mw": 200.0,
                    }
                )

        return BuildResult(
            dispatch_rows=[
                {
                    "dataset": "DISPATCH",
                    "source_url": "https://example.test/dispatch.zip",
                    "run_datetime": "2026-05-15T11:35:00",
                    "interval_datetime": "2026-05-15T11:35:00",
                    "region_id": region,
                    "rrp": price + 5.0,
                    "total_demand_mw": demand + 100.0,
                    "dispatchable_generation_mw": available + 50.0,
                    "dispatchable_load_mw": 260.0,
                    "net_interchange_mw": 180.0,
                    "excess_generation_mw": 25.0,
                }
                for region, price, demand, available in (
                    ("NSW1", 120.0, 9000.0, 11000.0),
                    ("QLD1", 90.0, 7000.0, 8000.0),
                    ("SA1", 150.0, 1800.0, 2400.0),
                    ("TAS1", 80.0, 1200.0, 1600.0),
                    ("VIC1", 110.0, 6000.0, 7200.0),
                )
            ],
            p5min_rows=[
                {
                    "dataset": "P5MIN",
                    "source_url": "https://example.test/p5.zip",
                    "run_datetime": "2026-05-15T11:30:00",
                    "interval_datetime": "2026-05-15T11:40:00",
                    "region_id": region,
                    "rrp": price + 3.0,
                    "total_demand_mw": demand + 80.0,
                    "dispatchable_generation_mw": available + 40.0,
                    "dispatchable_load_mw": 255.0,
                    "net_interchange_mw": 190.0,
                    "excess_generation_mw": 30.0,
                }
                for region, price, demand, available in (
                    ("NSW1", 120.0, 9000.0, 11000.0),
                    ("QLD1", 90.0, 7000.0, 8000.0),
                    ("SA1", 150.0, 1800.0, 2400.0),
                    ("TAS1", 80.0, 1200.0, 1600.0),
                    ("VIC1", 110.0, 6000.0, 7200.0),
                )
            ],
            predispatch_rows=[
                {
                    "dataset": "PREDISPATCH",
                    "source_url": "https://example.test/predispatch.zip",
                    "run_datetime": "2026-05-15T12:30:00",
                    "interval_datetime": "2026-05-15T13:00:00",
                    "region_id": region,
                    "rrp": price,
                    "total_demand_mw": demand,
                    "dispatchable_generation_mw": available,
                    "dispatchable_load_mw": 250.0,
                    "net_interchange_mw": 200.0,
                    "excess_generation_mw": 50.0,
                }
                for region, price, demand, available in (
                    ("NSW1", 120.0, 9000.0, 11000.0),
                    ("QLD1", 90.0, 7000.0, 8000.0),
                    ("SA1", 150.0, 1800.0, 2400.0),
                    ("TAS1", 80.0, 1200.0, 1600.0),
                    ("VIC1", 110.0, 6000.0, 7200.0),
                )
            ],
            price_rows=price_rows,
            adequacy_rows=adequacy_rows,
            gas_rows=[],
            notices=[
                {
                    "notice_id": "144080",
                    "creation_datetime": "2026-05-14T14:21:55",
                    "notice_type_description": "Reserve Contract / Direction / Instruction",
                    "external_reference": "Cancellation notice",
                    "reason_text": "Refer to Market Notice 144078",
                },
                {
                    "notice_id": "144078",
                    "creation_datetime": "2026-05-14T12:57:15",
                    "notice_type_description": "Reserve Contract / Direction / Instruction",
                    "external_reference": "Direction notice",
                    "reason_text": "Original notice body",
                },
            ],
            interconnector_rows=interconnector_rows,
            charts={
                "nsw1_price.svg": "<svg><text>NSW1 forecast price</text></svg>",
                "nsw1_adequacy.svg": "<svg><text>NSW1 demand and capacity</text></svg>",
                "nsw1_renewables.svg": "<svg><text>NSW1 solar and wind forecast</text></svg>",
            },
            summary={"generated_at": "2026-05-15T00:00:00", "source_counts": {}},
        )

    def test_market_notice_ids_and_references_are_linked(self) -> None:
        build = self._build()

        html = render_index(build)

        self.assertIn("Market overview", html)
        self.assertIn("<strong>Notice ID:</strong> 144080", html)
        self.assertIn("id='notice-144078'", html)
        self.assertIn('href="#notice-144078">Market Notice 144078</a>', html)
        self.assertIn('href="next-day.html"', html)
        self.assertIn("Dispatch overview", html)
        self.assertIn("Dispatchable gen", html)
        self.assertIn("All displayed times use Australia/Sydney.", html)
        self.assertIn("2026-05-15 10:00 AEST", html)
        self.assertIn("2026-05-15 13:00 AEST", html)

    def test_render_next_day_page_contains_region_sections(self) -> None:
        html = render_next_day_page(self._build())

        self.assertIn("Dispatch region summary", html)
        self.assertIn('id="nsw1"', html)
        self.assertIn("NSW1 next-day balance", html)
        self.assertIn("Actual dispatch from NEM day start, with 5-minute predispatch overlaid on the near-term predispatch forecast", html)
        self.assertIn("Actual dispatch", html)
        self.assertIn("5-minute predispatch", html)
        self.assertIn("Predispatch", html)
        self.assertIn("<svg", html)

    def test_render_seven_day_page_contains_week_ahead_section(self) -> None:
        html = render_seven_day_page(self._build())

        self.assertIn("7 day forecast", html)
        self.assertIn("Week-ahead charts", html)
        self.assertIn("NSW1 forecast price", html)

    def test_render_demand_page_contains_nem_chart(self) -> None:
        html = render_demand_page(self._build())

        self.assertIn("Demand overview", html)
        self.assertIn("NEM operational demand", html)
        self.assertIn("Total demand", html)

    def test_write_site_outputs_multiple_pages(self) -> None:
        build = self._build()
        with tempfile.TemporaryDirectory() as tmpdir:
            write_site(Path(tmpdir), build)

            self.assertTrue((Path(tmpdir) / "index.html").exists())
            self.assertTrue((Path(tmpdir) / "next-day.html").exists())
            self.assertTrue((Path(tmpdir) / "seven-day.html").exists())
            self.assertTrue((Path(tmpdir) / "demand.html").exists())
            self.assertTrue((Path(tmpdir) / "data" / "dispatch_actual.csv").exists())
            self.assertTrue((Path(tmpdir) / "data" / "p5min.csv").exists())


if __name__ == "__main__":
    unittest.main()
