import pytest

from backend.app.parsers import ParseError, parse_file


def test_csv_parser_turns_headers_into_labelled_text():
    parsed = parse_file("supplier.csv", b"Product Name,Brand,Price\nDemo Item,Demo,2.50 EUR\n")
    assert parsed.source_type == "csv"
    assert "Product Name: Demo Item" in parsed.text


def test_empty_and_malformed_spreadsheet_are_explicit_errors():
    with pytest.raises(ParseError):
        parse_file("empty.csv", b"")
    with pytest.raises(ParseError):
        parse_file("broken.xlsx", b"not an xlsx")
