import json
import os

import httpx
import streamlit as st

API = os.getenv("API_BASE_URL", "http://localhost:8000")
st.set_page_config(page_title="EK Intake Review", layout="wide")
st.title("EK Product Intake Automation")
st.caption("Synthetic-data-only internal operations PoC. Corrections and approvals remain separate decisions.")


def decision_label(product: dict) -> str:
    if product["status"] == "approved":
        return "auto-approved" if product["approval_source"] == "automatic" else "human-approved"
    return product["status"].replace("_", " ")


def get_json(path: str, **kwargs):
    response = httpx.get(f"{API}{path}", timeout=8, **kwargs)
    response.raise_for_status()
    return response.json()


def show_notice():
    notice = st.session_state.pop("workflow_notice", None)
    if notice:
        (st.success if notice["kind"] == "success" else st.warning)(notice["message"])


def overview_page():
    try:
        metrics = get_json("/metrics")
        batches = get_json("/batches")
    except Exception as exc:
        st.error(f"Could not reach API at {API}: {exc}")
        return

    st.subheader("Overview")
    columns = st.columns(5)
    columns[0].metric("Products", metrics["products_processed"])
    columns[1].metric("Straight-through", metrics["straight_through_approved"])
    columns[2].metric("Ever reviewed", metrics["ever_required_human_review"])
    columns[3].metric("Ready to approve", metrics["ready_for_approval"])
    columns[4].metric("Human-approved", metrics["human_approved"])
    st.caption(metrics["estimate_assumption"])
    st.metric("Supplier batches", len(batches))


def batches_page():
    st.subheader("Supplier batches")
    upload = st.file_uploader("Upload supplier catalogue", type=["csv", "xlsx"])
    if st.button("Process batch", disabled=upload is None):
        try:
            response = httpx.post(
                f"{API}/batches/upload",
                files={"file": (upload.name, upload.getvalue(), upload.type)},
                timeout=60,
            )
            response.raise_for_status()
            batch = response.json()
            st.session_state["workflow_notice"] = {
                "kind": "success",
                "message": f"Processed {batch['processed_rows']} of {batch['total_rows']} rows; {batch['failed_rows']} ingestion failures.",
            }
            st.rerun()
        except Exception as exc:
            st.error(f"Batch upload failed: {exc}")

    show_notice()
    try:
        batches = get_json("/batches")
    except Exception as exc:
        st.error(f"Could not load batches: {exc}")
        return
    if not batches:
        st.info("No supplier batches yet.")
        return

    st.dataframe(
        [
            {
                "filename": batch["source_name"],
                "uploaded": batch["created_at"],
                "status": batch["status"],
                "total": batch["total_rows"],
                "processed": batch["processed_rows"],
                "failed": batch["failed_rows"],
                "straight-through": batch["straight_through_approved"],
                "needs review": batch["currently_review_required"],
                "ready": batch["ready_for_approval"],
            }
            for batch in batches
        ],
        use_container_width=True,
    )

    batch_by_id = {batch["id"]: batch for batch in batches}
    batch_id = st.selectbox(
        "Batch detail",
        list(batch_by_id),
        format_func=lambda item: f"{batch_by_id[item]['source_name']} — {batch_by_id[item]['status']} — {item[:8]}",
    )
    batch = get_json(f"/batches/{batch_id}")
    summary = st.columns(6)
    summary[0].metric("Total rows", batch["total_rows"])
    summary[1].metric("Processed", batch["processed_rows"])
    summary[2].metric("Failed", batch["failed_rows"])
    summary[3].metric("Straight-through", batch["straight_through_approved"])
    summary[4].metric("Needs review", batch["currently_review_required"])
    summary[5].metric("Ready", batch["ready_for_approval"])

    if batch["row_errors"]:
        st.subheader("Ingestion failures")
        st.dataframe(batch["row_errors"], use_container_width=True)

    products = get_json(f"/batches/{batch_id}/products")
    st.subheader("Products")
    st.dataframe(
        [
            {
                "row": product["source_row_number"],
                "product": product["product"].get("product_name"),
                "decision": decision_label(product),
                "issues": len(product["issues"]),
                "ean": product["product"].get("ean"),
            }
            for product in products
        ],
        use_container_width=True,
    )
    if products:
        product_by_id = {product["id"]: product for product in products}
        product_id = st.selectbox(
            "Select product",
            list(product_by_id),
            format_func=lambda item: f"row {product_by_id[item]['source_row_number']} — {decision_label(product_by_id[item])} — {product_by_id[item]['product'].get('product_name') or '(unnamed)'}",
        )
        if st.button("Open selected product in Review Queue"):
            st.session_state["review_product_id"] = product_id
            st.session_state["review_status_filter"] = "all"
            st.session_state["navigate_to"] = "Review Queue"
            st.rerun()


