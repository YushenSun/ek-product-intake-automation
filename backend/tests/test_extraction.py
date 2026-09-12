import pytest

from backend.app.extraction.providers import ExtractionProviderError, MockExtractionProvider, OpenAIExtractionProvider
from backend.app.models.domain import Product


def test_mock_provider_extracts_direct_labels_with_evidence():
    result = MockExtractionProvider().extract("Product name: Demo Item\nBrand: Demo\nEAN: 4006381333931\nPrice: 2.50 EUR", "test.txt")
    assert result.product.product_name == "Demo Item"
    assert result.product.price == 2.5
    assert result.product.currency == "EUR"
    assert result.evidence[0].confidence == 1.0


def test_mock_provider_reports_conflicting_fields():
    result = MockExtractionProvider().extract("Brand: One\nBrand: Two", "test.txt")
    assert result.product.brand == "One"
    assert result.conflicts == ["brand"]


def test_provider_output_schema_rejects_unknown_fields():
    with pytest.raises(Exception):
        Product.model_validate({"product_name": "x", "surprise": "no"})


def test_openai_provider_rejects_malformed_structured_output(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {"choices": [{"message": {"content": "not json"}}]}
    monkeypatch.setattr("backend.app.extraction.providers.httpx.post", lambda *args, **kwargs: Response())
    provider = OpenAIExtractionProvider("demo-key", "https://example.invalid/v1", "demo")
    with pytest.raises(ExtractionProviderError):
        provider.extract("Product name: test", "test.txt")
