from __future__ import annotations

from dataclasses import dataclass, field
import re

from backend.app.models.domain import Product, Severity, ValidationIssue


COUNTRIES = {"de": "DE", "deutschland": "DE", "germany": "DE", "deutsch": "DE", "fr": "FR", "france": "FR", "italy": "IT", "italien": "IT", "nl": "NL", "netherlands": "NL", "niederlande": "NL"}
CURRENCIES = {"€": "EUR", "eur": "EUR", "euro": "EUR", "$": "USD", "usd": "USD", "£": "GBP", "gbp": "GBP"}


@dataclass(frozen=True)
class ValidationConfig:
    required_fields: tuple[str, ...] = ("product_name", "brand", "ean", "category", "supplier_name", "price", "currency")
    food_required_fields: tuple[str, ...] = ("ingredients", "allergens")
    allowed_currencies: tuple[str, ...] = ("EUR", "USD", "GBP")


def ean_is_valid(ean: str | None) -> bool:
    if not ean or not re.fullmatch(r"\d{8}|\d{13}", ean):
        return False
    digits = [int(d) for d in ean]
    check = sum(d * (3 if index % 2 == (len(digits) - 2) % 2 else 1) for index, d in enumerate(digits[:-1]))
    return (10 - check % 10) % 10 == digits[-1]


def normalize_weight(value: float | None, unit: str | None) -> tuple[float | None, str | None]:
    if value is None:
        return None, unit
    normalized_unit = (unit or "").strip().lower()
    if normalized_unit in {"g", "gram", "grams"}:
        return float(value), "g"
    if normalized_unit in {"kg", "kilogram", "kilograms"}:
        return float(value) * 1000, "g"
    if normalized_unit in {"ml", "milliliter", "milliliters"}:
        return float(value), "ml"
    if normalized_unit in {"l", "liter", "litre", "liters"}:
        return float(value) * 1000, "ml"
    return float(value), unit


def normalize_country(value: str | None) -> str | None:
    if not value:
        return value
    return COUNTRIES.get(value.strip().casefold(), value.strip().upper())


def normalize_currency(value: str | None) -> str | None:
    if not value:
        return value
    return CURRENCIES.get(value.strip().casefold(), value.strip().upper())


def validate_product(product: Product, config: ValidationConfig = ValidationConfig()) -> tuple[Product, list[ValidationIssue]]:
    product = product.model_copy(deep=True)
    product.weight, product.weight_unit = normalize_weight(product.weight, product.weight_unit)
    product.country_of_origin = normalize_country(product.country_of_origin)
    product.currency = normalize_currency(product.currency)
    issues: list[ValidationIssue] = []
    for name in config.required_fields:
        if getattr(product, name) in (None, ""):
            issues.append(ValidationIssue(code="missing_required", field=name, severity=Severity.ERROR, message=f"Required field '{name}' is missing."))
    if product.ean and not ean_is_valid(product.ean):
        issues.append(ValidationIssue(code="invalid_ean", field="ean", severity=Severity.ERROR, message="EAN must be a valid EAN-8 or EAN-13 checksum."))
    if product.weight is not None and (product.weight <= 0 or product.weight_unit not in {"g", "ml"}):
        issues.append(ValidationIssue(code="invalid_weight", field="weight", severity=Severity.WARNING, message="Weight is missing a supported unit or is not positive."))
    if product.price is not None and product.price <= 0:
        issues.append(ValidationIssue(code="invalid_price", field="price", severity=Severity.ERROR, message="Price must be greater than zero."))
    if product.currency and product.currency not in config.allowed_currencies:
        issues.append(ValidationIssue(code="unsupported_currency", field="currency", severity=Severity.WARNING, message="Currency is not in the configured PoC allow-list."))
    if product.category and product.category.casefold() == "food":
        for name in config.food_required_fields:
            if getattr(product, name) in (None, ""):
                issues.append(ValidationIssue(code="missing_food_field", field=name, severity=Severity.ERROR, message=f"Food products require '{name}'."))
    return product, issues
