# Five-minute interview demo

## 0:00–0:30 — The business problem

“Suppliers send catalogues with many SKUs. The goal is to automate safe rows, isolate bad rows, and preserve human control. This independent demo uses synthetic data only.”

## 0:30–1:30 — Upload a supplier catalogue

Open the Streamlit **Batches** page and upload `sample_data/supplier_catalogue_demo.csv`, or use:

```powershell
curl.exe -X POST http://localhost:8000/batches/upload -F "file=@sample_data/supplier_catalogue_demo.csv"
```

Show the batch totals: non-empty rows, ProductRecords created, ingestion failures, straight-through approvals, and review-required products. Point out that the empty spreadsheet row is ignored and failed rows retain their source row number.

## 1:30–2:15 — Inspect clean automation

Open a straight-through product from the batch. Show `1 kg → 1000 g` or `Deutschland → DE`, its spreadsheet row provenance, and automatic approval attribution.

## 2:15–3:15 — Inspect an exception

Open the invalid-EAN or incomplete-food product. Show the original labelled row text, deterministic validation issues, and `review_required`. Also show the within-batch duplicate: it is retained and escalated rather than silently dropped.

## 3:15–4:15 — Correct, then explicitly approve

Correct all blocking fields and select **Save corrections**. The record becomes `ready_for_approval`, not approved. State: **correction != approval**. Then press **Approve** and show `approval_source: human`.

## 4:15–4:45 — Historically correct metrics

Return to the batch and Overview pages. The product still counts under `ever_required_human_review`, now counts as `human_approved`, and never counts as `straight_through_approved`.

## 4:45–5:00 — Production boundary

Close with the deliberate PoC limits: synchronous processing, one worksheet, and UTF-8 CSV. Production would add bounded uploads, idempotency, background jobs, security controls, audit trails, and monitoring.
