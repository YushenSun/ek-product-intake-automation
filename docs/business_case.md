# Business case: EK Product Intake Automation

## The manual problem

A supplier catalogue may contain tens or hundreds of SKUs. Category managers otherwise have to copy each row, normalize units and country names, check product identifiers, and separately track rows that are incomplete or contradictory. One bad row should not delay every clean SKU in the file.

## Proposed workflow

A supplier system or operator sends one CSV/XLSX catalogue to an n8n webhook. n8n forwards the unchanged binary file to FastAPI, which processes every non-empty row independently through the product pipeline and persists the batch. n8n then reads the backend result and exposes all applicable outcomes:

- clean straight-through processing;
- products that require or historically required human review;
- row-level ingestion failures.

The last two outcomes are not mutually exclusive. An operations reviewer opens Streamlit, corrects a problematic record, and separately approves or rejects it.

## Clear ownership

- **n8n = orchestration / integrations:** inbound webhook, multipart forwarding, outcome routing, generic notification payloads, and the future downstream boundary.
- **FastAPI = business logic:** parsing, extraction, normalization, validation, duplicates, approval state, historical attribution, persistence, and metrics.
- **Streamlit = human review:** correction, issue inspection, explicit approval, and rejection.

n8n does not decide whether product data is valid and does not approve products. This keeps business rules testable in Python and prevents workflow nodes from drifting away from API behavior.

## What automation does—and does not do

Automation converts spreadsheet rows into normalized product drafts, validates required information and EANs, normalizes values, and detects duplicates both against existing records and earlier rows in the same batch. It does not silently discard duplicates, guess through structural failures, or turn a reviewer correction into approval.

An optional LLM can still structure text through the existing provider boundary. This n8n work introduces no new AI behavior or grounding claims.

## Human control and risks

A reviewer can inspect the original row-derived text, correct a ProductRecord, and then make a separate approve or reject decision. **Correction != approval.** Ingestion failures retain their row number and error message so the supplier file can be corrected.

Risks include incorrect supplier values, ambiguous columns, unexpectedly large files, repeated submissions, webhook abuse, unavailable dependencies, and failed downstream delivery. The PoC uses synchronous processing, synthetic data, credential-free placeholder notifications, and fail-fast HTTP behavior. Production needs authentication, upload limits, idempotency, asynchronous processing, access controls, audit records, managed credentials, retry policies, alerting, and monitoring.

## KPIs and assumptions

Useful batch KPIs include rows submitted, products created, ingestion failures, straight-through approvals, products ever requiring review, products currently waiting, products ready for approval, human approvals, and rejections. n8n transports and routes these backend-owned metrics; it does not recalculate product validity.

The configurable “manual minutes avoided” estimate remains illustrative and applies only to straight-through approvals. No synthetic result represents Eberlein und Kunz performance.

## PoC to production

**PoC:** demonstrate webhook-driven multi-SKU CSV/XLSX intake, row isolation, review routing, visible partial failures, and historically correct counts.  
**MVP:** agree supplier templates, authenticate callers, validate and pin n8n, add file-size limits and idempotency, replace generic notification fields with an approved ticket/email connector, and measure reviewer outcomes.  
**Production:** add encrypted durable storage, managed persistence, background processing, secret rotation, retries with dead-letter handling, audit logging, monitoring, and approved PIM/ERP/catalogue integrations.

The workflow's generic success, review, and ingestion-alert nodes mark integration seams. After an explicit human approval, a production flow could call the existing export-ready product endpoint and deliver the returned JSON to an approved downstream system; this PoC intentionally stops before that external write.