def review_queue_page():
    st.subheader("Review Queue")
    show_notice()
    statuses = ["all", "review_required", "ready_for_approval", "approved", "rejected"]
    status = st.selectbox("Filter", statuses, key="review_status_filter")
    params = {} if status == "all" else {"status": status}
    try:
        products = get_json("/products", params=params)
    except Exception as exc:
        st.error(f"Could not load products: {exc}")
        return
    if not products:
        st.info("No products for this filter.")
        return

    product_by_id = {product["id"]: product for product in products}
    target_id = st.session_state.pop("review_product_id", None)
    index = list(product_by_id).index(target_id) if target_id in product_by_id else 0
    selected_id = st.selectbox(
        "Product",
        list(product_by_id),
        index=index,
        format_func=lambda item: f"{decision_label(product_by_id[item])} — {product_by_id[item]['product'].get('product_name') or '(unnamed)'} — {item[:8]}",
    )
    selected = product_by_id[selected_id]
    provenance = f"Batch {selected['batch_id'][:8]}, row {selected['source_row_number']}" if selected["batch_id"] else "Single-product intake"
    st.info(f"Decision: **{decision_label(selected)}** · {provenance} · Corrections: **{selected['correction_count']}**")

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
                response = httpx.patch(
                    f"{API}/products/{selected_id}",
                    json={"product": json.loads(edited), "reviewer_note": note},
                    timeout=8,
                )
                response.raise_for_status()
                saved = response.json()
                if saved["status"] == "ready_for_approval":
                    message = "Corrections passed validation. Explicit approval is still required."
                    kind = "success"
                else:
                    message = "Corrections saved; blocking validation issues remain."
                    kind = "warning"
                st.session_state["workflow_notice"] = {"kind": kind, "message": message}
                st.session_state["review_product_id"] = selected_id
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save: {exc}")

        approve, reject = st.columns(2)
        if approve.button("Approve", disabled=selected["status"] != "ready_for_approval"):
            response = httpx.post(f"{API}/products/{selected_id}/approve", timeout=8)
            if response.is_success:
                st.session_state["workflow_notice"] = {"kind": "success", "message": "Human approval recorded."}
                st.session_state["review_product_id"] = selected_id
                st.rerun()
            else:
                st.error(response.text)

        if reject.button("Reject", disabled=selected["status"] == "rejected"):
            response = httpx.post(f"{API}/products/{selected_id}/reject", timeout=8)
            if response.is_success:
                st.session_state["workflow_notice"] = {"kind": "success", "message": "Product rejected."}
                st.session_state["review_product_id"] = selected_id
                st.rerun()
            else:
                st.error(response.text)


pages = ["Overview", "Batches", "Review Queue"]
requested_page = st.session_state.pop("navigate_to", None)
if requested_page:
    st.session_state["navigation"] = requested_page
page = st.sidebar.radio("Navigation", pages, key="navigation")

if page == "Overview":
    overview_page()
elif page == "Batches":
    batches_page()
else:
    review_queue_page()
