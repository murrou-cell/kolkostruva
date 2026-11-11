# kolkostruva

Price comparison across Bulgarian retail chains, built from the daily open data that КЗП publishes at [kolkostruva.bg/opendata](https://kolkostruva.bg/opendata) under чл. 55б ЗВЕРБ. Unofficial project, not affiliated with КЗП.

A scheduled GitHub Actions run downloads the latest daily files, reduces them (`reduce.py`, `updater.py`) into JSON, and deploys the static page in `web/` to GitHub Pages. No server, no database.

Run it locally: `DATA_DIR=_data BACKFILL_DAYS=3 KEEP_DAYS=1 python updater.py --once`, then copy `web/*` and the generated `latest.json`, `meta.json` and `cities/` (under `data/`) into one folder and serve it.

City names come from the NSI ЕКАТТЕ register (`ekatte.json`).
