# Tile Hunt Simulator — README

A Colab-first Python workflow to analyze “Tile Hunt” event data, enrich it with Google Sheets configuration, and produce player progression insights and visualizations.

---

## ✨ What this does

This simulator (analysis notebook/script) loads raw event logs from CSV, joins them with configuration tables from Google Sheets, calculates per-player daily MGs and cumulative progression, assigns levels from a config, and generates a suite of plots to understand distribution, drop-offs, and percentile-based outcomes.

**Key outputs**

* 100% stacked bar of MGs by feature per event day
* Final level histogram and share of players by final level
* Heatmap of unique players per (stuck) level by event day
* Percentiles of max level reached (50th/mean/75th/90th/95th/99th)
* Daily total MGs collected
* Daily average MGs collected
* Average cumulative MGs per event day

---

## 🗂️ Data sources

1. **Google Drive CSV** (mounted in Colab):

   * `tile_hunt_data.csv` at `/content/gdrive/MyDrive/TileHunt_Sim/`
2. **Google Sheets** (via `gspread`):

   * Spreadsheet **key**: `1i-ap1vCIHOxoo_dpxuIIlSKVX6oxqidYxNJMfVSwQ0c`
   * Worksheet **MGs Distribution** → columns: `feature`, `config_id`, `milestone_id`, `mgs`, `config_name`
   * Worksheet **TileHunt Config** → columns: `level`, `picks_from`, `picks_to`, `energy`

> You can change these locations/keys in the configuration section of the code.

---

## ✅ Prerequisites

* A Google account with access to the target Google Sheet
* Colab environment (recommended) **or** local Python 3.10+
* Access to the CSV in your Google Drive
* Enabled Google Drive and Google Sheets APIs (Colab handles OAuth prompts)

**Python libraries used**

```
itertools, pandas, numpy, openpyxl, duckdb, warnings,
matplotlib, seaborn, gspread, google-auth, google-colab,
polars, tqdm
```

---

## 🚀 Quick Start (in Google Colab)

1. Open the notebook/script in Google Colab.

2. **Run all cells.** The code will:

   * Mount Google Drive
   * Authenticate with Google
   * Connect to DuckDB (in-memory)
   * Load configuration from the two worksheets
   * Load `tile_hunt_data.csv` from your Drive path
   * Process & plot all charts

3. Review the printed logs for progress (“Mounting Google Drive…”, “Loading configuration data…”, etc.).

> If you’re using a copy of the spreadsheet, update the `spreadsheet = gc.open_by_key('<your_key>')` line.

---

## 🧩 Configuration knobs

Edit these values near the top of the script:

* **`data_path`**: folder containing `tile_hunt_data.csv`.
* **`start_date`, `end_date`**: event window filter (timezone implicit to the timestamps).
* **Spreadsheet key**: replace with your Google Sheet key if needed.
* **Worksheet names**: `"MGs Distribution"`, `"TileHunt Config"` (change if your tabs are named differently).

---

## 📜 Expected schemas

### `tile_hunt_data.csv`

Minimum expected columns:

* `eventtime` (datetime string)
* `bar_id` (int; renamed to `milestone_id` in code)
* `config_id` (string)
* `playerid` (string/int)

The script lowercases all column names and creates:

* `date` (`eventtime`.date)
* `event_day_start` = `eventtime` minus 10 hours, then `.date`

### Google Sheet — **MGs Distribution**

* `feature` (string)
* `config_id` (string)
* `milestone_id` (int)
* `mgs` (int)
* `config_name` (string)

### Google Sheet — **TileHunt Config**

* `level` (int)
* `picks_from` (float)
* `picks_to` (float)
* `energy` (float)
* The script also computes `cumu_energy` (grouped cumulative sum by level) — used for reference.

---

## 🔗 Core pipeline

1. **Filter event window** by `start_date`/`end_date`.
2. **Join** filtered events with **MGs Distribution** on (`config_id`, `milestone_id`).
3. **Aggregate** `mgs` per `playerid` and `event_day_start` → `mgs_collected` and `cumu_mgs_collected`.
4. **Level assignment** by joining with **TileHunt Config** using:

   * `cumu_mgs_collected >= picks_from` and `< picks_to`
5. **Event day index** derived from unique `event_day_start` (1…N) and merged back.
6. **Filter** out `level == 0` and constrain to first 7 event days (configurable).
7. **Aggregate** max level per player and compute summary statistics.
8. **Visualize** multiple distributions and trends.

DuckDB is used for a concise join; Pandas/Seaborn/Matplotlib for aggregation & plots.

---

## 📈 Visualizations produced

* **MGs by feature per event day** — 100% stacked bar with in-bar percentage labels
* **Final level distribution** — counts and percentages
* **Drop-off heatmap** — players at `stuck_level = level + 1` by event day
* **Levels by percentile** — bars for median, mean, 75th, 90th, 95th, 99th
* **Daily totals** — sum of MGs collected per event day
* **Daily averages** — average MGs collected per event day
* **Average cumulative MGs** — per event day

> Plots are sized for Colab; adjust `figsize`, grids, and label rotations if exporting.

---

## 🧪 Quality checks & notes

* The merge with MGs Distribution drops rows with missing `mgs` (`dropna(subset=['mgs'])`). Remove this if you need to include players with zero collection on a day.
* `event_day` calculation depends on `event_day_start` and the 10-hour offset; confirm this aligns with event business logic.
* Level bounds must be **non-overlapping** and **cover all expected ranges** of cumulative MGs.
* The script currently filters to `event_day < 8` (first 7 days). Adjust if your event is longer.

---

## 🧯 Troubleshooting

* **WorksheetNotFound**: Verify tab names exactly match (`MGs Distribution`, `TileHunt Config`).
* **Auth errors**: Re-run the Colab auth cell; ensure the Google account has access to the sheet and Drive file.
* **File not found**: Confirm `data_path` and that `tile_hunt_data.csv` exists.
* **Type errors on cast**: Check that numeric columns in the sheets are numeric and free of stray text/blank headers.
* **Empty charts**: Ensure the `start_date`/`end_date` window overlaps your CSV and `config_id`s match across sources.

---

## 📌 Known TODOs (from code comments)

* Add revenue share per max level reached (needs revenue data)
* End-of-day status by percentile
* Data by iteration
* Wager data to calculate payout
* Purchase distribution modeling
* Dice factor on specific days

---

## 🔐 Privacy & data handling

* Data are read-only from Drive and Sheets; no writes occur.
* Do not commit real spreadsheet keys or PII to version control.
* Consider parameterizing keys and paths via environment variables when running locally.

---

## 🧾 Example configuration block (snippet)

```python
# Define the data path and date range for filtering
data_path = '/content/gdrive/MyDrive/TileHunt_Sim/'
start_date = pd.to_datetime('2025-04-21 10:00:00')
end_date   = pd.to_datetime('2025-04-28 09:59:00')

# Google Sheet
SPREADSHEET_KEY = ''
MG_TAB = 'MGs Distribution'
CONFIG_TAB = 'TileHunt Config'
```

---

## 📜 License

Choose a license appropriate for your org (e.g., MIT, Apache-2.0, internal-only). Add it to the repository root.

---

## 🙌 Contributions

Issues and PRs welcome. Please include sample rows of the three inputs (CSV + two tabs) when reporting data issues to help reproduce.
