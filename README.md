# EK Product Intake Automation

> **Independent case-study prototype.** This project is inspired by the publicly described responsibilities of an AI & Automation working-student role at Eberlein und Kunz. It does not use or represent internal Eberlein und Kunz data or systems.

An end-to-end, local-first PoC for turning heterogeneous supplier product information into reviewable, normalized product records. It demonstrates a practical automation principle: **automate safe, repetitive work and send uncertainty to people.** All included data is synthetic.

## Why this exists

A supplier catalogue commonly contains tens or hundreds of SKUs, while product information also arrives as PDFs or free text. Copying and normalizing every row manually is slow and error-prone. This prototype parses every usable CSV/XLSX row independently, applies the existing extraction and validation pipeline, and isolates failures without losing the rest of the batch.

## Architecture at a glance

`supplier input → FastAPI → document/batch parser → per-product extraction → deterministic validation → SQLite → Streamlit operations and review`

Python owns document handling, validation, persistence, and the API. The optional OpenAI-compatible provider remains isolated behind an interface; the default deterministic mock provider requires no key. n8n remains an optional orchestration boundary and is not part of the batch-processing implementation.

## Run locally

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open the API documentation at http://localhost:8000/docs, the operations app at http://localhost:8501, and n8n at http://localhost:5678. Without Docker:

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

## Supplier batch demo

Upload the synthetic 14-row supplier catalogue:

```powershell
curl.exe -X POST http://localhost:8000/batches/upload -F "file=@sample_data/supplier_catalogue_demo.csv"
```

Then inspect:

```powershell
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

Batch statistics keep `ready_for_approval` separate from final approval and reuse Task 1 history fields. A human-approved product remains part of `ever_required_human_review` and never becomes straight-through.

## Safety and decision logic

Only initially clean products with all required fields, a valid EAN, no conflicts or duplicates, and no validation errors are approved automatically. A duplicate row still becomes a ProductRecord, normally with `review_required`; it is not silently discarded.

For escalated records, **correction != approval**. Saving a correction reruns deterministic validation. Remaining errors keep the record in `review_required`; a valid corrected record becomes `ready_for_approval`. It becomes `approved` only after the reviewer calls the approval endpoint. Therefore **straight-through automated approval != human-reviewed approval**.

## Evaluation, metrics, and tests

`evals/evaluate.py` remains the synthetic single-product benchmark. `/metrics` distinguishes straight-through approvals from human approvals and uses persisted history for the historical review rate. Batch endpoints expose the same attribution within each supplier file.

Run the complete offline suite with a repository-local pytest temp directory on Windows:

```powershell
python -m pytest -q --basetemp .pytest_tmp
```

## Schema update for existing local databases

This PoC intentionally has no migration framework. Task 2 adds the `batches` table plus nullable `batch_id` and `source_row_number` product columns. An existing local demo database must be recreated.

- Local run: stop the app and delete `ek_intake.db`; the next startup recreates it.
- Docker run: `docker compose down -v` removes disposable demo volumes; then run `docker compose up --build`.

Both operations delete existing PoC records. Export anything you want to keep first.

## Limitations and production path

Batch processing is intentionally synchronous and uses the active worksheet only. CSV input is UTF-8. A production version needs bounded upload sizes, asynchronous job execution for large catalogues, SSO/RBAC, encrypted storage, audit events, malware scanning, rate limits, retries, observability, and a managed database. See [docs/business_case.md](docs/business_case.md), [docs/architecture.md](docs/architecture.md), and [docs/demo_script.md](docs/demo_script.md).
