"""Streamlit front end for the Precursive data-entry agent.

Run locally with:   streamlit run app.py

Single-user local version: the agent runs inside the button click via
asyncio.run. The sidebar shows a bounded, progressively-updating view of the
plan, and the expander streams the agent's live thinking (browser-use logs).
The browser opens visibly so you can complete the 2FA prompt yourself.
"""

import sys
import time
import asyncio
import tempfile
from collections import deque

import pandas as pd
import streamlit as st

from agent_core import run_entries, build_plan


# --- silence the benign Windows asyncio "closed pipe" shutdown noise ---
def _ignore_closed_pipe(unraisable):
    exc = unraisable.exc_value
    if isinstance(exc, ValueError) and "closed pipe" in str(exc):
        return
    sys.__unraisablehook__(unraisable)


sys.unraisablehook = _ignore_closed_pipe


st.set_page_config(page_title="Precursive Data Entry Agent", page_icon="📅", layout="wide")
st.title("📅 Precursive Data Entry Agent")
st.caption("Upload your timesheet, enter your Precursive login, and let the agent fill it in. "
           "Keep the browser window on so you can enter the 2FA code. "
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


# ---------------- sidebar plan rendering (bounded window) ----------------
def render_sidebar(box, plan, entry_state):
    """Draw a SHORT, progressively-updating view: counts, empty days,
    recently done, the entry running now, and the next few up. Bounded even
    for thousands of entries."""
    entries = plan["entries"]
    total = len(entries)
    done_count = sum(1 for s in entry_state.values() if s.startswith("done"))

    with box.container():
        st.header("📋 Plan")
        st.markdown(f"**Progress:** {done_count} / {total} entries done")

        if plan["skipped_empty"]:
            st.markdown("**Skipped — empty days**")
            for d in plan["skipped_empty"]:
                st.markdown(f"- ~~{d['day']} {d['date']}~~ · no hours")

        st.divider()

        # last few completed
        done_entries = [e for e in entries
                        if entry_state.get(e["index"], "pending").startswith("done")]
        for e in done_entries[-3:]:
            icon = "⚠️" if entry_state.get(e["index"]) == "done_issues" else "✅"
            st.markdown(f"{icon} {e['day']} {e['date']} — {e['project']}")

        # currently running (with its tasks)
        cur = next((e for e in entries if entry_state.get(e["index"]) == "running"), None)
        if cur is not None:
            st.markdown(f"**⏳ Now: {cur['day']} {cur['date']} — {cur['project']}**")
            for t in cur["tasks"]:
                st.caption(f"• {t['tag']} ({t['hours']}h)")

        # up next
        pending = [e for e in entries
                   if entry_state.get(e["index"], "pending") == "pending"]
        if pending:
            st.markdown("**Up next**")
            for e in pending[:5]:
                st.markdown(f"⬜ {e['day']} {e['date']} — {e['project']}")
            if len(pending) > 5:
                st.caption(f"…and {len(pending) - 5} more")


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

    suffix = ".xlsm" if uploaded.name.lower().endswith(".xlsm") else ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        excel_path = tmp.name

    try:
        plan = build_plan(excel_path, columns=columns_arg)
    except Exception as e:
        st.error(f"Couldn't read that Excel file: {e}")
        st.stop()

    entry_state = {e["index"]: "pending" for e in plan["entries"]}

    sidebar_box = st.sidebar.empty()
    render_sidebar(sidebar_box, plan, entry_state)

    status_box = st.empty()
    progress_bar = st.progress(0.0)
    table_box = st.empty()
    agent_expander = st.expander("🔍 Agent thinking (live)", expanded=False)
    agent_log_box = agent_expander.empty()

    # --- live agent-thinking stream (throttled so chatty logs don't thrash) ---
    log_lines = deque(maxlen=500)
    last_log_paint = {"t": 0.0}

    def log_cb(line):
        log_lines.append(line)
        now = time.time()
        if now - last_log_paint["t"] > 0.25:
            last_log_paint["t"] = now
            agent_log_box.code("\n".join(log_lines))

    def progress_cb(ev):
        idx = ev.get("index")
        phase = ev.get("phase")
        if phase == "start":
            entry_state[idx] = "running"
        elif phase == "done":
            entry_state[idx] = "done_issues" if ev.get("had_failures") else "done_ok"
        elif phase == "skip":
            entry_state[idx] = "done_ok"

        render_sidebar(sidebar_box, plan, entry_state)

        done_count = sum(1 for s in entry_state.values() if s.startswith("done"))
        total = ev.get("total", 0)
        progress_bar.progress(done_count / total if total else 0.0)
        status_box.info(
            f"Processed {done_count}/{total} — {ev.get('label', '')}  |  "
            f"tokens: {ev['tokens']:,}  |  cost: ${ev['cost']:.4f}"
        )
        if ev["failures"]:
            table_box.dataframe(pd.DataFrame(ev["failures"]), use_container_width=True)
        else:
            table_box.success("No failures so far ✅")

    status_box.info("Starting… the browser is launching and logging in (watch for the 2FA prompt).")
    try:
        result = asyncio.run(run_entries(
            excel_path=excel_path,
            columns=columns_arg,
            email=email,
            password=password,
            headless=not show_browser,
            progress_cb=progress_cb,
            log_cb=log_cb,
        ))
    except Exception as e:
        st.error(f"The run stopped unexpectedly: {e}")
        st.stop()

    # flush any remaining buffered log lines
    agent_log_box.code("\n".join(log_lines))

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