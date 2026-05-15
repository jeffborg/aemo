from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from aemo_forecast.charts import Band, Series, line_chart


class ChartTests(unittest.TestCase):
    def test_line_chart_renders_day_sections_and_six_hour_ticks(self) -> None:
        start = datetime(2026, 5, 15, 0, 0)
        x_values = [start + timedelta(hours=6 * idx) for idx in range(8)]

        svg = line_chart(
            title="NSW1 forecast price",
            x_values=x_values,
            series_list=[Series("RRP", "#2563eb", [float(idx) for idx in range(8)])],
        )

        self.assertIn('y="24" font-size="18"', svg)
        self.assertIn(">Fri 15 May</text>", svg)
        self.assertIn(">Sat 16 May</text>", svg)
        self.assertGreaterEqual(svg.count('font-size="10" fill="#4b5563">00</text>'), 2)
        self.assertIn('stroke="#d1d5db"', svg)

    def test_line_chart_renders_band(self) -> None:
        start = datetime(2026, 5, 15, 0, 0)
        x_values = [start + timedelta(hours=6 * idx) for idx in range(3)]

        svg = line_chart(
            title="NSW1 demand and capacity",
            x_values=x_values,
            bands=[Band("Demand P10-P90", "#dc2626", [90.0, 100.0, 110.0], [110.0, 120.0, 130.0])],
            series_list=[Series("Demand P50", "#dc2626", [100.0, 110.0, 120.0])],
        )

        self.assertIn('fill-opacity="0.18"', svg)
        self.assertIn("Demand P10-P90", svg)
        self.assertIn("<polygon ", svg)

    def test_line_chart_rounds_ticks_and_labels_clipped_values(self) -> None:
        start = datetime(2026, 5, 15, 0, 0)
        x_values = [start + timedelta(hours=6 * idx) for idx in range(4)]

        svg = line_chart(
            title="NSW1 forecast price",
            x_values=x_values,
            series_list=[Series("RRP", "#2563eb", [100.0, 1800.0, 4200.0, 2600.0])],
            y_max=3000.0,
            annotate_clipped_max=True,
        )

        self.assertIn(">0</text>", svg)
        self.assertIn(">1000</text>", svg)
        self.assertIn(">2000</text>", svg)
        self.assertIn(">3000</text>", svg)
        self.assertIn(">4200</text>", svg)
        self.assertIn('transform="rotate(-45', svg)

    def test_line_chart_uses_y_max_as_cap_not_forced_ceiling(self) -> None:
        start = datetime(2026, 5, 15, 0, 0)
        x_values = [start + timedelta(hours=6 * idx) for idx in range(4)]

        svg = line_chart(
            title="NSW1 forecast price",
            x_values=x_values,
            series_list=[Series("RRP", "#2563eb", [100.0, 250.0, 420.0, 600.0])],
            y_max=3000.0,
            annotate_clipped_max=True,
        )

        self.assertIn(">0</text>", svg)
        self.assertIn(">200</text>", svg)
        self.assertIn(">400</text>", svg)
        self.assertIn(">600</text>", svg)
        self.assertNotIn(">3000</text>", svg)

    def test_line_chart_allows_smaller_negative_ticks(self) -> None:
        start = datetime(2026, 5, 15, 0, 0)
        x_values = [start + timedelta(hours=6 * idx) for idx in range(3)]

        svg = line_chart(
            title="NSW1 demand and capacity",
            x_values=x_values,
            series_list=[Series("Net imports", "#0f766e", [-400.0, 8000.0, 16000.0])],
        )

        self.assertIn(">-500</text>", svg)
        self.assertIn(">0</text>", svg)
        self.assertIn(">5000</text>", svg)
        self.assertIn(">10000</text>", svg)

    def test_line_chart_renders_hover_tooltips(self) -> None:
        start = datetime(2026, 5, 15, 0, 0)
        x_values = [start + timedelta(hours=6 * idx) for idx in range(2)]

        svg = line_chart(
            title="NSW1 renewables",
            x_values=x_values,
            bands=[Band("Demand P10-P90", "#dc2626", [90.0, 95.0], [110.0, 115.0])],
            series_list=[Series("Demand P50", "#dc2626", [100.0, 105.0])],
        )

        self.assertIn('class="hover-band"', svg)
        self.assertIn("<title>2026-05-15 00:00&#10;Demand P10-P90: 90 to 110&#10;Demand P50: 100</title>", svg)


if __name__ == "__main__":
    unittest.main()
