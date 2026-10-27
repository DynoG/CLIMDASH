# Adding a New Weather API Provider

This guide is the checklist to follow when integrating a new
token-authenticated API.

## Step 1 — Read the contract
Open `src/providers/base.py`. Every provider must return DataFrames
matching `CURRENT_COLUMNS` and `HISTORICAL_COLUMNS`.

## Step 2 — Create the adapter
Create `src/providers/<api_name>.py`. Subclass `WeatherProvider`.
Use `src/providers/open_meteo.py` as the reference implementation.

## Step 3 — Wire configuration
Add `MY_API_BASE_URL` and `MY_API_TOKEN` to `.env.example`. Read them
in `src/config.py` (do not call `os.getenv` from the adapter).

## Step 4 — Register
Add an `elif name == "<api_name>": return MyApiProvider()` branch in
`src/ingestion.get_provider()`.

## Step 5 — Test
Add `tests/test_<api_name>.py` that mocks the HTTP call and asserts
the schema. Run `pytest -q`.