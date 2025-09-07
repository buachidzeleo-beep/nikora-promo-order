# -*- coding: utf-8 -*-
"""
Nikora Promo Orders — Plain Logic (Single-File App, NO YAML)
"""

import io
import zipfile
from datetime import datetime
from typing import Dict, List

import pandas as pd
import streamlit as st

DATE_STR_FMT = "%Y-%m-%d"
WEEKDAYS_EN: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

BARCODE_CANDIDATES: List[str] = ["შტრიხკოდი", "Barcode", "barcode", "EAN", "ean", "SKU", "sku"]
SHOP_CANDIDATES: List[str] = ["ShopID", "shop_id", "Shop", "shop", "StoreID", "store_id", "Store", "store", "ობიექტი", "მაღაზია"]
SCHED_DAY_CANDIDATES: List[str] = ["Weekday", "weekday", "დღე", "Day", "day"]

MAP_NEW_COL_GEO = "ძირითადი შტრიხკოდი"
MAP_OLD_COL_GEO = "შტრიხკოდი"

GEORGIAN_DAY = {
    "Monday": "ორშაბათი",
    "Tuesday": "სამშაბათი",
    "Wednesday": "ოთხშაბათი",
    "Thursday": "ხუთშაბათი",
    "Friday": "პარასკევი",
}

