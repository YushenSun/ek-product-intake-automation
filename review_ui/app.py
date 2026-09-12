import json
import os

import httpx
import streamlit as st

API = os.getenv("API_BASE_URL", "http://localhost:8000")
st.set_page_config(page_title="EK Intake Review", layout="wide")
st.title("EK Product Intake — review queue")
st.caption("Synthetic-data-only PoC. Correction does not equal approval; reviewed records require an explicit approval decision.")


def decision_label(product: dict) -> str:
    if product["status"] == "approved":
        return "auto-approved" if product["approval_source"] == "automatic" else "human-approved"
    return product["status"].replace("_", " ")


try:
    metrics = httpx.get(f"{API}/metrics", timeout=5).json()
    cols = st.columns(5)
    cols[0].metric("Processed", metrics["products_processed"])
    cols[1].metric("Straight-through", metrics["straight_through_approved"])
    cols[2].metric("Needs review", metrics["currently_waiting_for_review"])
    cols[3].metric("Ready to approve", metrics["ready_for_approval"])
    cols[4].metric("Human-approved", metrics["human_approved"])
except Exception as exc:
    st.error(f"Could not reach API at {API}: {exc}")
    st.stop()

status = st.selectbox("Filter", ["all", "review_required", "ready_for_approval", "approved", "rejected"])
params = {} if status == "all" else {"status": status}
products = httpx.get(f"{API}/products", params=params, timeout=5).json()
if not products:
    st.info("No submissions for this filter. Use the API docs or send sample_data/clean_product.json.")
    st.stop()

selected = st.selectbox(
    "Product",
    products,
    format_func=lambda product: f"{decision_label(product)} — {product['product'].get('product_name') or '(unnamed)'} — {product['id'][:8]}",
)
st.info(f"Decision: **{decision_label(selected)}** · Corrections saved: **{selected['correction_count']}**")

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
            saved = response.json()
            if saved["status"] == "ready_for_approval":
                st.success("Corrections saved and validation passed. The product is ready for explicit approval.")
            else:
                st.warning("Corrections saved and validation rerun. Blocking issues remain.")
        except Exception as exc:
            st.error(f"Could not save: {exc}")

    approve, reject = st.columns(2)
    can_approve = selected["status"] == "ready_for_approval"
    if approve.button("Approve", disabled=not can_approve, help="Available only after corrections pass validation."):
        response = httpx.post(f"{API}/products/{selected['id']}/approve", timeout=8)
        st.success("Human approval recorded.") if response.is_success else st.error(response.text)

    if reject.button("Reject", disabled=selected["status"] == "rejected"):
        response = httpx.post(f"{API}/products/{selected['id']}/reject", timeout=8)
        st.success("Rejected.") if response.is_success else st.error(response.text)
