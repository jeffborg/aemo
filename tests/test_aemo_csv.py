from __future__ import annotations

import io
import unittest
import zipfile

from aemo_forecast.aemo_csv import read_aemo_records


def make_zip(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("sample.csv", text)
    return buffer.getvalue()


class AemoCsvTests(unittest.TestCase):
    def test_reads_requested_tables(self) -> None:
        zip_bytes = make_zip(
            "\n".join(
                [
                    "C,NEMP.WORLD,PD7DAY,AEMO,PUBLIC,2026/05/15,07:09:34,1,PD7DAY,1",
                    "I,PD7DAY,PRICESOLUTION,1,RUN_DATETIME,INTERVAL_DATETIME,REGIONID,RRP",
                    'D,PD7DAY,PRICESOLUTION,1,"2026/05/15 07:30:00","2026/05/15 07:30:00",NSW1,98.14',
                    "I,PD7DAY,MARKET_SUMMARY,2,RUN_DATETIME,INTERVAL_DATETIME,GPG_FUEL_FORECAST_TJ",
                    'D,PD7DAY,MARKET_SUMMARY,2,"2026/05/15 07:30:00","2026/05/16 00:00:00",50.66',
                ]
            )
        )

        result = read_aemo_records(zip_bytes, {("PD7DAY", "PRICESOLUTION")})

        self.assertEqual(1, len(result[("PD7DAY", "PRICESOLUTION")]))
        self.assertNotIn(("PD7DAY", "MARKET_SUMMARY"), result)


if __name__ == "__main__":
    unittest.main()

