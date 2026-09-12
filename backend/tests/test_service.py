import pytest

from backend.app.models.domain import ProductPatch, ProductStatus


GOOD = "Product name: Demo Food\nBrand: Demo\nEAN: 4006381333931\nCategory: Food\nSupplier: Synthetic Supplier\nPrice: 3.20 EUR\nIngredients: oats\nAllergens: gluten"
BAD = "Product name: Bad\nBrand: Demo\nCategory: Home\nSupplier: Demo\nPrice: 1 EUR"


def test_clean_product_is_auto_approved(service):
    record = service.create(GOOD, "good.txt", "txt")
    assert record.status == ProductStatus.APPROVED
    assert record.initial_status == ProductStatus.APPROVED
    assert record.decision_source == "automatic"
    assert record.approval_source == "automatic"
    assert record.approved_at is not None
    assert record.review_required_at is None


def test_bad_product_requires_review(service):
    record = service.create("Product name: Bad\nBrand: Demo\nEAN: 1234567890123\nCategory: Food\nSupplier: Demo\nPrice: 1 EUR", "bad.txt", "txt")
    assert record.status == ProductStatus.REVIEW_REQUIRED
    assert record.initial_status == ProductStatus.REVIEW_REQUIRED
    assert record.review_required_at is not None
    assert any(issue.code == "invalid_ean" for issue in record.issues)


def test_duplicate_detection(service):
    service.create(GOOD, "one.txt", "txt")
    duplicate = service.create(GOOD, "two.txt", "txt")
    assert duplicate.status == ProductStatus.REVIEW_REQUIRED
    assert any(issue.code == "possible_duplicate" for issue in duplicate.issues)


def test_correction_requires_explicit_approval(service):
    record = service.create(BAD, "bad.txt", "txt")
    corrected = record.product.model_copy(update={"ean": "4006381333931"})

    saved = service.patch(record.id, ProductPatch(product=corrected, reviewer_note="EAN supplied by reviewer"))

    assert saved.status == ProductStatus.READY_FOR_APPROVAL
    assert saved.status != ProductStatus.APPROVED
    assert saved.initial_status == ProductStatus.REVIEW_REQUIRED
    assert saved.decision_source == "pending_review"
    assert saved.correction_count == 1
    assert saved.reviewed_at is not None
    assert saved.approved_at is None

    approved = service.set_status(record.id, ProductStatus.APPROVED)
    assert approved.status == ProductStatus.APPROVED
    assert approved.decision_source == "human"
    assert approved.approval_source == "human"
    assert approved.approved_at is not None
    assert approved.review_required_at is not None


def test_correction_with_blocking_errors_stays_in_review(service):
    record = service.create(BAD, "bad.txt", "txt")
    still_invalid = record.product.model_copy(update={"ean": "1234567890123"})

    saved = service.patch(record.id, ProductPatch(product=still_invalid))

    assert saved.status == ProductStatus.REVIEW_REQUIRED
    assert saved.correction_count == 1


def test_reject_workflow(service):
    record = service.create(BAD, "bad.txt", "txt")
    rejected = service.set_status(record.id, ProductStatus.REJECTED)
    assert rejected.status == ProductStatus.REJECTED
    assert rejected.decision_source == "human"
    assert rejected.rejected_at is not None


def test_cannot_approve_open_errors(service):
    record = service.create(BAD, "bad.txt", "txt")
    with pytest.raises(ValueError):
        service.set_status(record.id, ProductStatus.APPROVED)
