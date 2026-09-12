from __future__ import annotations

from abc import ABC, abstractmethod
import json
import re

import httpx
from pydantic import ValidationError

from backend.app.config import settings
from backend.app.models.domain import ExtractionResult, FieldEvidence, Product


class ExtractionProviderError(RuntimeError):
    pass


class ExtractionProvider(ABC):
    @abstractmethod
    def extract(self, text: str, source_name: str) -> ExtractionResult:
        raise NotImplementedError


class MockExtractionProvider(ExtractionProvider):
    """Deterministic labelled-field extractor used for offline demos and tests.

    A confidence of 1.0 means an exact labelled field was read, not that the
    business fact is true. Values inferred from unlabelled prose remain absent.
    """
    aliases = {
        "product_name": ("product_name", "product name", "name", "artikelname"),
        "brand": ("brand", "marke"), "ean": ("ean", "gtin", "barcode"),
        "sku": ("sku", "article number", "artikelnummer"), "category": ("category", "kategorie"),
        "description": ("description", "beschreibung"), "weight": ("weight", "gewicht", "net weight"),
        "ingredients": ("ingredients", "zutaten"), "allergens": ("allergens", "allergene"),
        "country_of_origin": ("country_of_origin", "country of origin", "origin", "herkunftsland"),
        "packaging": ("packaging", "verpackung"), "supplier_name": ("supplier_name", "supplier", "lieferant"),
        "price": ("price", "preis"), "currency": ("currency", "währung"),
    }

    def extract(self, text: str, source_name: str) -> ExtractionResult:
        values: dict[str, str] = {}
        evidence: list[FieldEvidence] = []
        conflicts: list[str] = []
        for line in text.splitlines():
            match = re.match(r"^\s*([^:,;]+?)\s*[:;,]\s*(.+?)\s*$", line)
            if not match:
                continue
            label, value = match.groups()
            normalized_label = label.strip().lower().replace("-", "_")
            field = next((key for key, names in self.aliases.items() if normalized_label in names), None)
            if not field:
                continue
            if field in values and values[field].casefold() != value.casefold():
                conflicts.append(field)
                continue
            values[field] = value.strip()
            evidence.append(FieldEvidence(field=field, value=value.strip(), confidence=1.0, source=source_name, source_snippet=line[:240]))

        product_values = dict(values)
        # A compact field "weight: 250 g" belongs to both normalized fields.
        if weight_value := product_values.pop("weight", None):
            weight_match = re.match(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*([a-zA-Z]+)?\s*$", weight_value)
            if weight_match:
                product_values["weight"] = weight_match.group(1).replace(",", ".")
                if weight_match.group(2):
                    product_values["weight_unit"] = weight_match.group(2)
        if price_value := product_values.get("price"):
            number = re.search(r"-?[0-9]+(?:[.,][0-9]+)?", price_value)
            if number:
                product_values["price"] = number.group(0).replace(",", ".")
            currency = re.search(r"(EUR|USD|GBP|[A-Z]{3}|€|\$|£)", price_value, re.I)
            if currency and "currency" not in product_values:
                product_values["currency"] = currency.group(1)
        try:
            product = Product.model_validate(product_values)
        except ValidationError as exc:
            raise ExtractionProviderError(f"Mock provider produced invalid structured output: {exc}") from exc
        return ExtractionResult(product=product, evidence=evidence, conflicts=sorted(set(conflicts)), provider="mock")


class OpenAIExtractionProvider(ExtractionProvider):
    """OpenAI-compatible JSON-schema extraction boundary; never used by tests."""
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key, self.base_url, self.model = api_key, base_url.rstrip("/"), model

    def extract(self, text: str, source_name: str) -> ExtractionResult:
        schema = Product.model_json_schema()
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": "Extract supplier data. Return only schema-conformant JSON; use null for unknown values."}, {"role": "user", "content": text}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "product", "strict": True, "schema": schema}},
        }
        try:
            response = httpx.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json=body, timeout=20)
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
            product = Product.model_validate_json(raw)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError, ValidationError) as exc:
            raise ExtractionProviderError(f"LLM structured extraction failed: {exc}") from exc
        return ExtractionResult(product=product, evidence=[], conflicts=[], provider="openai-compatible")


def provider_from_settings() -> ExtractionProvider:
    if settings.extraction_provider.lower() == "mock":
        return MockExtractionProvider()
    if settings.extraction_provider.lower() in {"openai", "openai-compatible"}:
        if not settings.openai_api_key:
            raise ExtractionProviderError("OPENAI_API_KEY is required for the OpenAI-compatible provider.")
        return OpenAIExtractionProvider(settings.openai_api_key, settings.openai_base_url, settings.openai_model)
    raise ExtractionProviderError(f"Unknown extraction provider: {settings.extraction_provider}")
