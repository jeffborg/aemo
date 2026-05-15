# AEMO forecast publisher

This project pulls public AEMO NEMWeb forecast datasets, normalizes the latest regional forecast views, renders simple static charts, and publishes the result as a GitHub Pages site.

## What it publishes

- Regional predispatch views from `Predispatch_Reports`
- Regional forecast prices from `PD7DAY`
- Regional adequacy and reserve-style metrics from `PDPASA` and `STPASA`
- Wind and solar region metrics exposed in PASA region solutions
- Gas fuel forecast totals exposed in `PD7DAY`
- The latest day of market notices

The first version intentionally publishes **AEMO-provided forecast data**, not a custom forecasting model.

## Local commands

Create and activate a virtual environment if you want one, then run:

```bash
PYTHONPATH=src python3 -m aemo_forecast.cli build --output-dir site
```

Run the tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Run one test module:

```bash
PYTHONPATH=src python3 -m unittest tests.test_market_notice -v
```

The build command writes a Pages-ready static site into `site/`.

## Dev container

This repo includes `.devcontainer/` so it can be opened in a ready-to-run container with Python 3.12, GitHub CLI, the Python/Copilot VS Code extensions, and the package installed in editable mode.

Once the container is built, the same commands work unchanged:

```bash
python3 -m aemo_forecast.cli build --output-dir site
python3 -m unittest discover -s tests -v
```

## Output layout

- `site/index.html` - predispatch market overview landing page
- `site/next-day.html` - regional mixed actual dispatch, 5-minute predispatch, and predispatch page
- `site/seven-day.html` - dedicated 7 day PASA / PD7DAY page
- `site/demand.html` - next 24 hour demand overview page
- `site/data/*.csv` - normalized tabular exports
- `site/data/*.json` - machine-readable exports and summary metadata
- `site/charts/*.svg` - generated charts per region

## Dataset choices

- `PD7DAY` supplies region price forecasts plus the gas fuel forecast total (`GPG_FUEL_FORECAST_TJ`)
- `DispatchIS_Reports` supplies actual regional dispatch history for the current NEM day
- `P5_Reports` supplies the 5-minute predispatch window for the next hour
- `Predispatch_Reports` supplies the remaining live regional predispatch window used on the overview and next-day pages
- `PDPASA` supplies day-ahead region adequacy fields including demand, capacity, LOR levels, and solar/wind metrics
- `STPASA` extends those adequacy fields across the longer horizon
- `Market_Notice` supplies recent notices as plain-text reports

Coal, hydro, and gas generation mix splits are not published unless AEMO exposes them directly in these forecast datasets. Right now the only fuel-style forecast field wired in is the gas fuel total from `PD7DAY`.
