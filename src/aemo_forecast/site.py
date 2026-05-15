from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .charts import Band, Series, line_chart
from .pipeline import BuildResult, REGIONS, merge_for_charting, write_csv, write_json


NOTICE_REFERENCE_PATTERN = re.compile(r"\bMarket Notice\s+(\d{5,})\b", re.IGNORECASE)
SOURCE_TIMEZONE = ZoneInfo("Australia/Brisbane")
DISPLAY_TIMEZONE = ZoneInfo("Australia/Sydney")
UTC = ZoneInfo("UTC")


def _parse_timestamp(value: str, source_timezone: ZoneInfo = SOURCE_TIMEZONE) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=source_timezone)
    return parsed


def _display_datetime(value: str, source_timezone: ZoneInfo = SOURCE_TIMEZONE) -> datetime:
    return _parse_timestamp(value, source_timezone).astimezone(DISPLAY_TIMEZONE)


def _format_datetime(value: str, source_timezone: ZoneInfo = SOURCE_TIMEZONE) -> str:
    return _display_datetime(value, source_timezone).strftime("%Y-%m-%d %H:%M %Z")


def _notice_anchor(notice_id: str) -> str:
    return f"notice-{notice_id}"


def _notice_references(text: str) -> list[str]:
    seen: set[str] = set()
    references: list[str] = []
    for match in NOTICE_REFERENCE_PATTERN.finditer(text):
        notice_id = match.group(1)
        if notice_id not in seen:
            seen.add(notice_id)
            references.append(notice_id)
    return references


def _render_notice_body(text: str, known_notice_ids: set[str]) -> str:
    lines: list[str] = []
    for raw_line in text[:800].splitlines():
        parts: list[str] = []
        cursor = 0
        for match in NOTICE_REFERENCE_PATTERN.finditer(raw_line):
            parts.append(escape(raw_line[cursor : match.start()]))
            notice_id = match.group(1)
            label = escape(match.group(0))
            if notice_id in known_notice_ids:
                parts.append(f'<a href="#{_notice_anchor(notice_id)}">{label}</a>')
            else:
                parts.append(label)
            cursor = match.end()
        parts.append(escape(raw_line[cursor:]))
        lines.append("".join(parts))
    return "<br />".join(lines)


def _notices_html(build: BuildResult) -> str:
    selected_notices = build.notices[:50]
    selected_ids = {
        notice_id
        for notice in selected_notices
        if (notice_id := notice.get("notice_id"))
    }
    referenced_ids = {
        reference
        for notice in selected_notices
        for reference in _notice_references(notice.get("reason_text", ""))
    }
    rendered_ids = selected_ids | referenced_ids
    rendered_notices = [
        notice
        for notice in build.notices
        if notice.get("notice_id") in rendered_ids
    ]
    known_notice_ids = {
        notice_id
        for notice in rendered_notices
        if (notice_id := notice.get("notice_id"))
    }
    items = []
    for notice in rendered_notices:
        title = notice.get("external_reference") or notice.get("notice_type_description") or "Market notice"
        created = str(notice.get("creation_datetime", ""))
        notice_id = notice.get("notice_id", "")
        body = _render_notice_body(notice.get("reason_text", ""), known_notice_ids)
        items.append(
            f"<article class='notice' id='{escape(_notice_anchor(notice_id))}'>"
            f"<h4>{escape(title)}</h4>"
            f"<p><strong>Notice ID:</strong> {escape(notice_id)}</p>"
            f"<p><strong>Created:</strong> {escape(_format_datetime(created)) if created else '—'}</p>"
            f"<p><strong>Type:</strong> {escape(notice.get('notice_type_description', ''))}</p>"
            f"<p>{body}</p>"
            "</article>"
        )
    return "\n".join(items)


def _format_power(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "—"
    if abs(value) < 0.5:
        value = 0.0
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:,.0f} MW"


def _format_price(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) < 0.5:
        value = 0.0
    return f"${value:,.0f}/MWh"