def read_any_table(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith((".xls", ".xlsx")):
        obj = pd.read_excel(uploaded_file, sheet_name=None)
        first = next(iter(obj))
        return obj[first].copy()
    return pd.DataFrame()

def pick_first_existing(cols: List[str], candidates: List[str]) -> str:
    for c in candidates:
        if c in cols:
            return c
    return cols[0] if cols else ""

def normalize_weekday(val) -> str:
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if s.isdigit():
        i = int(s)
        if 1 <= i <= 5:
            return WEEKDAYS_EN[i-1]
        return ""
    low = s.lower()
    eng_map = {"monday":"Monday","tuesday":"Tuesday","wednesday":"Wednesday","thursday":"Thursday","friday":"Friday"}
    if low in eng_map:
        return eng_map[low]
    geo_map = {"ორშაბათი":"Monday","სამშაბათი":"Tuesday","ოთხშაბათი":"Wednesday","ხუთშაბათი":"Thursday","პარასკევი":"Friday"}
    if s in geo_map:
        return geo_map[s]
    return ""

def export_excel_bytes(df: pd.DataFrame, sheet_name: str = "Orders") -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    bio.seek(0)
    return bio.read()

st.set_page_config(page_title="Nikora Promo Orders — Plain Logic", layout="wide")
st.title("Nikora Promo Orders — Plain Logic (Single-File App)")
st.info("Incoming order files are **non-changeable**. We adapt on our side.")

left, right = st.columns([3, 2])

with left:
    st.subheader("1) Upload files (all required)")
    order_file = st.file_uploader("Order file (.xlsx / .xls / .csv)", type=["xlsx","xls","csv"], key="order")
    schedule_file = st.file_uploader("Shop Schedule (.xlsx / .xls / .csv)", type=["xlsx","xls","csv"], key="schedule")
    map_file = st.file_uploader("Barcode mapping (.xlsx / .xls / .csv) — columns: "
                                f"'{MAP_NEW_COL_GEO}' (new), '{MAP_OLD_COL_GEO}' (old)",
                                type=["xlsx","xls","csv"], key="map")

    if order_file is not None and schedule_file is not None and map_file is not None:
        df = read_any_table(order_file)
        schedule_df = read_any_table(schedule_file)
        map_df = read_any_table(map_file)

        st.subheader("2) Select columns")
        cols = df.columns.tolist()
        barcode_col_guess = pick_first_existing(cols, BARCODE_CANDIDATES)
        shop_col_guess = pick_first_existing(cols, SHOP_CANDIDATES)
        barcode_col = st.selectbox("Order: Barcode column", options=cols, index=cols.index(barcode_col_guess) if barcode_col_guess in cols else 0)
        shop_col = st.selectbox("Order: Shop column", options=cols, index=cols.index(shop_col_guess) if shop_col_guess in cols else 0)

        scols = schedule_df.columns.tolist()
        sched_day_guess = pick_first_existing(scols, SCHED_DAY_CANDIDATES)
        sched_shop_guess = scols[0] if scols else None
        sched_shop_col = st.selectbox("Schedule: Shop column", options=scols, index=scols.index(sched_shop_guess) if sched_shop_guess in scols else 0)
        sched_day_col = st.selectbox("Schedule: Weekday column", options=scols, index=scols.index(sched_day_guess) if sched_day_guess in scols else 0)

        run = st.button("3) Process")

        if run:
            work = df.copy()

            if MAP_NEW_COL_GEO not in map_df.columns or MAP_OLD_COL_GEO not in map_df.columns:
                st.error(f"Mapping must have columns: '{MAP_NEW_COL_GEO}' (new), '{MAP_OLD_COL_GEO}' (old).")
                st.stop()
            mapping = dict(zip(map_df[MAP_OLD_COL_GEO].astype(str), map_df[MAP_NEW_COL_GEO].astype(str)))
            work[barcode_col] = work[barcode_col].astype(str).map(lambda x: mapping.get(x, x))

            work[shop_col] = work[shop_col].astype(str).str.strip().str.upper()
            schedule_df[sched_shop_col] = schedule_df[sched_shop_col].astype(str).str.strip().str.upper()
            schedule_df["__Weekday__"] = schedule_df[sched_day_col].apply(normalize_weekday)

            merged = work.merge(schedule_df[[sched_shop_col, "__Weekday__"]], left_on=shop_col, right_on=sched_shop_col, how="left")

            splits: Dict[str, pd.DataFrame] = {}
            for wd in WEEKDAYS_EN:
                part = merged[merged["__Weekday__"] == wd].drop(columns=["__Weekday__", sched_shop_col], errors="ignore")
                splits[wd] = part

            unknown_mask = merged["__Weekday__"].isna() | (merged["__Weekday__"] == "")
            if unknown_mask.sum() > 0:
                splits["Unassigned"] = merged[unknown_mask].drop(columns=["__Weekday__", sched_shop_col], errors="ignore")
                st.warning(f"{int(unknown_mask.sum())} rows have no weekday in schedule — kept in 'Unassigned'.")

            st.subheader("Summary by weekday")
            st.write({k: len(v) for k, v in splits.items()})

            st.subheader("Download files")
            date_str = datetime.now().strftime(DATE_STR_FMT)
            for wd in ["Monday","Tuesday","Wednesday","Thursday","Friday","Unassigned"]:
                if wd in splits:
                    geo = GEORGIAN_DAY.get(wd, wd)
                    fname = f"ნიკორა, {geo}, {date_str}.xlsx" if wd != "Unassigned" else f"ნიკორა, გაურკვეველი დღე, {date_str}.xlsx"
                    data = export_excel_bytes(splits[wd])
                    st.download_button(label=f"Download {wd} ({geo})", data=data, file_name=fname, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.subheader("Or download everything as ZIP")
            zip_bio = io.BytesIO()
            with zipfile.ZipFile(zip_bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for wd in ["Monday","Tuesday","Wednesday","Thursday","Friday","Unassigned"]:
                    if wd in splits:
                        geo = GEORGIAN_DAY.get(wd, wd)
                        fname = f"ნიკორა, {geo}, {date_str}.xlsx" if wd != "Unassigned" else f"ნიკორა, გაურკვეველი დღე, {date_str}.xlsx"
                        zf.writestr(fname, export_excel_bytes(splits[wd]))
            zip_bio.seek(0)
            st.download_button(label="Download ZIP (all files)", data=zip_bio.getvalue(), file_name=f"ნიკორა, დაგრუპული დღეებით, {date_str}.zip", mime="application/zip")

with right:
    st.subheader("Notes")
    st.markdown("""
    - **No deletions**. Every incoming row is preserved.
    - **Barcode mapping**: strictly uses two Georgian columns: „ძირითადი შტრიხკოდი“ (new) and „შტრიხკოდი“ (old).
    - **Weekday** comes **only** from Shop Schedule; we ignore dates in the order file.
    - Export filenames are in Georgian.
    """)
