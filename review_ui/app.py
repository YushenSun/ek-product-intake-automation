import json
import os

import httpx
import streamlit as st

API = os.getenv("API_BASE_URL", "http://localhost:8000")
st.set_page_config(page_title="EK Intake Review", layout="wide")
st.title("EK Product Intake — review queue")
st.caption("Synthetic-data-only internal-tool PoC. Correct records before approval; errors cannot be overridden.")

try:
    metrics = httpx.get(f"{API}/metrics", timeout=5).json()
    cols = st.columns(4)
    cols[0].metric("Processed", metrics["products_processed"])
    cols[1].metric("Auto-approved", metrics["automatically_approved"])
    cols[2].metric("Needs review", metrics["review_required"])
    cols[3].metric("Rejected", metrics["rejected"])
except Exception as exc:
    st.error(f"Could not reach API at {API}: {exc}")
    st.stop()

status = st.selectbox("Filter", ["all", "review_required", "approved", "rejected"])
params = {} if status == "all" else {"status": status}
products = httpx.get(f"{API}/products", params=params, timeout=5).json()
if not products:
    st.info("No submissions yet. Use the API docs or send sample_data/clean_product.json.")
    st.stop()

selected = st.selectbox("Product", products, format_func=lambda p: f"{p['status']} — {p['product'].get('product_name') or '(unnamed)'} — {p['id'][:8]}")
left, right = st.columns(2)
with left:
    st.subheader("Issues")
    st.dataframe(selected["issues"], use_container_width=True)
    st.subheader("Evidence")
    st.dataframe(selected["evidence"], use_container_width=True)
    with st.expander("Source preview"):
        st.code(selected["source_preview"], language=None)
with right:
    st.subheader("Normalized record")
    edited = st.text_area("Edit JSON", value=json.dumps(selected["product"], indent=2), height=420)
    note = st.text_input("Reviewer note", value=selected.get("reviewer_note") or "")
    if st.button("Save corrections"):
        try:
            payload = {"product": json.loads(edited), "reviewer_note": note}
            response = httpx.patch(f"{API}/products/{selected['id']}", json=payload, timeout=8)
            response.raise_for_status()
            st.success("Saved and revalidated. Refresh to see the new status.")
        except Exception as exc:
            st.error(f"Could not save: {exc}")
    a, b = st.columns(2)
    if a.button("Approve", disabled=selected["status"] == "approved"):
        response = httpx.post(f"{API}/products/{selected['id']}/approve", timeout=8)
        st.success("Approved.") if response.is_success else st.error(response.text)
    if b.button("Reject", disabled=selected["status"] == "rejected"):
        response = httpx.post(f"{API}/products/{selected['id']}/reject", timeout=8)
        st.success("Rejected.") if response.is_success else st.error(response.text)
