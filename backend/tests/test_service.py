import pytest

from backend.app.models.domain import Product, ProductPatch, ProductStatus


GOOD = "Product name: Demo Food\nBrand: Demo\nEAN: 4006381333931\nCategory: Food\nSupplier: Synthetic Supplier\nPrice: 3.20 EUR\nIngredients: oats\nAllergens: gluten"


def test_clean_product_is_auto_approved(service):
    record = service.create(GOOD, "good.txt", "txt")
    assert record.status == ProductStatus.APPROVED


def test_bad_product_requires_review(service):
    record = service.create("Product name: Bad\nBrand: Demo\nEAN: 1234567890123\nCategory: Food\nSupplier: Demo\nPrice: 1 EUR", "bad.txt", "txt")
    assert record.status == ProductStatus.REVIEW_REQUIRED
    assert any(issue.code == "invalid_ean" for issue in record.issues)


def test_duplicate_detection(service):
    service.create(GOOD, "one.txt", "txt")
    duplicate = service.create(GOOD, "two.txt", "txt")
    assert duplicate.status == ProductStatus.REVIEW_REQUIRED
    assert any(issue.code == "possible_duplicate" for issue in duplicate.issues)


def test_correction_then_approval(service):
    record = service.create("Product name: Bad\nBrand: Demo\nCategory: Home\nSupplier: Demo\nPrice: 1 EUR", "bad.txt", "txt")
    corrected = record.product.model_copy(update={"ean": "4006381333931"})
    saved = service.patch(record.id, ProductPatch(product=corrected, reviewer_note="EAN supplied by reviewer"))
    assert saved.status == ProductStatus.APPROVED
    assert service.set_status(record.id, ProductStatus.APPROVED).status == ProductStatus.APPROVED


def test_reject_workflow(service):
    record = service.create("Product name: Bad\nBrand: Demo\nCategory: Home\nSupplier: Demo\nPrice: 1 EUR", "bad.txt", "txt")
    assert service.set_status(record.id, ProductStatus.REJECTED).status == ProductStatus.REJECTED


def test_cannot_approve_open_errors(service):
    record = service.create("Product name: Bad\nBrand: Demo\nCategory: Home\nSupplier: Demo\nPrice: 1 EUR", "bad.txt", "txt")
    with pytest.raises(ValueError):
        service.set_status(record.id, ProductStatus.APPROVED)
