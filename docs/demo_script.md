# Five-minute interview demo

## 0:00–0:30 — The business problem

“Supplier product data arrives as prose and spreadsheets. The repetitive work is not just copying: it is normalizing and deciding which records are safe. This independent demo uses synthetic data only.”

## 0:30–1:00 — Architecture

Show `docs/architecture.md`. Explain parser → extraction → deterministic checks → SQLite → review queue. Point out that n8n handles workflow integration while the Python service owns domain rules, and that the mock provider makes the demo reliable with no API key.

## 1:00–3:00 — Submit two products

Start the stack, open `/docs` and the Streamlit app. Post `sample_data/clean_product.json` to `POST /products`. Show its normalized `0.25 kg → 250 g`, `Deutschland → DE`, valid EAN, and straight-through approved status. Then post `sample_data/problem_product.json`. Highlight invalid EAN, zero price, and missing food information: it becomes `review_required`, rather than being silently accepted.

## 3:00–4:00 — Human review

In Streamlit filter for `review_required`. Show source preview, evidence, and issue list. Edit the JSON to provide a valid EAN, positive price, ingredients, and allergens, then select **Save corrections**. Show that validation reruns and the record becomes `ready_for_approval`, not `approved`. State the rule: **correction != approval**. Press **Approve** and show that the decision is now attributed as human-approved. Alternatively, reject an unsuitable record.

## 4:00–4:30 — Metrics and evaluation

Open `/metrics`. Show that the reviewed record still counts under `ever_required_human_review` after approval, appears under `human_approved`, and never appears under `straight_through_approved`. Explain that straight-through automated approval and human-reviewed approval are different business outcomes. Run `python -m evals.evaluate` and clarify that benchmark numbers are synthetic, not company performance.

## 4:30–5:00 — Production roadmap

Import the n8n workflow and show its webhook-to-API-to-status branch. Close with production needs: agreed rules, auth, supplier-data security, audit trails, queues, monitoring, and measured confidence calibration from reviewed outcomes.
