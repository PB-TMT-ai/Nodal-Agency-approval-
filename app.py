import os
import re
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
DATA_FILE = "nodal_agency_data.csv"
EXCEL_FILE = "Government_Approval_Dashboard (1).xlsx"
EXCEL_SHEET = "Government Agencies Pipeline"

COLUMNS = [
    "agency", "ministry_state", "center_state", "status", "stage",
    "annual_demand_mt", "potential", "priority", "jsw_support",
    "approved_brands", "date", "comment",
]

STATUS_OPTIONS = ["Active", "Inactive"]
STAGE_OPTIONS = ["Discussion", "File Submitted", "Decisioning", ""]
POTENTIAL_OPTIONS = ["High", "Medium", "Low", ""]
PRIORITY_OPTIONS = ["High", "Medium", "Low", ""]

st.set_page_config(
    page_title="Nodal Agency Approval Dashboard",
    page_icon="🏛️",
    layout="wide",
)


# --------------------------------------------------------------------------- #
# Data helpers
# --------------------------------------------------------------------------- #
def _clean_demand(value):
    if pd.isna(value):
        return None
    text = str(value).replace(",", "").replace("\n", "").strip()
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def _seed_from_excel() -> pd.DataFrame:
    """Build the initial dataset from the uploaded Excel workbook."""
    raw = pd.read_excel(EXCEL_FILE, sheet_name=EXCEL_SHEET, header=0)
    colmap = {
        "Current state of the project": "status",
        "Department": "agency",
        "Central/State": "ministry_state",
        "Center/State": "center_state",
        "Approved TMT Brand": "approved_brands",
        "Annual Demand (MT)": "annual_demand_mt",
        "Volume Potential": "potential",
        "JSW Support": "jsw_support",
        "Priority": "priority",
        "Discussion Stage": "stage",
        "Remarks": "comment",
    }
    raw = raw.rename(columns=colmap)
    raw["annual_demand_mt"] = raw["annual_demand_mt"].apply(_clean_demand)

    text_cols = [c for c in COLUMNS if c not in ("annual_demand_mt", "date")]
    for col in text_cols:
        raw[col] = raw[col].apply(lambda v: "" if pd.isna(v) else str(v).replace("\n", " ").strip())

    raw["date"] = "2026-02-17"  # "Last Updated" from the workbook's Executive Summary
    df = raw[[c for c in COLUMNS if c in raw.columns]].copy()
    df = df[df["agency"].astype(str).str.strip() != ""].reset_index(drop=True)
    return df


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Force a consistent schema/dtypes so filters and charts never see mixed types."""
    df = df.copy()
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMNS]
    df["annual_demand_mt"] = pd.to_numeric(df["annual_demand_mt"], errors="coerce")
    for col in COLUMNS:
        if col != "annual_demand_mt":
            df[col] = df[col].fillna("").astype(str)
    return df.reset_index(drop=True)


def load_data() -> pd.DataFrame:
    """Load from the CSV store, seeding from the Excel file on first run."""
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
    else:
        df = _seed_from_excel()
        df.to_csv(DATA_FILE, index=False)
    return _normalize(df)


def save_data(df: pd.DataFrame) -> None:
    df.to_csv(DATA_FILE, index=False)


def filter_options(series) -> list:
    """Unique, non-blank values as sorted strings (robust to NaN/mixed types)."""
    return sorted({str(v).strip() for v in series.dropna() if str(v).strip()})


def fmt_mt(value) -> str:
    if pd.isna(value):
        return "—"
    return f"{int(value):,} MT"


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

st.title("🏛️ Nodal Agency Approval Dashboard")
st.caption("Track approval status, potential and remarks for each government nodal agency.")

tab_dash, tab_add = st.tabs(["📊 Dashboard", "➕ Add / Edit Agency"])

# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
with tab_dash:
    # ---- Filters --------------------------------------------------------- #
    with st.sidebar:
        st.header("Filters")
        f_status = st.multiselect("Status", filter_options(df["status"]))
        f_ministry = st.multiselect("Ministry / State", filter_options(df["ministry_state"]))
        f_potential = st.multiselect("Potential", filter_options(df["potential"]))
        f_stage = st.multiselect("Stage", filter_options(df["stage"]))

    view = df.copy()
    if f_status:
        view = view[view["status"].isin(f_status)]
    if f_ministry:
        view = view[view["ministry_state"].isin(f_ministry)]
    if f_potential:
        view = view[view["potential"].isin(f_potential)]
    if f_stage:
        view = view[view["stage"].isin(f_stage)]

    # ---- KPIs ------------------------------------------------------------ #
    active = view[view["status"].str.lower() == "active"]
    inactive = view[view["status"].str.lower() == "inactive"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Agencies", len(view))
    c2.metric("Active", len(active))
    c3.metric("Inactive", len(inactive))
    c4.metric("Annual Demand (Active)", fmt_mt(active["annual_demand_mt"].sum()))

    st.divider()

    # ---- Charts ---------------------------------------------------------- #
    ch1, ch2, ch3 = st.columns(3)

    with ch1:
        st.subheader("By Stage")
        stage_df = active[active["stage"] != ""]
        if len(stage_df):
            counts = stage_df["stage"].value_counts().reset_index()
            counts.columns = ["Stage", "Count"]
            fig = px.bar(counts, x="Stage", y="Count", color="Stage", text="Count")
            fig.update_layout(showlegend=False, height=320, margin=dict(t=10, b=10))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No staged active agencies in current filter.")

    with ch2:
        st.subheader("By Potential")
        pot_df = view[view["potential"] != ""]
        if len(pot_df):
            counts = pot_df["potential"].value_counts().reset_index()
            counts.columns = ["Potential", "Count"]
            fig = px.pie(
                counts, names="Potential", values="Count", hole=0.5,
                color="Potential",
                color_discrete_map={"High": "#2e7d32", "Medium": "#f9a825", "Low": "#c62828"},
            )
            fig.update_layout(height=320, margin=dict(t=10, b=10))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No potential data in current filter.")

    with ch3:
        st.subheader("By Ministry / State")
        min_df = view[view["ministry_state"] != ""]
        if len(min_df):
            counts = min_df["ministry_state"].value_counts().reset_index()
            counts.columns = ["Ministry / State", "Count"]
            fig = px.bar(counts, x="Count", y="Ministry / State", orientation="h", text="Count")
            fig.update_layout(height=320, margin=dict(t=10, b=10), yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No ministry/state data in current filter.")

    st.divider()

    # ---- Status table ---------------------------------------------------- #
    st.subheader("Current Status by Nodal Agency")
    table = view.copy()
    table["annual_demand_mt"] = table["annual_demand_mt"].apply(
        lambda v: "" if pd.isna(v) else f"{int(v):,}"
    )
    table = table.rename(columns={
        "agency": "Nodal Agency",
        "ministry_state": "Ministry / State",
        "center_state": "Center / State",
        "status": "Status",
        "stage": "Stage",
        "annual_demand_mt": "Annual Demand (MT)",
        "potential": "Potential",
        "priority": "Priority",
        "jsw_support": "JSW Support",
        "approved_brands": "Approved Brands",
        "date": "Date",
        "comment": "Comment",
    })
    display_cols = [
        "Nodal Agency", "Ministry / State", "Status", "Stage",
        "Annual Demand (MT)", "Potential", "Priority", "Date", "Comment",
    ]
    st.dataframe(table[display_cols], width="stretch", hide_index=True)

    st.download_button(
        "⬇️ Download data (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="nodal_agency_data.csv",
        mime="text/csv",
    )

# --------------------------------------------------------------------------- #
# Add / Edit
# --------------------------------------------------------------------------- #
with tab_add:
    st.subheader("Add a new nodal agency")

    with st.form("add_agency", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            agency = st.text_input("Nodal Agency *", placeholder="e.g. NHAI")
            potential = st.selectbox("Potential *", POTENTIAL_OPTIONS, index=0)
            entry_date = st.date_input("Date *", value=date.today())
            ministry_state = st.text_input("Ministry / State", placeholder="e.g. MoRTH / Uttar Pradesh")
            center_state = st.text_input("Center / State", placeholder="e.g. Center")
        with col_b:
            status = st.selectbox("Status", STATUS_OPTIONS, index=0)
            stage = st.selectbox("Stage", STAGE_OPTIONS, index=0)
            annual_demand = st.number_input("Annual Demand (MT)", min_value=0, step=1000, value=0)
            priority = st.selectbox("Priority", PRIORITY_OPTIONS, index=0)
        comment = st.text_area("Comment / Remarks", placeholder="Latest update, next steps, blockers…")

        submitted = st.form_submit_button("💾 Save", type="primary", width="stretch")

        if submitted:
            if not agency.strip():
                st.error("Nodal Agency name is required.")
            else:
                new_row = {
                    "agency": agency.strip(),
                    "ministry_state": ministry_state.strip(),
                    "center_state": center_state.strip(),
                    "status": status,
                    "stage": stage,
                    "annual_demand_mt": float(annual_demand) if annual_demand else None,
                    "potential": potential,
                    "priority": priority,
                    "jsw_support": "",
                    "approved_brands": "",
                    "date": entry_date.strftime("%Y-%m-%d"),
                    "comment": comment.strip(),
                }
                st.session_state.df = _normalize(
                    pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                )
                save_data(st.session_state.df)
                st.success(f"Saved “{agency.strip()}”.")

    st.divider()
    st.subheader("Edit / delete existing entries")
    st.caption("Edit cells directly, tick rows to delete, then click Save changes.")

    edited = st.data_editor(
        st.session_state.df,
        width="stretch",
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "annual_demand_mt": st.column_config.NumberColumn("Annual Demand (MT)", format="%d"),
            "status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
            "stage": st.column_config.SelectboxColumn("Stage", options=STAGE_OPTIONS),
            "potential": st.column_config.SelectboxColumn("Potential", options=POTENTIAL_OPTIONS),
            "priority": st.column_config.SelectboxColumn("Priority", options=PRIORITY_OPTIONS),
        },
        key="editor",
    )

    if st.button("💾 Save changes", type="primary"):
        st.session_state.df = _normalize(edited)
        save_data(st.session_state.df)
        st.success("Changes saved.")
        st.rerun()
