# EK Product Intake Automation

> **Independent case-study prototype.** This project is inspired by the publicly described responsibilities of an AI & Automation working-student role at Eberlein und Kunz. It does not use or represent internal Eberlein und Kunz data or systems.

An end-to-end, local-first PoC for turning heterogeneous supplier product information into reviewable, normalized product records. It demonstrates a practical automation principle: **automate safe, repetitive work and send uncertainty to people.** All included data is synthetic.

## Why this exists

Supplier product data often arrives as spreadsheets, PDFs, and free text. Normalizing it manually is slow and error-prone. This prototype parses these inputs, uses an interchangeable extraction provider, applies deterministic business rules, and either auto-approves a record or makes it visible in a small review queue.

## Architecture at a glance

`n8n / supplier input → FastAPI → parser → extraction provider → deterministic validation → SQLite → Streamlit review / export-ready JSON`

Python is used for document handling, validation, and the API; n8n is the orchestration boundary that can connect inbound webhooks and downstream systems without embedding integration logic in the application. The optional OpenAI-compatible provider is isolated behind an interface; no LLM decision overrides deterministic rules.

## Run locally

```bash
copy .env.example .env
docker compose up --build
```

Open the API documentation at http://localhost:8000/docs, the review app at http://localhost:8501, and n8n at http://localhost:5678; import `n8n/product_intake_workflow.json` into n8n. The default `mock` provider requires no key. Alternatively, without Docker:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
streamlit run review_ui/app.py
```

Submit demo data:

```bash
curl -X POST http://localhost:8000/products -H "Content-Type: application/json" -d @sample_data/clean_product.json
python -m evals.evaluate
pytest -q
```

Files can be uploaded to `POST /products/upload` (CSV, XLSX, PDF, TXT). Plain text and structured submissions use `POST /products`. The generated `n8n/product_intake_workflow.json` imports into a local n8n instance.

## Safety and decision logic

Only initially clean products with every required field, a valid EAN, no conflicts or duplicates, and no validation errors are approved automatically. Missing data, invalid codes, source conflicts, extraction failures, or food records without ingredients/allergens require review.

For escalated records, **correction != approval**. Saving a correction reruns deterministic validation. Remaining errors keep the record in `review_required`; a valid corrected record becomes `ready_for_approval`. It becomes `approved` only after the reviewer calls the approval endpoint. The application records whether approval was straight-through or human-made, so **straight-through automated approval != human-reviewed approval**.

Confidence is *not* a sole approval criterion. The mock provider sets confidence to `1.0` only when a field was directly labelled in the source; absent values mean the parser cannot substantiate a confidence. See [docs/architecture.md](docs/architecture.md).

## Evaluation and metrics

`evals/evaluate.py` benchmarks the mock provider against synthetic ground truth. It reports extraction and normalization accuracy, validation detection, review and approval rates, false auto-approval rate, and latency. These are **synthetic benchmark metrics**, not Eberlein und Kunz results.

`/metrics` distinguishes straight-through approvals from human approvals and uses persisted history for the historical review rate. The time-saving estimate applies only to straight-through records and remains a clearly labelled configurable assumption.

## Schema update for existing local databases

This PoC intentionally has no migration framework. The decision-history fields change the SQLite schema, so an existing local demo database must be recreated.

- Local run: stop the app and delete `ek_intake.db`; the next startup recreates it.
- Docker run: `docker compose down -v` removes the disposable SQLite and n8n demo volumes; then run `docker compose up --build`.

Both operations delete existing PoC records. Export anything you want to keep first.

## Limitations and production path

This deliberately excludes authentication, queues, malware scanning, enterprise integrations, and production observability. A production version needs SSO/RBAC, encrypted object storage, audit trails, virus scanning, rate limits, retries and queues, privacy-approved LLM processing, prompt-injection defences, monitoring, and a managed database. See [docs/business_case.md](docs/business_case.md) and [docs/demo_script.md](docs/demo_script.md).
