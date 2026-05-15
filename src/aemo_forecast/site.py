from __future__ import annotations

from html import escape
from pathlib import Path
import re

from .pipeline import BuildResult, REGIONS, write_csv, write_json


NOTICE_REFERENCE_PATTERN = re.compile(r"\bMarket Notice\s+(\d{5,})\b", re.IGNORECASE)


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
        created = notice.get("creation_datetime", "")
        notice_id = notice.get("notice_id", "")
        body = _render_notice_body(notice.get("reason_text", ""), known_notice_ids)
        items.append(
            f"<article class='notice' id='{escape(_notice_anchor(notice_id))}'>"
            f"<h4>{escape(title)}</h4>"
            f"<p><strong>Notice ID:</strong> {escape(notice_id)}</p>"
            f"<p><strong>Created:</strong> {escape(created)}</p>"
            f"<p><strong>Type:</strong> {escape(notice.get('notice_type_description', ''))}</p>"
            f"<p>{body}</p>"
            "</article>"
        )
    return "\n".join(items)


def _chart_figure(svg_markup: str | None, caption: str) -> str:
    chart = svg_markup if svg_markup is not None else '<div class="chart-missing">Chart unavailable</div>'
    return (
        "<figure>"
        f"{chart}"
        f"<figcaption>{escape(caption)}</figcaption>"
        "</figure>"
    )


def _region_section(build: BuildResult, region: str) -> str:
    slug = region.lower()
    return f"""
    <section class="region-card">
      <h3>{region}</h3>
      <div class="chart-grid">
        {_chart_figure(build.charts.get(f"{slug}_price.svg"), "Forecast price")}
        {_chart_figure(build.charts.get(f"{slug}_adequacy.svg"), "Balance view with capacity, import support, demand band, LOR1, and LOR2")}
        {_chart_figure(build.charts.get(f"{slug}_renewables.svg"), "Stacked solar and wind with intermittent generation and demand")}
      </div>
    </section>
    """


def render_index(build: BuildResult) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AEMO forecast publisher</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f8fafc; color: #111827; }}
    main {{ max-width: 1360px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }}
    h1, h2, h3 {{ margin-bottom: 0.5rem; }}
    .summary {{ background: white; border-radius: 12px; padding: 1rem 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    .links a {{ margin-right: 1rem; }}
    .region-card, .notice-panel {{ background: white; border-radius: 12px; padding: 1rem 1.25rem; margin-top: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    .chart-grid {{ display: flex; flex-direction: column; gap: 1rem; }}
    figure {{ margin: 0; max-width: 1120px; }}
    figure svg {{ display: block; width: 100%; height: auto; border: 1px solid #e5e7eb; border-radius: 8px; background: white; }}
    figcaption {{ margin-top: 0.5rem; color: #4b5563; font-size: 0.95rem; }}
    .chart-missing {{ padding: 2rem; border: 1px dashed #cbd5e1; border-radius: 8px; color: #64748b; background: #fff; }}
    .notice {{ border-top: 1px solid #e5e7eb; padding-top: 1rem; margin-top: 1rem; }}
  </style>
</head>
<body>
  <main>
    <h1>AEMO forecast publisher</h1>
    <section class="summary">
      <p>Latest generated site built from public AEMO NEMWeb forecast datasets.</p>
      <p><strong>Generated:</strong> {escape(build.summary["generated_at"])}</p>
      <p><strong>Sources:</strong> PD7DAY prices, gas, and interconnector flows; PDPASA; STPASA; and the latest day of market notices.</p>
      <p class="links">
        <a href="data/prices.csv">prices.csv</a>
        <a href="data/prices.json">prices.json</a>
        <a href="data/interconnector_imports.csv">interconnector_imports.csv</a>
        <a href="data/interconnector_imports.json">interconnector_imports.json</a>
        <a href="data/adequacy.csv">adequacy.csv</a>
        <a href="data/adequacy.json">adequacy.json</a>
        <a href="data/gas_fuel_forecast.csv">gas_fuel_forecast.csv</a>
        <a href="data/gas_fuel_forecast.json">gas_fuel_forecast.json</a>
        <a href="data/market_notices.csv">market_notices.csv</a>
        <a href="data/market_notices.json">market_notices.json</a>
        <a href="data/summary.json">summary.json</a>
      </p>
    </section>
    <h2>Regional charts</h2>
    {''.join(_region_section(build, region) for region in REGIONS)}
    <section class="notice-panel">
      <h2>Recent market notices</h2>
      {_notices_html(build)}
    </section>
  </main>
</body>
</html>
"""


def write_site(output_dir: Path, build: BuildResult) -> None:
    data_dir = output_dir / "data"
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

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
