from __future__ import annotations

import unittest

from aemo_forecast.pipeline import BuildResult
from aemo_forecast.site import render_index


class SiteTests(unittest.TestCase):
    def test_market_notice_ids_and_references_are_linked(self) -> None:
        build = BuildResult(
            price_rows=[],
            adequacy_rows=[],
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
            interconnector_rows=[],
            charts={},
            summary={"generated_at": "2026-05-15T00:00:00", "source_counts": {}},
        )

        html = render_index(build)

        self.assertIn("<strong>Notice ID:</strong> 144080", html)
        self.assertIn("id='notice-144078'", html)
        self.assertIn('href="#notice-144078">Market Notice 144078</a>', html)
        self.assertIn("Chart unavailable", html)

    def test_render_index_inlines_svg_charts(self) -> None:
        build = BuildResult(
            price_rows=[],
            adequacy_rows=[],
            gas_rows=[],
            notices=[],
            interconnector_rows=[],
            charts={
                "nsw1_price.svg": '<svg viewBox="0 0 10 10"><title>hover</title></svg>',
                "nsw1_adequacy.svg": '<svg viewBox="0 0 10 10"></svg>',
                "nsw1_renewables.svg": '<svg viewBox="0 0 10 10"></svg>',
            },
            summary={"generated_at": "2026-05-15T00:00:00", "source_counts": {}},
        )

        html = render_index(build)

        self.assertIn('<svg viewBox="0 0 10 10"><title>hover</title></svg>', html)
        self.assertNotIn('<img src="charts/nsw1_price.svg"', html)


if __name__ == "__main__":
    unittest.main()
