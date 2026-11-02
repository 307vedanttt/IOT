import os
import pandas as pd
import streamlit as st

LOG_FILE = "logs/events.csv"

st.set_page_config(page_title="PPE Gate Compliance Report", layout="wide", page_icon="🛡️")
st.title("🛡️ PPE Compliance Gate: Analytics & Audit Report")

if st.button("🔄 Refresh Data"):
    st.rerun()

if not os.path.exists(LOG_FILE):
    st.info("No events logged yet. Run main.py first to start capturing gate entries.")
    st.stop()

df = pd.read_csv(LOG_FILE)
total = len(df)
passed = int((df["result"] == "PASS").sum())
violations = int((df["result"] == "VIOLATION").sum())
rate = (100 * passed / total) if total else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Checks", total)
c2.metric("Compliant Entries", passed)
c3.metric("Safety Violations", violations)
c4.metric("Compliance Rate", f"{rate:.1f}%")

viol = df[df["result"] == "VIOLATION"]
if not viol.empty:
    items = viol["missing"].fillna("").str.split("+").explode()
    non_empty_items = items[items != ""]
    if not non_empty_items.empty:
        st.subheader("📊 Most Frequent Violations")
        st.bar_chart(non_empty_items.value_counts())

st.subheader("📋 Event Log (Latest Entries First)")
st.dataframe(df.tail(50).iloc[::-1], use_container_width=True)

st.subheader("📸 Latest Violation Snapshots")
photos = [p for p in viol["snapshot"].dropna().tolist()[-6:][::-1] if os.path.exists(p)]

if photos:
    cols = st.columns(3)
    for i, p in enumerate(photos):
        cols[i % 3].image(p, caption=os.path.basename(p), use_container_width=True)
else:
    st.caption("No violation snapshots recorded yet.")

