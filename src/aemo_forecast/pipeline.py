from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from .aemo_csv import read_aemo_records
from .charts import Band, Series, line_chart
from .market_notice import parse_market_notice
from .nemweb import fetch_bytes, fetch_text, latest_matching_file, recent_market_notice_files


REGIONS = ("NSW1", "QLD1", "SA1", "TAS1", "VIC1")
SOURCE_PRIORITY = {"PDPASA": 0, "STPASA": 1}
PRICE_KEY = ("PD7DAY", "PRICESOLUTION")
GAS_KEY = ("PD7DAY", "MARKET_SUMMARY")
INTERCONNECTOR_KEY = ("PD7DAY", "INTERCONNECTORSOLUTION")
PDPASA_KEY = ("PDPASA", "REGIONSOLUTION")
STPASA_KEY = ("STPASA", "REGIONSOLUTION")
INTERCONNECTOR_REGIONS = {
    "N-Q-MNSP1": ("NSW1", "QLD1"),
    "NSW1-QLD1": ("NSW1", "QLD1"),
    "T-V-MNSP1": ("TAS1", "VIC1"),
    "V-S-MNSP1": ("VIC1", "SA1"),
    "V-SA": ("VIC1", "SA1"),
    "VIC1-NSW1": ("VIC1", "NSW1"),
}


def parse_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y/%m/%d %H:%M:%S")


def parse_optional_float(value: str) -> float | None:
    if value in {"", None}:
        return None
    return float(value)


def isoformat(value: str) -> str:
    return parse_datetime(value).isoformat()


def horizon_for_interval(run_datetime: str, interval_datetime: str) -> str:
    run_at = parse_datetime(run_datetime)
    interval_at = parse_datetime(interval_datetime)
    return "day_ahead" if interval_at <= run_at + timedelta(hours=24) else "seven_day"


def normalize_prices(rows: list[dict[str, str]], source_url: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        region = row.get("REGIONID")
        if region not in REGIONS:
            continue
        normalized.append(
            {
                "dataset": "PD7DAY",
                "source_url": source_url,
                "run_datetime": isoformat(row["RUN_DATETIME"]),
                "interval_datetime": isoformat(row["INTERVAL_DATETIME"]),
                "region_id": region,
                "horizon": horizon_for_interval(row["RUN_DATETIME"], row["INTERVAL_DATETIME"]),
                "rrp": parse_optional_float(row["RRP"]),
                "lower_1sec_rrp": parse_optional_float(row["LOWER1SECRRP"]),
                "lower_6sec_rrp": parse_optional_float(row["LOWER6SECRRP"]),
                "lower_60sec_rrp": parse_optional_float(row["LOWER60SECRRP"]),
                "lower_5min_rrp": parse_optional_float(row["LOWER5MINRRP"]),
                "lower_reg_rrp": parse_optional_float(row["LOWERREGRRP"]),
                "raise_1sec_rrp": parse_optional_float(row["RAISE1SECRRP"]),
                "raise_6sec_rrp": parse_optional_float(row["RAISE6SECRRP"]),
                "raise_60sec_rrp": parse_optional_float(row["RAISE60SECRRP"]),
                "raise_5min_rrp": parse_optional_float(row["RAISE5MINRRP"]),
                "raise_reg_rrp": parse_optional_float(row["RAISEREGRRP"]),
            }
        )
    return normalized


def normalize_gas(rows: list[dict[str, str]], source_url: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "dataset": "PD7DAY",
                "source_url": source_url,
                "run_datetime": isoformat(row["RUN_DATETIME"]),
                "interval_datetime": isoformat(row["INTERVAL_DATETIME"]),
                "horizon": horizon_for_interval(row["RUN_DATETIME"], row["INTERVAL_DATETIME"]),
                "gpg_fuel_forecast_tj": parse_optional_float(row["GPG_FUEL_FORECAST_TJ"]),
            }
        )
    return normalized