def _chart_datetimes(rows: list[dict[str, object]]) -> list[datetime]:
    return [_display_datetime(str(row["interval_datetime"])) for row in rows]


def _sorted_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(rows, key=lambda row: str(row["interval_datetime"]))


def _merged_day_ahead_rows(build: BuildResult) -> list[dict[str, object]]:
    return _sorted_rows(
        [
            row
            for row in merge_for_charting(build.adequacy_rows)
            if row.get("horizon") == "day_ahead"
        ]
    )


def _region_day_ahead_adequacy(build: BuildResult, region: str) -> list[dict[str, object]]:
    return _sorted_rows(
        [row for row in _merged_day_ahead_rows(build) if row["region_id"] == region]
    )


def _region_day_ahead_prices(build: BuildResult, region: str) -> list[dict[str, object]]:
    return _sorted_rows(
        [
            row
            for row in build.price_rows
            if row["region_id"] == region and row.get("horizon") == "day_ahead"
        ]
    )


def _imports_by_region(build: BuildResult) -> dict[str, dict[str, float]]:
    lookup: dict[str, dict[str, float]] = {region: {} for region in REGIONS}
    for row in build.interconnector_rows:
        if row.get("horizon") != "day_ahead":
            continue
        region = str(row["region_id"])
        lookup.setdefault(region, {})[str(row["interval_datetime"])] = float(row["net_import_mw"])
    return lookup


def _region_predispatch_rows(build: BuildResult, region: str) -> list[dict[str, object]]:
    return _sorted_rows(
        [row for row in build.predispatch_rows if row["region_id"] == region]
    )


def _region_dispatch_rows(build: BuildResult, region: str) -> list[dict[str, object]]:
    return _sorted_rows(
        [row for row in build.dispatch_rows if row["region_id"] == region]
    )


def _region_p5min_rows(build: BuildResult, region: str) -> list[dict[str, object]]:
    return _sorted_rows(
        [row for row in build.p5min_rows if row["region_id"] == region]
    )


def _region_next_day_rows(build: BuildResult, region: str) -> list[dict[str, object]]:
    dispatch_rows = _region_dispatch_rows(build, region)
    p5_rows = _region_p5min_rows(build, region)
    predispatch_rows = _region_predispatch_rows(build, region)
    p5_end = max((row["interval_datetime"] for row in p5_rows), default=None)
    combined = list(dispatch_rows)
    combined.extend(p5_rows)
    combined.extend(
        row for row in predispatch_rows if p5_end is None or row["interval_datetime"] > p5_end
    )
    return _sorted_rows(combined)


def _region_next_day_price_rows(build: BuildResult, region: str) -> list[dict[str, object]]:
    return _sorted_rows(
        [
            *_region_dispatch_rows(build, region),
            *_region_p5min_rows(build, region),
            *_region_predispatch_rows(build, region),
        ]
    )


def _series_points(rows: list[dict[str, object]], field: str, dataset: str | None = None) -> list[float | None]:
    points: list[float | None] = []
    for row in rows:
        if dataset is not None and row.get("dataset") != dataset:
            points.append(None)
            continue
        value = row.get(field)
        points.append(float(value) if isinstance(value, (int, float)) else value)  # type: ignore[arg-type]
    return points


