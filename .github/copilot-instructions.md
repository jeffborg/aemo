# Copilot instructions

## Build and test

- Build the static site with `PYTHONPATH=src python3 -m aemo_forecast.cli build --output-dir site`
- Run all tests with `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- Run a single test module with `PYTHONPATH=src python3 -m unittest tests.test_market_notice -v`

## Architecture

- The project is a small Python pipeline that turns public AEMO NEMWeb downloads into a GitHub Pages site.
- `PD7DAY` supplies forecast price data and the gas fuel forecast total.
- `PDPASA` and `STPASA` supply region adequacy data such as demand, capacity, LOR levels, and solar/wind fields.
- Market notices are fetched separately from the `Market_Notice` directory and rendered as a recent-notices feed.
- The generated site is fully static: CSV and JSON exports live under `site/data/`, SVG charts under `site/charts/`, and the main page at `site/index.html`.

## Repository-specific conventions

- Prefer region-level normalized outputs over raw unit-level tables unless the task explicitly needs DUID-level detail.
- Keep AEMO sources separate in the normalized outputs rather than force-merging unlike report families.
- When overlapping adequacy intervals exist, prefer `PDPASA` over `STPASA` for near-term charting.
- Publish only fields directly supported by the parsed AEMO datasets. Do not infer missing fuel-mix splits.
- Preserve market notices as standalone records with their raw reason text intact.

