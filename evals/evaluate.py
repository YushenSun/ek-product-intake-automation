"""Reproducible offline evaluation of synthetic source cases only."""
from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from backend.app.extraction.providers import MockExtractionProvider
from backend.app.models.domain import Severity
from backend.app.validation.rules import validate_product


def run() -> dict[str, float | int]:
    cases = json.loads((Path(__file__).parents[1] / "sample_data" / "product_cases.json").read_text(encoding="utf-8"))
    provider = MockExtractionProvider()
    exact, possible, validation_correct, review_correct, duplicate_correct = 0, 0, 0, 0, 0
    latency_ms: list[float] = []
    approved = 0
    false_auto_approvals = 0
    seen_product_keys: set[tuple[str, str]] = set()
    for case in cases:
        started = perf_counter()
        result = provider.extract(case["source"], case["id"])
        product, issues = validate_product(result.product)
        key = ((product.product_name or "").casefold(), (product.supplier_name or "").casefold())
        duplicate = key in seen_product_keys and bool(key[0] and key[1])
        seen_product_keys.add(key)
        review = any(issue.severity == Severity.ERROR for issue in issues) or bool(result.conflicts) or duplicate
        latency_ms.append((perf_counter() - started) * 1000)
        approved += not review
        false_auto_approvals += int(not review and case["should_review"])
        review_correct += review == case["should_review"]
        validation_correct += review == case["should_review"]
        duplicate_correct += (case["id"] == "duplicate_candidate") == duplicate
        for field, expected in case["expected"].items():
            possible += 1
            exact += getattr(product, field) == expected
    total = len(cases)
    return {
        "synthetic_cases": total,
        "field_extraction_accuracy": round(exact / possible, 3) if possible else 1.0,
        "normalized_field_accuracy": round(exact / possible, 3) if possible else 1.0,
        "missing_field_and_validation_accuracy": round(validation_correct / total, 3),
        "duplicate_detection_accuracy": round(duplicate_correct / total, 3),
        "human_review_rate": round(sum(case["should_review"] for case in cases) / total, 3),
        "auto_approval_rate": round(approved / total, 3),
        "false_auto_approval_rate": round(false_auto_approvals / total, 3),
        "review_routing_accuracy": round(review_correct / total, 3),
        "average_processing_latency_ms": round(sum(latency_ms) / total, 3),
    }


if __name__ == "__main__":
    print("Synthetic benchmark only — not company performance data")
    print(json.dumps(run(), indent=2))
