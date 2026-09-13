# n8n batch-intake demo

This walkthrough demonstrates n8n as an orchestration layer around the existing FastAPI batch pipeline. It uses only synthetic data and requires no Teams, Slack, email, ERP, PIM, or marketplace credentials.

## Responsibilities

- **n8n:** receives a supplier file, forwards it to FastAPI, reads the returned batch/products, exposes independent outcome routes, and returns a concise webhook response.
- **FastAPI:** owns parsing, extraction, normalization, validation, duplicate detection, persistence, batch metrics, and all approval state.
- **Streamlit:** provides the human-review queue and explicit correction/approve/reject controls.

n8n never decides that a product is valid and never approves a product.

## 1. Start the local stack

From the repository root:

```powershell
cd D:\Coding\codex\EK
Copy-Item .env.example .env -ErrorAction SilentlyContinue
docker compose up --build
```

Wait until the backend is available:

```powershell
curl.exe http://localhost:8000/health
```

Open:

- n8n: http://localhost:5678
- Streamlit: http://localhost:8501
- FastAPI docs: http://localhost:8000/docs

A new n8n volume may show the one-time local owner setup screen. Complete that local setup; no external integration credentials are needed.

## 2. Import the workflow

In n8n:

1. Open **Workflows**.
2. Choose **Import from File**.
3. Select `n8n/batch_product_intake_workflow.json`.
4. Open the imported **EK Batch Product Intake Orchestration** workflow.

The required incoming multipart field name is exactly `file`. Both CSV and XLSX use this same field because FastAPI detects the filename extension.

## 3. Understand the node flow

The main path is:

```text
Supplier spreadsheet webhook
→ Validate incoming file
→ Upload batch to FastAPI
→ Validate batch response
→ Fetch batch products
→ Build outcome summary
```

**Build outcome summary** fans out to four paths:

- **Clean straight-through? → Automatic success placeholder**
- **Human review involved? → Review notification placeholder**
- **Partial ingestion errors? → Ingestion alert placeholder**
- **Return batch outcome**

The review and partial-error checks run independently, so both can be true for one batch. The webhook response always contains all applicable outcome flags, even though the three placeholder nodes visually demonstrate separate future integrations.

## 4. Run the test webhook

Select **Supplier spreadsheet webhook**, choose **Listen for test event**, then run this in a second PowerShell window:

```powershell
cd D:\Coding\codex\EK
curl.exe -X POST "http://localhost:5678/webhook-test/ek-batch-intake" `
  -F "file=@sample_data/supplier_catalogue_demo.csv"
```

The expected response contains fields shaped like:

```json
{
  "batch_id": "...",
  "filename": "supplier_catalogue_demo.csv",
  "batch_status": "completed_with_errors",
  "failed_rows": 2,
  "status_counts": {
    "straight_through_approved": 6,
    "ever_required_human_review": 6,
    "currently_review_required": 6,
    "ready_for_approval": 0,
    "human_approved": 0,
    "rejected": 0
  },
  "outcomes": {
    "clean_straight_through": false,
    "human_review": true,
    "partial_ingestion_errors": true
  },
  "products_needing_attention": [
    {"id": "...", "status": "review_required", "source_row_number": 4}
  ],
  "row_errors": [
    {"row_number": 9, "code": "extractionprovidererror", "message": "..."}
  ],
  "review_ui_url": "http://localhost:8501"
}
```

The numeric examples above are illustrative; use the actual returned values. With the included catalogue, expect both human-review and ingestion-error outcomes because it deliberately contains invalid/missing data, a duplicate, malformed price, and a structurally malformed row.

Inspect the n8n execution data for:

- the FastAPI batch ID and status;
- backend-derived counts;
- products with `review_required` or `ready_for_approval`;
- persisted row-level ingestion errors;
- both applicable placeholder branches.

## 5. Activate the production webhook path

For a reusable local webhook, activate the workflow and call:

```powershell
curl.exe -X POST "http://localhost:5678/webhook/ek-batch-intake" `
  -F "file=@sample_data/supplier_catalogue_demo.csv"
```

The `webhook-test` URL works only while n8n is listening for a test event. The `webhook` URL requires the workflow to be active.

## 6. Review and approve a product

Open http://localhost:8501:

1. Select **Batches** and choose the returned batch.
2. Inspect straight-through products, review-required products, and ingestion failures.
3. Open a problematic product in **Review Queue**.
4. Correct all blocking fields.
5. Choose **Save corrections**.
6. Verify it becomes `ready_for_approval`, not `approved`.
7. Choose **Approve**.
8. Verify it becomes human-approved.

This demonstrates **correction != approval** and **straight-through automated approval != human-reviewed approval**.

## 7. Failure behavior

The workflow fails visibly when:

- the multipart `file` field is missing;
- the uploaded filename is not CSV/XLSX;
- FastAPI returns a 4xx or 5xx response;
- the backend is unavailable or times out;
- FastAPI returns a successful HTTP status with an invalid batch payload;
- fetching batch products fails.

The HTTP nodes use n8n's normal stop-on-error behavior. They are not configured to continue and manufacture a success response. Production should add an organization-approved retry policy, alert destination, idempotency key, and dead-letter/remediation process.

## 8. Networking

Inside Compose, n8n and Streamlit call:

```text
http://backend:8000
```

The browser and PowerShell commands use localhost because they run outside the Compose network:

```text
http://localhost:5678
http://localhost:8501
http://localhost:8000
```

No `host.docker.internal` dependency remains in the workflow.

## 9. Production continuation

The three Edit Fields nodes are credential-free integration seams:

- **Automatic success placeholder:** replace with an approved catalogue-publication or monitoring event.
- **Review notification placeholder:** replace with an approved ticket, Teams, email, or operations-queue connector.
- **Ingestion alert placeholder:** replace with supplier remediation and operational alerting.

After explicit approval, a small downstream workflow could receive an approved product ID, call `GET http://backend:8000/products/{id}/export`, and deliver the export-ready JSON to an approved PIM, ERP, or catalogue API. This repository intentionally does not perform that external write.

## 10. Validated local runtime

The full local Docker demo was validated with `n8nio/n8n:2.38.7`: multipart CSV upload, batch processing, review and row-error routing, and correction → ready for approval → explicit approval. Compose uses `N8N_WEBHOOK_URL=http://localhost:5678/` for the local browser-facing webhook URL. Production deployment still requires its own security and operational validation.
