from __future__ import annotations

from html import escape
from pathlib import Path

from .pipeline import BuildResult, REGIONS, write_csv, write_json


def _notices_html(build: BuildResult) -> str:
    items = []
    for notice in build.notices[:50]:
        title = notice.get("external_reference") or notice.get("notice_type_description") or "Market notice"
        created = notice.get("creation_datetime", "")
        body = escape(notice.get("reason_text", "")[:800]).replace("\n", "<br />")
        items.append(
            "<article class='notice'>"
            f"<h4>{escape(title)}</h4>"
            f"<p><strong>Created:</strong> {escape(created)}</p>"
            f"<p><strong>Type:</strong> {escape(notice.get('notice_type_description', ''))}</p>"
            f"<p>{body}</p>"
            "</article>"
        )
    return "\n".join(items)


def _region_section(region: str) -> str:
    slug = region.lower()
    return f"""
    <section class="region-card">
      <h3>{region}</h3>
      <div class="chart-grid">
        <figure>
          <img src="charts/{slug}_price.svg" alt="{region} forecast price chart" />
          <figcaption>Forecast price</figcaption>
        </figure>
        <figure>
          <img src="charts/{slug}_adequacy.svg" alt="{region} demand and capacity chart" />
          <figcaption>Demand, capacity, LOR1, and LOR2</figcaption>
        </figure>
        <figure>
          <img src="charts/{slug}_renewables.svg" alt="{region} solar and wind chart" />
          <figcaption>Solar, wind, and intermittent generation</figcaption>
        </figure>
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
    main {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }}
    h1, h2, h3 {{ margin-bottom: 0.5rem; }}
    .summary {{ background: white; border-radius: 12px; padding: 1rem 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    .links a {{ margin-right: 1rem; }}
    .region-card, .notice-panel {{ background: white; border-radius: 12px; padding: 1rem 1.25rem; margin-top: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }}
    figure {{ margin: 0; }}
    img {{ width: 100%; height: auto; border: 1px solid #e5e7eb; border-radius: 8px; background: white; }}
    figcaption {{ margin-top: 0.5rem; color: #4b5563; font-size: 0.95rem; }}
    .notice {{ border-top: 1px solid #e5e7eb; padding-top: 1rem; margin-top: 1rem; }}
  </style>
</head>
<body>
  <main>
    <h1>AEMO forecast publisher</h1>
    <section class="summary">
      <p>Latest generated site built from public AEMO NEMWeb forecast datasets.</p>
      <p><strong>Generated:</strong> {escape(build.summary["generated_at"])}</p>
      <p><strong>Sources:</strong> PD7DAY, PDPASA, STPASA, and the latest day of market notices.</p>
      <p class="links">
        <a href="data/prices.csv">prices.csv</a>
        <a href="data/prices.json">prices.json</a>
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
    {''.join(_region_section(region) for region in REGIONS)}
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

