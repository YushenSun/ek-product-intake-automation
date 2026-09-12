from backend.app.models.domain import Product, Severity
from backend.app.validation.rules import ean_is_valid, normalize_country, normalize_weight, validate_product


def test_ean_checksum_validation():
    assert ean_is_valid("4006381333931")
    assert not ean_is_valid("4006381333932")
    assert not ean_is_valid("not-an-ean")


def test_normalizes_weight_and_country():
    assert normalize_weight(0.25, "kg") == (250.0, "g")
    assert normalize_weight(250, "g") == (250.0, "g")
    assert normalize_country("Deutschland") == "DE"
    assert normalize_country("Germany") == "DE"


def test_required_food_fields_and_price_are_errors():
    product, issues = validate_product(Product(product_name="Soup", brand="Demo", ean="4006381333931", category="food", supplier_name="Demo", price=0, currency="EUR"))
    error_fields = {issue.field for issue in issues if issue.severity == Severity.ERROR}
    assert {"ingredients", "allergens", "price"} <= error_fields
    assert product.currency == "EUR"