def _solar_value(row: dict[str, object]) -> float | None:
    for key in ("ss_solar_cleared_mw", "ss_solar_uigf_mw", "ss_solar_availability_mw"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _wind_value(row: dict[str, object]) -> float | None:
    for key in ("ss_wind_cleared_mw", "ss_wind_uigf_mw", "ss_wind_availability_mw"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _intermittent_value(row: dict[str, object]) -> float | None:
    for key in ("total_intermittent_generation_mw", "uigf_mw"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    solar = _solar_value(row)
    wind = _wind_value(row)
    if solar is None and wind is None:
        return None
    return (solar or 0.0) + (wind or 0.0)


def _sum_optional(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _nem_day_ahead_demand(build: BuildResult) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in _merged_day_ahead_rows(build):
        grouped[str(row["interval_datetime"])].append(row)

    nem_rows: list[dict[str, object]] = []
    for interval_datetime in sorted(grouped):
        interval_rows = grouped[interval_datetime]
        nem_rows.append(
            {
                "interval_datetime": interval_datetime,
                "demand10_mw": _sum_optional([row.get("demand10_mw") for row in interval_rows]),  # type: ignore[arg-type]
                "demand50_mw": _sum_optional([row.get("demand50_mw") for row in interval_rows]),  # type: ignore[arg-type]
                "demand90_mw": _sum_optional([row.get("demand90_mw") for row in interval_rows]),  # type: ignore[arg-type]
                "demand_and_nonschedgen_mw": _sum_optional(
                    [row.get("demand_and_nonschedgen_mw") for row in interval_rows]  # type: ignore[arg-type]
                ),
            }
        )
    return nem_rows


def _nem_predispatch_rows(build: BuildResult) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in build.predispatch_rows:
        grouped[str(row["interval_datetime"])].append(row)

    nem_rows: list[dict[str, object]] = []
    for interval_datetime in sorted(grouped):
        interval_rows = grouped[interval_datetime]
        nem_rows.append(
            {
                "interval_datetime": interval_datetime,
                "total_demand_mw": _sum_optional([row.get("total_demand_mw") for row in interval_rows]),  # type: ignore[arg-type]
                "dispatchable_generation_mw": _sum_optional([row.get("dispatchable_generation_mw") for row in interval_rows]),  # type: ignore[arg-type]
                "dispatchable_load_mw": _sum_optional([row.get("dispatchable_load_mw") for row in interval_rows]),  # type: ignore[arg-type]
                "net_interchange_mw": _sum_optional([row.get("net_interchange_mw") for row in interval_rows]),  # type: ignore[arg-type]
            }
        )
    return nem_rows


def _nem_next_day_rows(build: BuildResult) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for region in REGIONS:
        for row in _region_next_day_rows(build, region):
            grouped[str(row["interval_datetime"])].append(row)

    nem_rows: list[dict[str, object]] = []
    for interval_datetime in sorted(grouped):
        interval_rows = grouped[interval_datetime]
        nem_rows.append(
            {
                "interval_datetime": interval_datetime,
                "total_demand_mw": _sum_optional([row.get("total_demand_mw") for row in interval_rows]),  # type: ignore[arg-type]
                "dispatchable_generation_mw": _sum_optional([row.get("dispatchable_generation_mw") for row in interval_rows]),  # type: ignore[arg-type]
                "dispatchable_load_mw": _sum_optional([row.get("dispatchable_load_mw") for row in interval_rows]),  # type: ignore[arg-type]
                "net_interchange_mw": _sum_optional([row.get("net_interchange_mw") for row in interval_rows]),  # type: ignore[arg-type]
                "rrp": _sum_optional([row.get("rrp") for row in interval_rows]),  # type: ignore[arg-type]
            }
        )
    return nem_rows


def _sparkline_svg(lines: list[tuple[list[float | None], str]]) -> str:
    values = [point for points, _ in lines for point in points if point is not None]
    if len(values) < 2:
        return '<div class="chart-missing small">No sparkline available</div>'

    width = 220
    height = 72
    left = 4
    top = 4
    plot_width = width - 8
    plot_height = height - 8
    minimum = min(values)
    maximum = max(values)
    if minimum == maximum:
        minimum -= 1.0
        maximum += 1.0

    def x_pos(index: int, count: int) -> float:
        return left + (plot_width * index / max(1, count - 1))

    def y_pos(value: float) -> float:
        return top + plot_height - ((value - minimum) / (maximum - minimum) * plot_height)

    polylines: list[str] = []
    for points, color in lines:
        current: list[str] = []
        for idx, point in enumerate(points):
            if point is None:
                if len(current) >= 2:
                    polylines.append(
                        f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(current)}" />'
                    )
                current = []
                continue
            current.append(f"{x_pos(idx, len(points)):.1f},{y_pos(point):.1f}")
        if len(current) >= 2:
            polylines.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(current)}" />'
            )

    return (
        f'<svg class="sparkline" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" rx="10" ry="10" fill="#f8fafc" />'
        + "".join(polylines)
        + "</svg>"
    )


def _chart_figure(svg_markup: str, caption: str) -> str:
    return "<figure>" + svg_markup + f"<figcaption>{escape(caption)}</figcaption></figure>"


def _week_ahead_sections(build: BuildResult) -> str:
    sections = []
    for region in REGIONS:
        slug = region.lower()
        region_charts = [
            ("Forecast price", build.charts.get(f"{slug}_price.svg")),
            (
                "Balance view with capacity, import support, demand band, LOR1, and LOR2",
                build.charts.get(f"{slug}_adequacy.svg"),
            ),
            (
                "Stacked solar and wind with intermittent generation and demand",
                build.charts.get(f"{slug}_renewables.svg"),
            ),
        ]
        available_charts = [(caption, svg) for caption, svg in region_charts if svg is not None]
        if not available_charts:
            continue
        sections.append(
            f"""
            <section id="week-ahead-{slug}">
              <h3>{region}</h3>
              <div class="chart-stack">
                {''.join(_chart_figure(svg, caption) for caption, svg in available_charts)}
              </div>
            </section>
            """
        )
    if not sections:
        return ""
    return '<section><h2>Week-ahead charts</h2><p class="muted">Full 7 day regional charts remain available here.</p></section>' + "".join(sections)


def _page_nav(active_page: str) -> str:
    items = [
        ("overview", "Overview", "index.html"),
        ("next-day", "Next day", "next-day.html"),
        ("seven-day", "7 day", "seven-day.html"),
        ("demand", "Demand", "demand.html"),
    ]
    links = []
    for key, label, href in items:
        active = " active" if key == active_page else ""
        links.append(f'<a class="nav-link{active}" href="{href}">{escape(label)}</a>')
    return '<nav class="app-nav">' + "".join(links) + "</nav>"


def _page_shell(title: str, active_page: str, build: BuildResult, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #e8eef5;
      --panel: #ffffff;
      --border: #dbe4ef;
      --text: #10243b;
      --muted: #5c7085;
      --nav: #183a5b;
      --accent: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }}
    header {{ background: linear-gradient(180deg, #21486d 0%, var(--nav) 100%); color: white; padding: 1rem 1rem 0.75rem; box-shadow: 0 2px 8px rgba(16,36,59,0.18); }}
    header h1 {{ margin: 0 0 0.75rem; font-size: 1.3rem; font-weight: 600; text-align: center; }}
    .app-nav {{ display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap; padding-bottom: 0.25rem; }}
    .nav-link {{ color: rgba(255,255,255,0.84); text-decoration: none; padding: 0.45rem 0.85rem; border-radius: 999px; border: 1px solid rgba(255,255,255,0.16); }}
    .nav-link.active {{ background: rgba(255,255,255,0.18); color: white; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 1rem 1rem 3rem; }}
    section {{ background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 1rem 1.1rem; margin-top: 1rem; box-shadow: 0 1px 4px rgba(16,36,59,0.06); }}
    h2, h3 {{ margin: 0 0 0.75rem; }}
    p {{ margin: 0.35rem 0; }}
    .muted {{ color: var(--muted); }}
    .small {{ font-size: 0.9rem; }}
    .hero {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0.75rem; align-items: center; }}
    .hero-links, .region-links {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
    .hero-links a, .region-links a {{ text-decoration: none; color: var(--accent); background: #eff6ff; border: 1px solid #bfdbfe; padding: 0.4rem 0.7rem; border-radius: 999px; font-size: 0.95rem; }}
    .overview-grid, .mini-card-grid, .demand-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }}
    .overview-card, .mini-card {{ background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%); border: 1px solid var(--border); border-radius: 14px; padding: 0.9rem; }}
    .overview-card h3, .mini-card h3 {{ margin-bottom: 0.35rem; }}
    .card-header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.55rem 0.8rem; margin: 0.85rem 0 0; }}
    .metric-grid dt {{ font-size: 0.82rem; color: var(--muted); }}
    .metric-grid dd {{ margin: 0.2rem 0 0; font-size: 0.96rem; font-weight: 600; }}
    .sparkline {{ display: block; width: 100%; height: auto; margin-top: 0.65rem; }}
    .chart-stack {{ display: flex; flex-direction: column; gap: 1rem; }}
    figure {{ margin: 0; }}
    figure svg {{ display: block; width: 100%; height: auto; border: 1px solid var(--border); border-radius: 10px; background: white; }}
    figcaption {{ margin-top: 0.45rem; font-size: 0.94rem; color: var(--muted); }}
    .chart-missing {{ padding: 2rem; border: 1px dashed #cbd5e1; border-radius: 8px; color: #64748b; background: #fff; }}
    .chart-missing.small {{ padding: 1rem; }}
    .notice {{ border-top: 1px solid var(--border); padding-top: 1rem; margin-top: 1rem; }}
    .notice:first-child {{ border-top: 0; padding-top: 0; margin-top: 0; }}
    .data-links a {{ margin-right: 0.9rem; color: var(--accent); }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    {_page_nav(active_page)}
  </header>
  <main>
    <section>
      <div class="hero">
        <div>
        <p><strong>Generated:</strong> {escape(_format_datetime(str(build.summary["generated_at"]), UTC))}</p>
        <p class="muted small">All displayed times use Australia/Sydney.</p>
        <p class="muted small">Static AEMO forecast pages built from predispatch, PASA, PD7DAY, and market notices.</p>
      </div>
        <div class="hero-links">
          <a href="index.html">Overview</a>
          <a href="next-day.html">Next day</a>
          <a href="seven-day.html">7 day</a>
          <a href="demand.html">Demand</a>
        </div>
      </div>
      <p class="data-links small">
        <a href="data/dispatch_actual.csv">dispatch_actual.csv</a>
        <a href="data/p5min.csv">p5min.csv</a>
        <a href="data/predispatch.csv">predispatch.csv</a>
        <a href="data/prices.csv">prices.csv</a>
        <a href="data/interconnector_imports.csv">interconnector_imports.csv</a>
        <a href="data/adequacy.csv">adequacy.csv</a>
        <a href="data/market_notices.json">market_notices.json</a>
      </p>
    </section>
    {body}
  </main>
</body>
</html>
"""


def _overview_cards(build: BuildResult) -> str:
    cards = []
    for region in REGIONS:
        predispatch_rows = _region_predispatch_rows(build, region)
        snapshot = predispatch_rows[0] if predispatch_rows else None
        interval = _format_datetime(str(snapshot["interval_datetime"])) if snapshot else "No interval"
        generation = float(snapshot["dispatchable_generation_mw"]) if snapshot and snapshot.get("dispatchable_generation_mw") is not None else None
        demand = float(snapshot["total_demand_mw"]) if snapshot and snapshot.get("total_demand_mw") is not None else None
        interchange = float(snapshot["net_interchange_mw"]) if snapshot and snapshot.get("net_interchange_mw") is not None else None
        import_support = None if generation is None or interchange is None else generation + max(interchange, 0.0)
        margin = None if import_support is None or demand is None else import_support - demand
        sparkline = _sparkline_svg(
            [
                ([row.get("total_demand_mw") for row in predispatch_rows], "#dc2626"),  # type: ignore[list-item]
                (
                    [
                        None if row.get("dispatchable_generation_mw") is None or row.get("net_interchange_mw") is None
                        else float(row["dispatchable_generation_mw"]) + max(float(row["net_interchange_mw"]), 0.0)
                        for row in predispatch_rows
                    ],
                    "#2563eb",
                ),
            ]
        )
        cards.append(
            f"""
            <article class="overview-card">
              <div class="card-header">
                <h3>{region}</h3>
                <a href="next-day.html#{region.lower()}">Open</a>
              </div>
              <p class="muted small">{escape(interval)}</p>
              {sparkline}
              <dl class="metric-grid">
                <div><dt>Price</dt><dd>{_format_price(snapshot.get("rrp") if snapshot else None)}</dd></div>
                <div><dt>Total demand</dt><dd>{_format_power(demand)}</dd></div>
                <div><dt>Avail + imports</dt><dd>{_format_power(import_support)}</dd></div>
                <div><dt>Headroom</dt><dd>{_format_power(margin, signed=True)}</dd></div>
                <div><dt>Dispatchable gen</dt><dd>{_format_power(generation)}</dd></div>
                <div><dt>Net interchange</dt><dd>{_format_power(interchange, signed=True)}</dd></div>
              </dl>
            </article>
            """
        )
    return '<section><h2>Dispatch overview</h2><div class="overview-grid">' + "".join(cards) + "</div></section>"


def _price_outlook_cards(build: BuildResult) -> str:
    cards = []
    for region in REGIONS:
        predispatch_rows = _region_predispatch_rows(build, region)
        if predispatch_rows:
            now_price = predispatch_rows[0].get("rrp")
            high_price = max(
                (row.get("rrp") for row in predispatch_rows if row.get("rrp") is not None),
                default=None,
            )
        else:
            now_price = None
            high_price = None
        cards.append(
            f"""
            <article class="mini-card">
              <h3>{region}</h3>
              <p><strong>Predispatch now:</strong> {_format_price(now_price if isinstance(now_price, float) else None)}</p>
              <p class="muted"><strong>Window high:</strong> {_format_price(high_price if isinstance(high_price, float) else None)}</p>
            </article>
            """
        )
    return '<section><h2>Outlook</h2><div class="mini-card-grid">' + "".join(cards) + "</div></section>"


def render_index(build: BuildResult) -> str:
    body = (
        _overview_cards(build)
        + _price_outlook_cards(build)
        + f'<section><h2>Recent market notices</h2>{_notices_html(build)}</section>'
    )
    return _page_shell("Market overview", "overview", build, body)


def _predispatch_balance_chart(region: str, rows: list[dict[str, object]]) -> str:
    dispatchable_generation = [row.get("dispatchable_generation_mw") for row in rows]
    import_support = []
    import_support_top = []
    for row, generation in zip(rows, dispatchable_generation):
        lower = float(generation) if generation is not None else None
        positive_import = max(float(row.get("net_interchange_mw", 0.0) or 0.0), 0.0)
        import_support.append(lower)
        import_support_top.append(None if lower is None else lower + positive_import)
    return line_chart(
        title=f"{region} next-day balance",
        x_values=_chart_datetimes(rows),
        bands=[
            Band(
                "Dispatchable generation",
                "#a855f7",
                [0.0 if value is not None else None for value in dispatchable_generation],  # type: ignore[list-item]
                dispatchable_generation,  # type: ignore[arg-type]
                opacity=0.24,
            ),
            Band(
                "Import support",
                "#06b6d4",
                import_support,  # type: ignore[arg-type]
                import_support_top,  # type: ignore[arg-type]
                opacity=0.30,
            ),
        ],
        series_list=[
            Series("Total demand", "#dc2626", [row.get("total_demand_mw") for row in rows]),  # type: ignore[list-item]
            Series("Dispatchable load", "#0f766e", [row.get("dispatchable_load_mw") for row in rows]),  # type: ignore[list-item]
            Series("Excess generation", "#d97706", [row.get("excess_generation_mw") for row in rows]),  # type: ignore[list-item]
        ],
    )


def _predispatch_price_chart(region: str, rows: list[dict[str, object]]) -> str:
    return line_chart(
        title=f"{region} next-day price timeline",
        x_values=_chart_datetimes(rows),
        series_list=[
            Series("Actual dispatch", "#111827", _series_points(rows, "rrp", "DISPATCH")),
            Series("5-minute predispatch", "#0ea5e9", _series_points(rows, "rrp", "P5MIN")),
            Series("Predispatch", "#2563eb", _series_points(rows, "rrp", "PREDISPATCH")),
        ],
        y_max=3000.0,
        annotate_clipped_max=True,
    )


def _predispatch_detail_chart(region: str, rows: list[dict[str, object]]) -> str:
    solar_points = [_solar_value(row) for row in rows]
    wind_points = [_wind_value(row) for row in rows]
    return line_chart(
        title=f"{region} next-day generation detail",
        x_values=_chart_datetimes(rows),
        bands=[
            Band(
                "Solar",
                "#f59e0b",
                [0.0 if value is not None else None for value in solar_points],
                solar_points,
                opacity=0.28,
            ),
            Band(
                "Wind",
                "#0ea5e9",
                [
                    None if solar is None and wind is None else (solar or 0.0)
                    for solar, wind in zip(solar_points, wind_points)
                ],
                [
                    None if solar is None and wind is None else (solar or 0.0) + (wind or 0.0)
                    for solar, wind in zip(solar_points, wind_points)
                ],
                opacity=0.28,
            ),
        ],
        series_list=[
            Series("Intermittent generation", "#10b981", [_intermittent_value(row) for row in rows]),
            Series("Dispatchable generation", "#a855f7", [row.get("dispatchable_generation_mw") for row in rows]),  # type: ignore[list-item]
            Series("Available generation", "#2563eb", [row.get("available_generation_mw") for row in rows]),  # type: ignore[list-item]
            Series("Net interchange", "#0891b2", [row.get("net_interchange_mw") for row in rows]),  # type: ignore[list-item]
            Series("Total demand", "#dc2626", [row.get("total_demand_mw") for row in rows]),  # type: ignore[list-item]
        ],
    )


def render_next_day_page(build: BuildResult) -> str:
    region_links = "".join(
        f'<a href="#{region.lower()}">{region}</a>' for region in REGIONS
    )
    sections = [
        '<section><h2>Select region</h2><div class="region-links">' + region_links + "</div></section>"
    ]
    for region in REGIONS:
        rows = _region_next_day_rows(build, region)
        price_rows = _region_next_day_price_rows(build, region)
        snapshot = rows[0] if rows else None
        support = (
            None
            if snapshot is None or snapshot.get("dispatchable_generation_mw") is None or snapshot.get("net_interchange_mw") is None
            else float(snapshot["dispatchable_generation_mw"]) + max(float(snapshot["net_interchange_mw"]), 0.0)
        )
        margin = (
            None if snapshot is None or support is None or snapshot.get("total_demand_mw") is None else support - float(snapshot["total_demand_mw"])
        )
        section_body = (
            _chart_figure(_predispatch_balance_chart(region, rows), "Dispatchable generation, positive imports, demand, dispatchable load, and excess generation")
            + _chart_figure(_predispatch_price_chart(region, price_rows), "Actual dispatch prices to now, with 5-minute predispatch overlaid on the near-term predispatch forecast before the remaining predispatch window")
            + _chart_figure(_predispatch_detail_chart(region, rows), "Solar, wind, intermittent, dispatchable, available generation, interchange, and demand over the same mixed timeline")
        )
        sections.append(
            f"""
            <section id="{region.lower()}">
              <div class="hero">
                <div>
                  <h2>{region}</h2>
                  <p class="muted">Actual dispatch from NEM day start, with 5-minute predispatch overlaid on the near-term predispatch forecast before the remaining predispatch window.</p>
                </div>
                <div>
                  <p><strong>Avail + imports:</strong> {_format_power(support)}</p>
                  <p class="muted"><strong>Headroom:</strong> {_format_power(margin, signed=True)}</p>
                </div>
              </div>
              <div class="chart-stack">{section_body}</div>
            </section>
            """
        )
    return _page_shell("Dispatch region summary", "next-day", build, "".join(sections))


def render_seven_day_page(build: BuildResult) -> str:
    body = _week_ahead_sections(build)
    return _page_shell("7 day forecast", "seven-day", build, body)


def _demand_chart(title: str, rows: list[dict[str, object]]) -> str:
    return line_chart(
        title=title,
        x_values=_chart_datetimes(rows),
        bands=[
            Band(
                "Dispatchable generation",
                "#f59e0b",
                [0.0 if row.get("dispatchable_generation_mw") is not None else None for row in rows],  # type: ignore[list-item]
                [row.get("dispatchable_generation_mw") for row in rows],  # type: ignore[list-item]
                opacity=0.18,
            )
        ],
        series_list=[
            Series("Total demand", "#1f2937", [row.get("total_demand_mw") for row in rows]),  # type: ignore[list-item]
            Series(
                "Net interchange",
                "#dc2626",
                [row.get("net_interchange_mw") for row in rows],  # type: ignore[list-item]
            ),
        ],
    )


def render_demand_page(build: BuildResult) -> str:
    links = ['<a href="#nem">NEM</a>'] + [f'<a href="#{region.lower()}">{region}</a>' for region in REGIONS]
    sections = [
        '<section><h2>Demand views</h2><div class="region-links">' + "".join(links) + "</div></section>"
    ]
    nem_rows = _nem_next_day_rows(build)
    sections.append(
        f"""
        <section id="nem">
          <h2>NEM operational demand</h2>
          <p class="muted">Actual dispatch plus overlapping 5-minute predispatch and predispatch across the current next-day window.</p>
          {_chart_figure(_demand_chart("NEM operational demand tracking", nem_rows), "Dispatchable generation area with total demand and net interchange")}
        </section>
        """
    )
    region_charts = []
    for region in REGIONS:
        rows = _region_next_day_rows(build, region)
        region_charts.append(
            f"""
            <article id="{region.lower()}" class="mini-card">
              <h3>{region}</h3>
              {_chart_figure(_demand_chart(f"{region} demand forecast", rows), "Regional mixed actual and forecast demand timeline")}
            </article>
            """
        )
    sections.append('<section><h2>Regional demand</h2><div class="demand-grid">' + "".join(region_charts) + "</div></section>")
    return _page_shell("Demand overview", "demand", build, "".join(sections))


def write_site(output_dir: Path, build: BuildResult) -> None:
    data_dir = output_dir / "data"
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    write_csv(data_dir / "dispatch_actual.csv", build.dispatch_rows)
    write_json(data_dir / "dispatch_actual.json", build.dispatch_rows)
    write_csv(data_dir / "p5min.csv", build.p5min_rows)
    write_json(data_dir / "p5min.json", build.p5min_rows)
    write_csv(data_dir / "predispatch.csv", build.predispatch_rows)
    write_json(data_dir / "predispatch.json", build.predispatch_rows)
    write_csv(data_dir / "prices.csv", build.price_rows)
    write_json(data_dir / "prices.json", build.price_rows)
    write_csv(data_dir / "interconnector_imports.csv", build.interconnector_rows)
    write_json(data_dir / "interconnector_imports.json", build.interconnector_rows)
    write_csv(data_dir / "adequacy.csv", build.adequacy_rows)
    write_json(data_dir / "adequacy.json", build.adequacy_rows)
    write_csv(data_dir / "gas_fuel_forecast.csv", build.gas_rows)
    write_json(data_dir / "gas_fuel_forecast.json", build.gas_rows)
    write_csv(data_dir / "market_notices.csv", build.notices)
    write_json(data_dir / "market_notices.json", build.notices)
    write_json(data_dir / "summary.json", build.summary)

    for filename, svg in build.charts.items():
        (charts_dir / filename).write_text(svg, encoding="utf-8")

    (output_dir / "index.html").write_text(render_index(build), encoding="utf-8")
    (output_dir / "next-day.html").write_text(render_next_day_page(build), encoding="utf-8")
    (output_dir / "seven-day.html").write_text(render_seven_day_page(build), encoding="utf-8")
    (output_dir / "demand.html").write_text(render_demand_page(build), encoding="utf-8")
