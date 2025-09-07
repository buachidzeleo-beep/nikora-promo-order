# -*- coding: utf-8 -*-
"""
Nikora Promo Orders — Plain Logic (Single File, No YAML)
- Incoming order files are NON-CHANGEABLE; we adapt on our side.
- Two steps only:
  1) Barcode fix via 2-column Georgian list (old -> new).
  2) Weekday split from Shop Schedule (Shop -> Weekday). We ignore dates in the order.

This version **locks** the columns (no dropdowns) and **auto-loads** schedule/map from local files,
so the operator only uploads the Order file.

Locked columns:
- Order:   Barcode = "Код EAN/UPC",  Shop = "Завод"
- Schedule: Shop = "shop_code",      Weekday = "allowed_weekday"
- Mapping columns (strict): new = "ძირითადი შტრიხკოდი", old = "შტრიხკოდი"

Default files the app tries to load (same folder as this .py or ./config/):
- barcode_map.xlsx
- shop_schedule.xlsx
"""

import io
import os
import zipfile
from datetime import datetime
from typing import Dict, List

import pandas as pd
import streamlit as st

DATE_STR_FMT = "%Y-%m-%d"
WEEKDAYS_EN: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

ORDER_BARCODE_COL = "Код EAN/UPC"
ORDER_SHOP_COL    = "Завод"

SCHED_SHOP_COL    = "shop_code"
SCHED_DAY_COL     = "allowed_weekday"

MAP_NEW_COL_GEO = "ძირითადი შტრიხკოდი"
MAP_OLD_COL_GEO = "შტრიხკოდი"

LOCAL_MAP_FILES = ["barcode_map.xlsx", os.path.join("config", "barcode_map.xlsx")]
LOCAL_SCHED_FILES = ["shop_schedule.xlsx", os.path.join("config", "shop_schedule.xlsx")]

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

def read_path_first_sheet(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    obj = pd.read_excel(path, sheet_name=None)
    first = next(iter(obj))
    return obj[first].copy()

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

def try_load_local(filename_candidates: List[str]) -> pd.DataFrame:
    here = os.path.dirname(__file__)
    for rel in filename_candidates:
        p1 = os.path.join(here, rel)
        p2 = rel
        for p in (p1, p2):
            try:
                if os.path.exists(p):
                    return read_path_first_sheet(p)
            except Exception:
                continue
    return pd.DataFrame()

st.set_page_config(page_title="Nikora Promo Orders — Fixed Columns", layout="wide")
st.title("Nikora Promo Orders — Fixed Columns (Single-File App)")
st.info("Incoming order files are **non-changeable**. We adapt on our side.\n"
        "Columns are **locked** and schedule/map are loaded from local files by default.")

left, right = st.columns([3, 2])

with left:
    schedule_df = try_load_local(LOCAL_SCHED_FILES)
    map_df = try_load_local(LOCAL_MAP_FILES)

    if schedule_df.empty:
        st.error("Could not load local **shop_schedule.xlsx**. Place it alongside the script or in ./config/.")
    else:
        st.success("Loaded local shop schedule ✔")

    if map_df.empty:
        st.error("Could not load local **barcode_map.xlsx**. Place it alongside the script or in ./config/.")
    else:
        st.success("Loaded local barcode map ✔")

    st.subheader("1) Upload Order file (REQUIRED)")
    order_file = st.file_uploader("Order file (.xlsx / .xls / .csv)", type=["xlsx","xls","csv"], key="order")

    st.caption("Optional: override local files at runtime (if needed)")
    override_schedule = st.file_uploader("Override Shop Schedule (optional)", type=["xlsx","xls","csv"], key="sched_override")
    override_map = st.file_uploader("Override Barcode Map (optional)", type=["xlsx","xls","csv"], key="map_override")

    if override_schedule is not None:
        schedule_df = read_any_table(override_schedule)
        st.warning("Using OVERRIDE Shop Schedule (uploaded file).")

    if override_map is not None:
        map_df = read_any_table(override_map)
        st.warning("Using OVERRIDE Barcode Map (uploaded file).")

    if order_file is not None and not schedule_df.empty and not map_df.empty:
        df = read_any_table(order_file)

        st.subheader("2) Process with fixed columns")
        st.write(f"- Order barcode column: **{ORDER_BARCODE_COL}**")
        st.write(f"- Order shop column: **{ORDER_SHOP_COL}**")
        st.write(f"- Schedule shop column: **{SCHED_SHOP_COL}**")
        st.write(f"- Schedule weekday column: **{SCHED_DAY_COL}**")
        go = st.button("Run (Barcode fix → Weekday split)")

        if go:
            missing = []
            for c in (ORDER_BARCODE_COL, ORDER_SHOP_COL):
                if c not in df.columns:
                    missing.append(c)
            for c in (SCHED_SHOP_COL, SCHED_DAY_COL):
                if c not in schedule_df.columns:
                    missing.append(c)
            for c in (MAP_NEW_COL_GEO, MAP_OLD_COL_GEO):
                if c not in map_df.columns:
                    missing.append(c)

            if missing:
                st.error("Missing required columns: " + ", ".join(missing))
                st.stop()

            work = df.copy()
            mapping = dict(zip(map_df[MAP_OLD_COL_GEO].astype(str), map_df[MAP_NEW_COL_GEO].astype(str)))
            work[ORDER_BARCODE_COL] = work[ORDER_BARCODE_COL].astype(str).map(lambda x: mapping.get(x, x))

            work[ORDER_SHOP_COL] = work[ORDER_SHOP_COL].astype(str).str.strip().str.upper()
            schedule_df[SCHED_SHOP_COL] = schedule_df[SCHED_SHOP_COL].astype(str).str.strip().str.upper()
            schedule_df["__Weekday__"] = schedule_df[SCHED_DAY_COL].apply(normalize_weekday)

            merged = work.merge(
                schedule_df[[SCHED_SHOP_COL, "__Weekday__"]],
                left_on=ORDER_SHOP_COL,
                right_on=SCHED_SHOP_COL,
                how="left",
            )

            splits: Dict[str, pd.DataFrame] = {}
            for wd in WEEKDAYS_EN:
                part = merged[merged["__Weekday__"] == wd].drop(columns=["__Weekday__", SCHED_SHOP_COL], errors="ignore")
                splits[wd] = part

            unknown_mask = merged["__Weekday__"].isna() | (merged["__Weekday__"] == "")
            if unknown_mask.sum() > 0:
                splits["Unassigned"] = merged[unknown_mask].drop(columns=["__Weekday__", SCHED_SHOP_COL], errors="ignore")
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
    - **Locked columns** so operators don't need to pick them.
    - **Auto-loads** `shop_schedule.xlsx` and `barcode_map.xlsx` from the app folder or `./config/`.
    - You can still override the schedule/map at runtime via optional uploads.
    """)
