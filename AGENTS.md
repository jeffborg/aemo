# AGENTS

## Repository purpose

Build and publish a static GitHub Pages site from public AEMO NEMWeb forecast datasets. The repository is about **republishing AEMO forecast data cleanly**, not training a forecasting model.

## Commands

- Build the site: `PYTHONPATH=src python3 -m aemo_forecast.cli build --output-dir site`
- Run all tests: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- Run one test module: `PYTHONPATH=src python3 -m unittest tests.test_market_notice -v`
- In the dev container, `PYTHONPATH` is preconfigured to `src`, so the same commands also work without the prefix.

## Architecture

- `src/aemo_forecast/nemweb.py` handles NEMWeb directory discovery and downloads.
- `src/aemo_forecast/aemo_csv.py` parses zipped AEMO CSV files with `C/I/D` record sections.
- `src/aemo_forecast/pipeline.py` normalizes `PD7DAY`, `PDPASA`, `STPASA`, and market notices into publishable records.
- `src/aemo_forecast/charts.py` renders SVG charts without external plotting dependencies.
- `src/aemo_forecast/site.py` writes CSV, JSON, SVG, and `index.html`.
- `.github/workflows/publish.yml` builds and deploys the site to GitHub Pages.

## Data conventions

- Keep outputs region-level unless the user explicitly asks for unit-level views.
- Treat `PDPASA` as the day-ahead adequacy source and `STPASA` as the longer-range adequacy source.
- Use `PD7DAY` for forecast prices and the gas fuel forecast field.
- Publish only fields verified in AEMO data. Do not invent fuel-mix breakdowns.
- Keep market notices as a separate time-ordered feed instead of merging them into regional forecast tables.

## Output conventions

- Generated artifacts belong under `site/`.
- Machine-readable data goes in `site/data/`.
- Charts go in `site/charts/`.
- Avoid committing generated outputs unless the user explicitly asks for checked-in site artifacts.

## Environment conventions

- `.devcontainer/devcontainer.json` is the local container entrypoint for future AI-assisted runs.
- The container installs the package with `pip install -e .` during setup and includes GitHub CLI.
