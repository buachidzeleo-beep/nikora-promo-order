# Nikora Promo Orders — Plain Logic

Incoming order files are **non-changeable** — we adapt on our side. This app applies a fixed barcode mapping and splits the final order into **five weekday files** based on a **Shop Schedule**.

## Process (2 steps)
1. **Barcode fix (REQUIRED):** Replace values in the order's barcode column using a 2‑column Georgian mapping file:

   - Column 1 (new): **„ძირითადი შტრიხკოდი“**
   - Column 2 (old): **„შტრიხკოდი“**

2. **Weekday split (REQUIRED):** Derive weekday via VLOOKUP logic from **Shop Schedule** (Shop → Weekday). We **ignore dates** inside the order file. Split into **Mon–Fri**, keep unmatched in **Unassigned**.

## Files
- `Nikora_promo_orders.py` — Streamlit app (place at repo root).
- `config/config.yaml` — Project configuration (documenting column names, normalization, output pattern). The current app does not require this file to run; it serves as a repo config for clarity and future automation.
- `requirements.txt` — Python dependencies.
- `.gitignore` — Basic ignores for Python/Streamlit/exports.

## Run
```bash
pip install -r requirements.txt
python -m streamlit run Nikora_promo_orders.py
```

## Using the App
1. Upload **Order** file (`.xlsx/.xls/.csv`)
2. Upload **Shop Schedule** (Shop → Weekday)
3. Upload **Barcode Mapping** (2 columns: **„ძირითადი შტრიხკოდი“**, **„შტრიხკოდი“**)
4. Select the **Barcode column** and **Shop column** from the order in the dropdowns
5. Click **Process orders**
6. Download **weekday files** or a combined **ZIP**

## Notes
- We **do not delete** rows. If a shop isn't found in the schedule or weekday is invalid, those rows go to **Unassigned**.
- Column names are chosen in the UI. If you want to **lock** column names and read `config/config.yaml` automatically, see the block below to patch the script.

## (Optional) Auto‑apply config
Add this snippet near the top of `Nikora_promo_orders.py` (after imports) to **preselect/lock** columns from `config/config.yaml` when present:
```python
import os, yaml
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.yaml")
CFG = None
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CFG = yaml.safe_load(f)

# Later, after reading dataframes and before showing selectboxes:
force_bar = CFG.get("order", {}).get("force_barcode_column") if CFG else None
force_shop = CFG.get("order", {}).get("force_shop_column") if CFG else None
sched_force_shop = CFG.get("schedule", {}).get("force_shop_column") if CFG else None
sched_force_day = CFG.get("schedule", {}).get("force_weekday_column") if CFG else None

# If provided, skip the dropdowns and set columns directly:
if force_bar and force_bar in df.columns:
    barcode_col = force_bar
if force_shop and force_shop in df.columns:
    shop_col = force_shop
# For schedule, replace:
#   sched_shop_col, sched_day_col = schedule_df.columns[0], schedule_df.columns[1]
# with:
if sched_force_shop and sched_force_shop in schedule_df.columns:
    sched_shop_col = sched_force_shop
if sched_force_day and sched_force_day in schedule_df.columns:
    sched_day_col = sched_force_day
```

## License
Internal / private use for Nikora order processing.
