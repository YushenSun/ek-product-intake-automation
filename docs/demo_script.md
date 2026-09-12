# Five-minute interview demo

## 0:00–0:30 — The business problem and boundaries

“Suppliers send catalogues with many SKUs. The goal is to automate safe rows, isolate bad rows, and preserve human control. n8n orchestrates integrations, FastAPI owns every business rule, and Streamlit is the human-review surface. This independent demo uses synthetic data only.”

## 0:30–1:30 — Send a supplier spreadsheet through n8n

Start the Compose stack, import `n8n/batch_product_intake_workflow.json`, select **Supplier spreadsheet webhook**, and choose **Listen for test event**. Then run:

```powershell
curl.exe -X POST "http://localhost:5678/webhook-test/ek-batch-intake" `
  -F "file=@sample_data/supplier_catalogue_demo.csv"
```

Show the n8n execution. Point out the internal container URL `http://backend:8000/batches/upload` and the returned batch ID/status. The workflow also retrieves the batch products and builds one structured summary.

The synthetic catalogue contains both review cases and ingestion failures, so **Human review involved?** and **Partial ingestion errors?** can both take their true branches. This is deliberate: the workflow does not hide one condition behind another.

## 1:30–2:10 — Explain the orchestration boundary

Open **Build outcome summary**. It only reads FastAPI fields such as `failed_rows`, `ever_required_human_review`, `currently_review_required`, `ready_for_approval`, and returned product statuses.

State clearly:

- n8n receives, forwards, routes, and prepares integration payloads;
- FastAPI parses, extracts, normalizes, validates, detects duplicates, persists, and decides product status;
- the generic success/review/error nodes use no external credentials.

A clean-only supplier batch would take **Automatic success placeholder** when both failed rows and historical review count are zero.

## 2:10–2:50 — Inspect batch results in Streamlit

Open http://localhost:8501 and select **Batches**. Show total rows, ProductRecords created, ingestion failures, straight-through approvals, and review-required products. Point out that the empty spreadsheet row is ignored and failed rows retain their source row number.

Open a straight-through product and show `1 kg → 1000 g` or `Deutschland → DE`, its spreadsheet row provenance, and automatic approval attribution.

## 2:50–3:30 — Inspect an exception

Open the invalid-EAN, incomplete-food, or duplicate product. Show the original labelled row text, deterministic validation issues, and `review_required`. The within-batch duplicate is retained and escalated rather than silently dropped.

Also show the batch ingestion errors in Streamlit or the n8n response's `row_errors`.

## 3:30–4:20 — Correct, then explicitly approve

Correct all blocking fields and select **Save corrections**. Deterministic validation reruns and the record becomes `ready_for_approval`, not approved. State: **correction != approval**.

Then press **Approve** and show `approval_source: human`. n8n did not perform this decision.

## 4:20–4:45 — Historically correct metrics

Return to the batch and Overview pages. The product still counts under `ever_required_human_review`, now counts as `human_approved`, and never counts as `straight_through_approved`.

Explain that straight-through automated approval and human-reviewed approval are distinct business outcomes.

## 4:45–5:00 — Production continuation

Show the three credential-free placeholder nodes. In production:

- the review placeholder becomes an approved Teams/email/ticket connector;
- the ingestion alert becomes operational monitoring or supplier remediation;
- after explicit approval, an approved downstream workflow can call `GET /products/{id}/export` and write to a PIM, ERP, or catalogue system.

Close with the deliberate PoC limits: synchronous processing, no authentication, no production retries, one XLSX worksheet, UTF-8 CSV, and an unpinned n8n image pending real compatibility validation.
