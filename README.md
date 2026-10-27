# Climate Reporting Pipeline

A modular climate and weather reporting pipeline built on **Open-Meteo**,
**Pandas**, **ipywidgets**, and **ipyleaflet**. Designed from day one to
swap the data provider for **any future token-authenticated REST API**
without touching the notebooks or the dashboard code.

## Why it's built this way

All external APIs are adapted through a provider contract
(`src/providers/base.py`). Downstream code depends only on the
**normalised DataFrame schema**, never on a specific API's response
shape. Adding a new API = writing one new file under `src/providers/`
and adding one line to `src/ingestion.get_provider()`. Nothing else
changes.

## Quick start (from absolute scratch)

### 1. Clone and enter the repo
```bash
git clone https://github.com/<you>/climate-reporting-pipeline.git
cd climate-reporting-pipeline
```

### 2. Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows PowerShell
```

### 3. Install dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env if you have an API key. For the free Open-Meteo tier,
# leave OPEN_METEO_API_KEY blank and OPEN_METEO_COMMERCIAL=false.
```

### 5. Launch the notebook
```bash
jupyter lab
# Then open notebooks/executive_report.ipynb and run all cells.
```

## Project layout
```
src/                 Importable Python — the only place logic lives
  providers/         One file per external API (adapter pattern)
  config.py          Environment + path loading
notebooks/           Exploratory and deliverable notebooks
data/                cities.csv committed; raw/ and processed/ git-ignored
docs/                Long-form guides (see api_provider_guide.md)
tests/               pytest modules
```

## Configuration reference
All configuration lives in `.env`. The keys are documented in
`.env.example`. The most important:

| Variable                                     | Purpose                                                |
|----------------------------------------------|--------------------------------------------------------|
| `PROVIDER`                                   | Which provider to use (`open_meteo` by default)        |
| `OPEN_METEO_COMMERCIAL`                      | `true` to route to `customer-api.open-meteo.com`       |
| `OPEN_METEO_API_KEY`                         | Only required if `OPEN_METEO_COMMERCIAL=true`          |
| `GENERIC_API_BASE_URL` / `GENERIC_API_TOKEN` | Placeholders for a future provider                     |
| `CITIES_CSV`                                 | Path to the location list (default `data/cities.csv`)  |

## Adding a new API provider

See [`docs/api_provider_guide.md`](docs/api_provider_guide.md). In short:

1. Subclass `WeatherProvider` in a new file under `src/providers/`.
2. Implement `fetch_current` and `fetch_historical` to return the
   normalised schema (see `src/providers/base.py`).
3. Add any required env vars to `.env.example`.
4. Register the provider in `src/ingestion.get_provider()`.

The notebook, the map, and the executive dashboard will continue to
work with no changes.

## Running tests
```bash
pytest -q
```

## Serving a read-only executive dashboard
```bash
voila notebooks/executive_report.ipynb --no-browser
```

## Troubleshooting

**Widgets render as JSON.** JupyterLab 4 + ipywidgets 8 works out of
the box; older setups may need `pip install jupyterlab_widgets`.

**`FileNotFoundError: data/cities.csv`.** Run from the repo root, or
set `CITIES_CSV` in `.env` to an absolute path.

**`RuntimeError: Required environment variable ... is missing`.** You
forgot `cp .env.example .env`.

## License
MIT. See `LICENSE`.