# EK Product Intake Automation

> **Independent case-study prototype.** This project is inspired by the publicly described responsibilities of an AI & Automation working-student role at Eberlein und Kunz. It does not use or represent internal Eberlein und Kunz data or systems.

An end-to-end, local-first PoC for turning heterogeneous supplier product information into reviewable, normalized product records. It demonstrates a practical automation principle: **automate safe, repetitive work and send uncertainty to people.** All included data is synthetic.

## Why this exists

A supplier catalogue commonly contains tens or hundreds of SKUs, while product information also arrives as PDFs or free text. Copying and normalizing every row manually is slow and error-prone. This prototype parses every usable CSV/XLSX row independently, applies the existing extraction and validation pipeline, and isolates failures without losing the rest of the batch.

## Architecture at a glance

`supplier spreadsheet → n8n webhook/orchestration → FastAPI batch intake → per-product extraction and deterministic validation → SQLite → Streamlit human review`

Responsibilities stay deliberately separate:

- **n8n = orchestration and integration boundaries.** It receives the file, forwards it, inspects backend results, and emits credential-free success/review/error payloads.
- **FastAPI = business logic and source of truth.** It owns parsing, extraction, normalization, validation, duplicates, approval state, persistence, and metrics.
- **Streamlit = human review.** It supports correction followed by a separate explicit approve or reject decision.

n8n never independently validates or approves a product. The optional OpenAI-compatible provider remains isolated behind an interface; the default deterministic mock provider requires no key.

## Run locally

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open:

- FastAPI documentation: http://localhost:8000/docs
- Streamlit operations app: http://localhost:8501
- n8n: http://localhost:5678

Without Docker:

```powershell
conda create -n ek-intake python=3.12 -y
conda activate ek-intake
python -m pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

In another shell:

```powershell
conda activate ek-intake
streamlit run review_ui/app.py
```

## n8n batch automation demo

Import `n8n/batch_product_intake_workflow.json` in n8n. For a test execution, select **Supplier spreadsheet webhook**, choose **Listen for test event**, and run:

```powershell
curl.exe -X POST "http://localhost:5678/webhook-test/ek-batch-intake" `
  -F "file=@sample_data/supplier_catalogue_demo.csv"
```

After activating the workflow, use the production webhook path:

```powershell
curl.exe -X POST "http://localhost:5678/webhook/ek-batch-intake" `
  -F "file=@sample_data/supplier_catalogue_demo.csv"
```

The incoming multipart field name must be `file`. n8n forwards that binary field to `http://backend:8000/batches/upload`, fetches the created batch products, and returns a structured response containing the batch ID, status, counts, products needing attention, row errors, and independent outcome flags.

The included catalogue deliberately triggers human-review and partial-error branches at the same time. See [docs/n8n_demo.md](docs/n8n_demo.md) for the interview-ready walkthrough.

## Direct supplier batch demo

FastAPI can also be called directly:

```powershell
curl.exe -X POST http://localhost:8000/batches/upload -F "file=@sample_data/supplier_catalogue_demo.csv"
curl.exe http://localhost:8000/batches
curl.exe http://localhost:8000/metrics
```

Each non-empty spreadsheet row retains its original row number. Structurally malformed rows and extraction failures are stored as batch row errors; other rows continue. Every successful row calls the same `IntakeService` used by single-product endpoints, so normalization, validation, database duplicate checks, within-batch duplicate checks, and the human-review state machine are not duplicated.

Existing `POST /products` and `POST /products/upload` behavior remains available. Single spreadsheet uploads continue to process the first usable product, while `POST /batches/upload` is the explicit multi-product endpoint.

## Batch API

- `POST /batches/upload` — synchronously process a CSV or XLSX catalogue.
- `GET /batches` — list persisted batches with live decision counts.
- `GET /batches/{batch_id}` — retrieve one batch, including row ingestion errors.
- `GET /batches/{batch_id}/products` — list its products with source row provenance.

Batch statistics keep `ready_for_approval` separate from final approval and reuse persisted decision history. A human-approved product remains part of `ever_required_human_review` and never becomes straight-through.

## Safety and decision logic

Only initially clean products with all required fields, a valid EAN, no conflicts or duplicates, and no validation errors are approved automatically. A duplicate row still becomes a ProductRecord, normally with `review_required`; it is not silently discarded.

For escalated records, **correction != approval**. Saving a correction reruns deterministic validation. Remaining errors keep the record in `review_required`; a valid corrected record becomes `ready_for_approval`. It becomes `approved` only after the reviewer calls the approval endpoint. Therefore **straight-through automated approval != human-reviewed approval**.

## Evaluation, metrics, and tests

`evals/evaluate.py` remains the synthetic single-product benchmark. `/metrics` distinguishes straight-through approvals from human approvals and uses persisted history for the historical review rate. Batch endpoints expose the same attribution within each supplier file.

Run the complete offline suite with a repository-local pytest temp directory on Windows:

```powershell
python -m pytest -q --basetemp .pytest_tmp
```

The tests include structural checks for the importable n8n JSON and transaction-level isolation when one extraction call fails between successful spreadsheet rows.

## Schema update for existing local databases

This PoC intentionally has no migration framework. Task 2 added the `batches` table plus nullable `batch_id` and `source_row_number` product columns. An older local demo database must be recreated.

- Local run: stop the app and delete `ek_intake.db`; the next startup recreates it.
- Docker run: `docker compose down -v` removes disposable demo volumes; then run `docker compose up --build`.

Both operations delete existing PoC records. Export anything you want to keep first. Task 3 adds no database schema changes.

## Limitations and production path

Batch processing is synchronous and uses the active worksheet only. CSV input is UTF-8. The n8n placeholders do not send real messages or publish data downstream, and the workflow uses n8n's default fail-fast HTTP behavior rather than a production retry policy.

The Compose file retains the repository's existing `n8nio/n8n:latest` tag because Docker was unavailable in the implementation environment, so a different release could not be validated honestly. Before production, validate the workflow against an approved n8n release and pin that version or digest. Production also needs bounded uploads, idempotency, background jobs, authentication, authorization, secret management, audit events, retry/alert policies, observability, and an approved downstream connector.

See [docs/business_case.md](docs/business_case.md), [docs/architecture.md](docs/architecture.md), [docs/demo_script.md](docs/demo_script.md), and [docs/n8n_demo.md](docs/n8n_demo.md).
