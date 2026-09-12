# Business case: EK Product Intake Automation

## The manual problem

A supplier catalogue may contain tens or hundreds of SKUs. Category managers otherwise have to copy each row, normalize units and country names, check product identifiers, and separately track rows that are incomplete or contradictory. One bad row should not delay every clean SKU in the file.

## Proposed future workflow

A manager uploads one CSV or XLSX catalogue. The system processes every non-empty row independently through the same product checks, preserves the spreadsheet row number, and presents a batch summary. Clean products proceed straight through; problematic products enter the review queue; rows that cannot be ingested are shown as explicit failures.

## What automation does—and does not do

Automation converts spreadsheet rows into normalized product drafts, validates required information and EANs, normalizes values, and detects duplicates both against existing records and earlier rows in the same batch. It does not silently discard duplicates, guess through structural failures, or turn a reviewer correction into approval.

An optional LLM can still structure text through the existing provider boundary. Batch intake does not introduce new AI behavior or grounding claims.

## Human control and risks

A reviewer can inspect the original row-derived text, correct a ProductRecord, and then make a separate approve or reject decision. **Correction != approval.** Ingestion failures retain their row number and error message so the supplier file can be corrected.

Risks include incorrect supplier values, ambiguous columns, unexpectedly large files, and repeated submissions. The PoC uses synchronous processing and synthetic data. Production needs upload limits, idempotency, asynchronous processing, access controls, audit records, and monitoring.

## KPIs and assumptions

Useful batch KPIs include rows submitted, products created, ingestion failures, straight-through approvals, products ever requiring review, products currently waiting, products ready for approval, human approvals, and rejections. These distinguish operational throughput from data quality.

The configurable “manual minutes avoided” estimate remains illustrative and applies only to straight-through approvals. No synthetic result represents Eberlein und Kunz performance.

## PoC to production

**PoC:** demonstrate multi-SKU CSV/XLSX intake, row isolation, review routing, and historically correct counts.  
**MVP:** agree supplier templates, add file-size limits and idempotency, test with authorized data, and measure reviewer outcomes.  
**Production:** add identity, encrypted storage, managed persistence, background job processing, retries, audit logging, monitoring, and approved downstream integrations.
