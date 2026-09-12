from io import BytesIO

import pytest
from openpyxl import Workbook

from backend.app.parsers import ParseError, parse_file, parse_spreadsheet_batch


def xlsx_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_single_csv_parser_keeps_first_product_behavior():
    parsed = parse_file("supplier.csv", b"Product Name,Brand,Price\nDemo Item,Demo,2.50 EUR\nSecond,Demo,3 EUR\n")
    assert parsed.source_type == "csv"
    assert "Product Name: Demo Item" in parsed.text
    assert "Second" not in parsed.text


def test_csv_batch_parses_multiple_rows_and_preserves_numbers():
    content = b"\nProduct Name,Brand,EAN,Price\nFirst,Demo,2000000000008,2 EUR\n\nSecond,Demo,2000000000015,3 EUR\n"
    parsed = parse_spreadsheet_batch("supplier.csv", content)
    assert [row.row_number for row in parsed.rows] == [3, 5]
    assert "Product Name: First" in parsed.rows[0].text
    assert "Product Name: Second" in parsed.rows[1].text
    assert parsed.total_rows == 2


def test_csv_batch_tolerates_missing_cells_and_isolates_extra_cells():
    content = b"Product Name,Brand,EAN\nMissing Cells,Demo\nMalformed,Demo,2000000000008,unexpected\n"
    parsed = parse_spreadsheet_batch("supplier.csv", content)
    assert len(parsed.rows) == 1
    assert "EAN:" not in parsed.rows[0].text
    assert parsed.row_errors[0].row_number == 3
    assert parsed.row_errors[0].code == "extra_cells"


def test_xlsx_batch_parses_multiple_rows_and_ignores_empty_rows():
    content = xlsx_bytes([
        ["Product Name", "Brand", "EAN", "Price"],
        ["First", "Demo", "2000000000008", "2 EUR"],
        [None, None, None, None],
        ["Second", "Demo", None, "3 EUR"],
    ])
    parsed = parse_spreadsheet_batch("supplier.xlsx", content)
    assert [row.row_number for row in parsed.rows] == [2, 4]
    assert "EAN:" not in parsed.rows[1].text
    assert parsed.total_rows == 2


def test_empty_and_malformed_spreadsheet_are_explicit_errors():
    with pytest.raises(ParseError):
        parse_file("empty.csv", b"")
    with pytest.raises(ParseError):
        parse_file("broken.xlsx", b"not an xlsx")
    with pytest.raises(ParseError):
        parse_spreadsheet_batch("not-supported.txt", b"Product: X")
