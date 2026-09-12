from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from backend.app.models.domain import BatchRowError


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    source_type: str


@dataclass(frozen=True)
class ParsedBatchRow:
    row_number: int
    text: str


@dataclass(frozen=True)
class ParsedBatch:
    source_type: str
    rows: list[ParsedBatchRow]
    row_errors: list[BatchRowError]

    @property
    def total_rows(self) -> int:
        return len(self.rows) + len(self.row_errors)


def parse_text(text: str, source_type: str = "txt") -> ParsedDocument:
    cleaned = text.strip()
    if not cleaned:
        raise ParseError("The submission is empty.")
    return ParsedDocument(text=cleaned, source_type=source_type)


def _is_empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _rows_to_batch(rows: list[list[object]], source_type: str) -> ParsedBatch:
    indexed_rows = [(number, list(row)) for number, row in enumerate(rows, start=1)]
    header_entry = next(((number, row) for number, row in indexed_rows if any(not _is_empty(cell) for cell in row)), None)
    if header_entry is None:
        raise ParseError("Spreadsheet has no usable rows.")

    header_number, header_row = header_entry
    headers = ["" if _is_empty(cell) else str(cell).strip() for cell in header_row]
    while headers and not headers[-1]:
        headers.pop()
    if not headers or not any(headers):
        raise ParseError("Spreadsheet has no usable headers.")

    parsed_rows: list[ParsedBatchRow] = []
    row_errors: list[BatchRowError] = []
    for row_number, values in indexed_rows:
        if row_number <= header_number or not any(not _is_empty(cell) for cell in values):
            continue

        extra_values = values[len(headers):]
        if any(not _is_empty(cell) for cell in extra_values):
            row_errors.append(BatchRowError(row_number=row_number, code="extra_cells", message="Row contains values beyond the declared headers."))
            continue

        padded = values[:len(headers)] + [None] * max(0, len(headers) - len(values))
        if any(not header and not _is_empty(value) for header, value in zip(headers, padded)):
            row_errors.append(BatchRowError(row_number=row_number, code="unmapped_cell", message="Row contains a value under an empty header."))
            continue

        lines = [
            f"{header}: {value}"
            for header, value in zip(headers, padded)
            if header and not _is_empty(value)
        ]
        if not lines:
            row_errors.append(BatchRowError(row_number=row_number, code="empty_product", message="Row has no labelled product values."))
            continue
        parsed_rows.append(ParsedBatchRow(row_number=row_number, text="\n".join(lines)))

    if not parsed_rows and not row_errors:
        raise ParseError("Spreadsheet contains headers but no data rows.")
    return ParsedBatch(source_type=source_type, rows=parsed_rows, row_errors=row_errors)


def parse_spreadsheet_batch(filename: str, content: bytes) -> ParsedBatch:
    if not content:
        raise ParseError("The uploaded file is empty.")
    extension = Path(filename).suffix.lower()
    try:
        if extension == ".csv":
            decoded = content.decode("utf-8-sig")
            return _rows_to_batch(list(csv.reader(io.StringIO(decoded))), "csv")
        if extension == ".xlsx":
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = workbook.active
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]
            return _rows_to_batch(rows, "xlsx")
    except ParseError:
        raise
    except UnicodeDecodeError as exc:
        raise ParseError("CSV file is not valid UTF-8.") from exc
    except Exception as exc:
        raise ParseError(f"Could not parse {extension or 'file'}: {exc}") from exc
    raise ParseError(f"Batch upload supports CSV and XLSX only, not {extension or 'files without an extension'}.")


def parse_file(filename: str, content: bytes) -> ParsedDocument:
    if not content:
        raise ParseError("The uploaded file is empty.")
    extension = Path(filename).suffix.lower()
    if extension in {".csv", ".xlsx"}:
        batch = parse_spreadsheet_batch(filename, content)
        if batch.rows:
            return ParsedDocument(text=batch.rows[0].text, source_type=batch.source_type)
        first_error = batch.row_errors[0]
        raise ParseError(f"First spreadsheet product could not be parsed: {first_error.message}")
    try:
        if extension in {".txt", ".md"}:
            return parse_text(content.decode("utf-8"), "txt")
        if extension == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return parse_text(text, "pdf")
    except UnicodeDecodeError as exc:
        raise ParseError("Text file is not valid UTF-8.") from exc
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(f"Could not parse {extension or 'file'}: {exc}") from exc
    raise ParseError(f"Unsupported file type: {extension or 'no extension'}.")
