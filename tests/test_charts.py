from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from aemo_forecast.charts import Series, line_chart


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


if __name__ == "__main__":
    unittest.main()
