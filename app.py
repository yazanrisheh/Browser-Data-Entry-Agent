"""Streamlit front end for the Precursive data-entry agent.

Run locally with:   streamlit run app.py

This is the "for now" single-user local version: the agent runs inside the
button click via asyncio.run, and the failures table updates live as it goes.
For a deployed multi-user version you'd move the run to a background worker
and have the page poll a database instead (see notes in chat).
"""

import sys
import asyncio
import tempfile

import pandas as pd
import streamlit as st

from agent_core import run_entries


# --- silence the benign Windows asyncio "closed pipe" shutdown noise ---
def _ignore_closed_pipe(unraisable):
    exc = unraisable.exc_value
    if isinstance(exc, ValueError) and "closed pipe" in str(exc):
        return
    sys.__unraisablehook__(unraisable)


sys.unraisablehook = _ignore_closed_pipe


st.set_page_config(page_title="Precursive Data Entry Agent", page_icon="🗓️", layout="wide")
st.title("🗓️ Precursive Data Entry Agent")
st.caption("Upload your timesheet, enter your Precursive login, and let the agent fill it in. "
           "Anything it can't log is flagged below and downloadable as a CSV.")

# ---------------- inputs ----------------
col_a, col_b = st.columns(2)
with col_a:
    email = st.text_input("Precursive email")
with col_b:
    password = st.text_input("Precursive password", type="password")

uploaded = st.file_uploader("Timesheet (Excel)", type=["xlsx", "xlsm"])

st.subheader("Which date columns to process?")
mode = st.radio(
    "Selection mode",
    ["All columns", "First N columns", "Specific columns"],
    horizontal=True,
    label_visibility="collapsed",
)

columns_arg = None
if mode == "First N columns":
    n = st.number_input("How many columns from the left? (1 = Mon, 2 = Tue, ...)",
                        min_value=1, value=3, step=1)
    columns_arg = int(n)
elif mode == "Specific columns":
    spec = st.text_input("Column positions, comma-separated (e.g. 1,3,5)", value="3")
    try:
        columns_arg = [int(x.strip()) for x in spec.split(",") if x.strip()]
    except ValueError:
        st.error("Use only numbers separated by commas, e.g. 1,3,5")
        columns_arg = []

show_browser = st.checkbox("Show the browser window while it works", value=True)

run_btn = st.button("Run data entry", type="primary")

st.divider()

# ---------------- run ----------------
if run_btn:
    if not email or not password:
        st.warning("Please enter both your Precursive email and password.")
        st.stop()
    if uploaded is None:
        st.warning("Please upload your timesheet Excel file.")
        st.stop()
    if mode == "Specific columns" and not columns_arg:
        st.warning("Please enter valid column positions.")
        st.stop()

    # Save the uploaded file to a temp path for openpyxl to read.
    suffix = ".xlsm" if uploaded.name.lower().endswith(".xlsm") else ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        excel_path = tmp.name

    status_box = st.empty()
    progress_bar = st.progress(0.0)
    table_box = st.empty()

    def progress_cb(done, total, failures, tokens, cost, label):
        progress_bar.progress(done / total if total else 0.0)
        status_box.info(
            f"Processed {done}/{total} — {label}  |  tokens: {tokens:,}  |  cost: ${cost:.4f}"
        )
        if failures:
            table_box.dataframe(pd.DataFrame(failures), use_container_width=True)
        else:
            table_box.success("No failures so far ✅")

    status_box.info("Starting… the browser is launching and logging in.")
    try:
        result = asyncio.run(run_entries(
            excel_path=excel_path,
            columns=columns_arg,
            email=email,
            password=password,
            headless=not show_browser,
            progress_cb=progress_cb,
        ))
    except Exception as e:
        st.error(f"The run stopped unexpectedly: {e}")
        st.stop()

    # ---------------- summary ----------------
    progress_bar.progress(1.0)
    failures = result["failures"]
    if failures:
        status_box.warning(
            f"Done. {len(failures)} task(s) were skipped or failed out of "
            f"{result['total']} entr(ies). Tokens: {result['tokens']:,} · Cost: ${result['cost']:.4f}"
        )
        df = pd.DataFrame(failures)
        table_box.dataframe(df, use_container_width=True)
        st.download_button(
            "⬇️ Download the missed-tasks CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="missed_tasks.csv",
            mime="text/csv",
        )
    else:
        status_box.success(
            f"All tasks logged successfully across {result['total']} entr(ies)! "
            f"Tokens: {result['tokens']:,} · Cost: ${result['cost']:.4f}"
        )
        table_box.empty()