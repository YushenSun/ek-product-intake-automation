# Business case: EK Product Intake Automation

## The manual problem

When supplier product information arrives in different layouts, a category manager has to read a file, copy values into a target format, notice omissions, and check basic data quality. The costly part is not only typing: it is deciding whether the data is trustworthy enough to publish or hand downstream.

## Proposed future workflow

The supplier file enters a small automated intake flow. It creates a common product record, applies the same basic checks every time, and separates clean records from records that need attention. A manager sees only exceptions with the original source, the extracted values, and the reasons for review.

## What AI does—and does not do

An optional LLM can turn unstructured wording into a structured draft. Deterministic code still checks EAN checksums, mandatory information, units, currencies, prices, food fields, conflicts, and duplicates. AI does **not** approve a product on its own, resolve contradictory supplier claims silently, or replace category-manager judgment.

## Human control and risks

People can correct, approve, or reject every exception. The design treats missing, invalid, conflicting, or failed extraction as a review item. Risks include wrong extraction, misleading source documents, private supplier data, and integration failures. The PoC limits risk by using synthetic data, explicit validation, no automatic override of errors, and an offline mock provider.

## KPIs and assumptions

Measure the share of records automatically approved, review rate, issue count, processing latency, reviewer correction rate, and false auto-approval rate. The app offers an illustrative “manual minutes avoided” total, based on a configurable assumption (default six minutes per safely auto-approved record). This is not a claim about actual EK workflows, costs, or productivity.

## PoC to production

**PoC:** validate workflow, rule coverage, and reviewer usability on synthetic examples.  
**MVP:** pilot with authorized supplier data, agreed field rules, user feedback, and monitored outcomes.  
**Production:** integrate identity, ERP/PIM destinations, encrypted storage, audit logging, queues/retries, monitoring, and a privacy/security review for any LLM provider.
