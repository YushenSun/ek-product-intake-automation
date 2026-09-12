from backend.app.models.domain import BatchStatus, ProductPatch, ProductStatus
from backend.app.services.batch import BatchService


HEADER = "Product Name,Brand,EAN,Category,Supplier,Price\n"


def test_batch_creates_multiple_products_and_isolates_bad_row(batch_service):
    content = (
        HEADER
        + "First,Demo,2000000000008,Home,Synthetic Supplier,2 EUR\n"
        + "Malformed,Demo,2000000000015,Home,Synthetic Supplier,3 EUR,unexpected\n"
        + "Second,Demo,2000000000022,Home,Synthetic Supplier,4 EUR\n"
        + ",,,,,\n"
    ).encode()

    batch = batch_service.create("catalogue.csv", content)
    products = batch_service.products(batch.id)

    assert batch.status == BatchStatus.COMPLETED_WITH_ERRORS
    assert batch.total_rows == 3
    assert batch.processed_rows == 2
    assert batch.failed_rows == 1
    assert batch.row_errors[0].row_number == 3
    assert [product.source_row_number for product in products] == [2, 4]


def test_within_batch_duplicate_routes_second_row_to_review(batch_service):
    content = (
        HEADER
        + "First,Demo,2000000000008,Home,Synthetic Supplier,2 EUR\n"
        + "First Copy,Demo,2000000000008,Home,Synthetic Supplier,2 EUR\n"
    ).encode()

    batch = batch_service.create("duplicates.csv", content)
    products = batch_service.products(batch.id)

    assert products[0].status == ProductStatus.APPROVED
    assert products[1].status == ProductStatus.REVIEW_REQUIRED
    assert any(issue.code == "possible_duplicate" for issue in products[1].issues)
    assert batch.straight_through_approved == 1
    assert batch.ever_required_human_review == 1
    assert batch.currently_review_required == 1


def test_batch_detects_duplicate_against_existing_database(service, batch_service):
    service.create(
        "Product name: Existing\nBrand: Demo\nEAN: 2000000000008\nCategory: Home\nSupplier: Synthetic Supplier\nPrice: 2 EUR",
        "existing.txt",
        "txt",
    )
    batch = batch_service.create(
        "new.csv",
        (HEADER + "Incoming,Demo,2000000000008,Home,Synthetic Supplier,2 EUR\n").encode(),
    )
    product = batch_service.products(batch.id)[0]

    assert product.status == ProductStatus.REVIEW_REQUIRED
    assert any(issue.code == "possible_duplicate" for issue in product.issues)


def test_batch_counts_preserve_historical_human_attribution(batch_service):
    batch = batch_service.create(
        "review.csv",
        (HEADER + "Needs EAN,Demo,,Home,Synthetic Supplier,2 EUR\n").encode(),
    )
    product = batch_service.products(batch.id)[0]
    corrected = product.product.model_copy(update={"ean": "2000000000008"})

    ready = batch_service.intake.patch(product.id, ProductPatch(product=corrected))
    approved = batch_service.intake.set_status(product.id, ProductStatus.APPROVED)
    refreshed = batch_service.get(batch.id)

    assert ready.status == ProductStatus.READY_FOR_APPROVAL
    assert approved.approval_source == "human"
    assert refreshed.straight_through_approved == 0
    assert refreshed.ever_required_human_review == 1
    assert refreshed.human_approved == 1