def normalize_interconnector_imports(rows: list[dict[str, str]], source_url: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        regions = INTERCONNECTOR_REGIONS.get(row.get("INTERCONNECTORID", ""))
        flow = parse_optional_float(row.get("MWFLOW"))
        if regions is None or flow is None:
            continue

        run_datetime = isoformat(row["RUN_DATETIME"])
        interval_datetime = isoformat(row["INTERVAL_DATETIME"])
        horizon = horizon_for_interval(row["RUN_DATETIME"], row["INTERVAL_DATETIME"])
        from_region, to_region = regions

        for region_id, delta in ((from_region, -flow), (to_region, flow)):
            key = (region_id, interval_datetime)
            if key not in grouped:
                grouped[key] = {
                    "dataset": "PD7DAY",
                    "source_url": source_url,
                    "run_datetime": run_datetime,
                    "interval_datetime": interval_datetime,
                    "region_id": region_id,
                    "horizon": horizon,
                    "net_import_mw": 0.0,
                }
            grouped[key]["net_import_mw"] += delta

    return [grouped[key] for key in sorted(grouped)]


def normalize_pasa(rows: list[dict[str, str]], dataset: str, source_url: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        region = row.get("REGIONID")
        if region not in REGIONS:
            continue
        normalized.append(
            {
                "dataset": dataset,
                "source_url": source_url,
                "run_datetime": isoformat(row["RUN_DATETIME"]),
                "interval_datetime": isoformat(row["INTERVAL_DATETIME"]),
                "region_id": region,
                "horizon": "day_ahead" if dataset == "PDPASA" else "seven_day",
                "demand10_mw": parse_optional_float(row["DEMAND10"]),
                "demand50_mw": parse_optional_float(row["DEMAND50"]),
                "demand90_mw": parse_optional_float(row["DEMAND90"]),
                "reserve_requirement_mw": parse_optional_float(row["RESERVEREQ"]),
                "capacity_requirement_mw": parse_optional_float(row["CAPACITYREQ"]),
                "energy_requirement_demand50_mw": parse_optional_float(row["ENERGYREQDEMAND50"]),
                "unconstrained_capacity_mw": parse_optional_float(row["UNCONSTRAINEDCAPACITY"]),
                "constrained_capacity_mw": parse_optional_float(row["CONSTRAINEDCAPACITY"]),
                "surplus_capacity_mw": parse_optional_float(row["SURPLUSCAPACITY"]),
                "surplus_reserve_mw": parse_optional_float(row["SURPLUSRESERVE"]),
                "reserve_condition": row["RESERVECONDITION"],
                "lor_condition": row["LORCONDITION"],
                "aggregate_capacity_available_mw": parse_optional_float(row["AGGREGATECAPACITYAVAILABLE"]),
                "aggregate_scheduled_load_mw": parse_optional_float(row["AGGREGATESCHEDULEDLOAD"]),
                "aggregate_pasa_availability_mw": parse_optional_float(row["AGGREGATEPASAAVAILABILITY"]),
                "calculated_lor1_level_mw": parse_optional_float(row["CALCULATEDLOR1LEVEL"]),
                "calculated_lor2_level_mw": parse_optional_float(row["CALCULATEDLOR2LEVEL"]),
                "total_intermittent_generation_mw": parse_optional_float(row["TOTALINTERMITTENTGENERATION"]),
                "demand_and_nonschedgen_mw": parse_optional_float(row["DEMAND_AND_NONSCHEDGEN"]),
                "uigf_mw": parse_optional_float(row["UIGF"]),
                "semi_scheduled_capacity_mw": parse_optional_float(row["SEMISCHEDULEDCAPACITY"]),
                "lor_semi_scheduled_capacity_mw": parse_optional_float(row["LOR_SEMISCHEDULEDCAPACITY"]),
                "lcr_mw": parse_optional_float(row["LCR"]),
                "lcr2_mw": parse_optional_float(row["LCR2"]),
                "fum_mw": parse_optional_float(row["FUM"]),
                "ss_solar_uigf_mw": parse_optional_float(row["SS_SOLAR_UIGF"]),
                "ss_wind_uigf_mw": parse_optional_float(row["SS_WIND_UIGF"]),
                "ss_solar_capacity_mw": parse_optional_float(row["SS_SOLAR_CAPACITY"]),
                "ss_wind_capacity_mw": parse_optional_float(row["SS_WIND_CAPACITY"]),
                "ss_solar_cleared_mw": parse_optional_float(row["SS_SOLAR_CLEARED"]),
                "ss_wind_cleared_mw": parse_optional_float(row["SS_WIND_CLEARED"]),
                "wdr_available_mw": parse_optional_float(row["WDR_AVAILABLE"]),
                "wdr_pasa_available_mw": parse_optional_float(row["WDR_PASAAVAILABLE"]),
                "wdr_capacity_mw": parse_optional_float(row["WDR_CAPACITY"]),
            }
        )
    return normalized


def merge_for_charting(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["region_id"], row["interval_datetime"])].append(row)

    merged: list[dict[str, Any]] = []
    for key in sorted(grouped):
        candidates = grouped[key]
        chosen = sorted(
            candidates,
            key=lambda item: (
                SOURCE_PRIORITY.get(item["dataset"], 99),
                item["run_datetime"],
            ),
        )[0]
        merged.append(chosen)
    return merged


def _chart_datetimes(rows: list[dict[str, Any]]) -> list[datetime]:
    values = []
    for row in rows:
        values.append(datetime.fromisoformat(row["interval_datetime"]))
    return values


def build_region_charts(
    price_rows: list[dict[str, Any]],
    adequacy_rows: list[dict[str, Any]],
    import_rows: list[dict[str, Any]],
) -> dict[str, str]:
    charts: dict[str, str] = {}
    merged_rows = merge_for_charting(adequacy_rows)
    imports_by_region = {
        region: {
            row["interval_datetime"]: row["net_import_mw"]
            for row in import_rows
            if row["region_id"] == region
        }
        for region in REGIONS
    }

    for region in REGIONS:
        region_prices = sorted(
            [row for row in price_rows if row["region_id"] == region],
            key=lambda row: row["interval_datetime"],
        )
        region_adequacy = sorted(
            [row for row in merged_rows if row["region_id"] == region],
            key=lambda row: row["interval_datetime"],
        )
        region_imports = imports_by_region[region]
        available_capacity = [row["aggregate_capacity_available_mw"] for row in region_adequacy]
        import_support = []
        import_support_top = []
        for row, available in zip(region_adequacy, available_capacity):
            net_import = region_imports.get(row["interval_datetime"])
            positive_import = max(net_import, 0.0) if net_import is not None else 0.0
            lower = available if available is not None else None
            import_support.append(lower)
            import_support_top.append(
                None if lower is None else lower + positive_import
            )

        charts[f"{region.lower()}_price.svg"] = line_chart(
            title=f"{region} forecast price",
            x_values=_chart_datetimes(region_prices),
            series_list=[Series("RRP", "#2563eb", [row["rrp"] for row in region_prices])],
            y_max=3000.0,
            annotate_clipped_max=True,
        )
        charts[f"{region.lower()}_adequacy.svg"] = line_chart(
            title=f"{region} demand and capacity",
            x_values=_chart_datetimes(region_adequacy),
            bands=[
                Band(
                    "Available capacity",
                    "#a855f7",
                    [0.0 if value is not None else None for value in available_capacity],
                    available_capacity,
                    opacity=0.24,
                ),
                Band(
                    "Import support",
                    "#06b6d4",
                    import_support,
                    import_support_top,
                    opacity=0.30,
                ),
                Band(
                    "Demand P10-P90",
                    "#dc2626",
                    [row["demand10_mw"] for row in region_adequacy],
                    [row["demand90_mw"] for row in region_adequacy],
                )
            ],
            series_list=[
                Series("Demand P50", "#dc2626", [row["demand50_mw"] for row in region_adequacy]),
                Series("LOR1 level", "#d97706", [row["calculated_lor1_level_mw"] for row in region_adequacy]),
                Series("LOR2 level", "#7c3aed", [row["calculated_lor2_level_mw"] for row in region_adequacy]),
            ],
        )
        charts[f"{region.lower()}_renewables.svg"] = line_chart(
            title=f"{region} solar and wind forecast",
            x_values=_chart_datetimes(region_adequacy),
            bands=[
                Band(
                    "Solar UIGF",
                    "#f59e0b",
                    [0.0 if row["ss_solar_uigf_mw"] is not None else None for row in region_adequacy],
                    [row["ss_solar_uigf_mw"] for row in region_adequacy],
                    opacity=0.32,
                ),
                Band(
                    "Wind UIGF",
                    "#0ea5e9",
                    [row["ss_solar_uigf_mw"] for row in region_adequacy],
                    [
                        None
                        if row["ss_solar_uigf_mw"] is None or row["ss_wind_uigf_mw"] is None
                        else row["ss_solar_uigf_mw"] + row["ss_wind_uigf_mw"]
                        for row in region_adequacy
                    ],
                    opacity=0.32,
                ),
            ],
            series_list=[
                Series("Demand P50", "#dc2626", [row["demand50_mw"] for row in region_adequacy]),
                Series(
                    "Intermittent generation",
                    "#10b981",
                    [row["total_intermittent_generation_mw"] for row in region_adequacy],
                ),
            ],
        )

    return charts


@dataclass
class BuildResult:
    summary: dict[str, Any]
    price_rows: list[dict[str, Any]]
    gas_rows: list[dict[str, Any]]
    interconnector_rows: list[dict[str, Any]]
    adequacy_rows: list[dict[str, Any]]
    notices: list[dict[str, Any]]
    charts: dict[str, str]


def build_dataset_bundle() -> BuildResult:
    pd7day_url = latest_matching_file("PD7Day", "PUBLIC_PD7DAY_")
    pdpasa_url = latest_matching_file("PDPASA", "PUBLIC_PDPASA_")
    stpasa_url = latest_matching_file("Short_Term_PASA_Reports", "PUBLIC_STPASA_")

    pd7day_records = read_aemo_records(fetch_bytes(pd7day_url), [PRICE_KEY, GAS_KEY, INTERCONNECTOR_KEY])
    pdpasa_records = read_aemo_records(fetch_bytes(pdpasa_url), [PDPASA_KEY])
    stpasa_records = read_aemo_records(fetch_bytes(stpasa_url), [STPASA_KEY])

    price_rows = normalize_prices(pd7day_records.get(PRICE_KEY, []), pd7day_url)
    gas_rows = normalize_gas(pd7day_records.get(GAS_KEY, []), pd7day_url)
    interconnector_rows = normalize_interconnector_imports(pd7day_records.get(INTERCONNECTOR_KEY, []), pd7day_url)
    adequacy_rows = normalize_pasa(pdpasa_records.get(PDPASA_KEY, []), "PDPASA", pdpasa_url)
    adequacy_rows.extend(normalize_pasa(stpasa_records.get(STPASA_KEY, []), "STPASA", stpasa_url))

    notice_errors: list[dict[str, str]] = []
    notices: list[dict[str, Any]] = []
    for url in recent_market_notice_files():
        try:
            notices.append(parse_market_notice(fetch_text(url), url))
        except HTTPError as exc:
            notice_errors.append({"source_url": url, "error": f"HTTP {exc.code}"})
    notices = sorted(notices, key=lambda row: row.get("creation_datetime", ""), reverse=True)

    charts = build_region_charts(price_rows, adequacy_rows, interconnector_rows)

    summary = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "sources": {
            "pd7day": pd7day_url,
            "pdpasa": pdpasa_url,
            "stpasa": stpasa_url,
            "market_notice_count": len(notices),
        },
        "counts": {
            "price_rows": len(price_rows),
            "gas_rows": len(gas_rows),
            "interconnector_rows": len(interconnector_rows),
            "adequacy_rows": len(adequacy_rows),
            "market_notices": len(notices),
        },
        "errors": {
            "market_notice_fetch": notice_errors,
        },
    }

    return BuildResult(
        summary=summary,
        price_rows=price_rows,
        gas_rows=gas_rows,
        interconnector_rows=interconnector_rows,
        adequacy_rows=adequacy_rows,
        notices=notices,
        charts=charts,
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
