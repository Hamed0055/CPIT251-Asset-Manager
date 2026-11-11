"""Read-only CSV preparation and confirmed, atomic asset insertion. No Tk code."""
import csv
from dataclasses import dataclass
from pathlib import Path

from src.asset_service import insert_validated_asset
from src.database import connect
from src.reports import ASSET_COLUMNS, DETAIL_HEADERS, SUMMARY_HEADERS
from src.validation import ValidationError, validate_asset

REQUIRED_HEADERS = frozenset({"Name", "Category", "Year", "Status"})
ALLOWED_HEADERS = frozenset(header for header, _key in ASSET_COLUMNS) | frozenset(DETAIL_HEADERS)


class CSVImportError(ValueError):
    """The file cannot be interpreted safely as an asset inventory."""


@dataclass(frozen=True)
class RowIssue:
    row_number: int
    kind: str
    message: str


@dataclass(frozen=True)
class ImportRecord:
    row_number: int
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PreviewRow:
    row_number: int
    values: tuple[str, ...]
    outcome: str


@dataclass(frozen=True)
class ImportPreview:
    source: Path
    database: Path
    headers: tuple[str, ...]
    total: int
    records: tuple[ImportRecord, ...]
    issues: tuple[RowIssue, ...]
    first_rows: tuple[PreviewRow, ...]
    warnings: tuple[str, ...]

    @property
    def valid(self):
        return len(self.records)

    @property
    def invalid(self):
        return sum(issue.kind == "invalid" for issue in self.issues)

    @property
    def duplicates(self):
        return sum(issue.kind == "duplicate" for issue in self.issues)


@dataclass(frozen=True)
class ImportResult:
    total: int
    inserted: int
    issues: tuple[RowIssue, ...]

    @property
    def invalid(self):
        return sum(issue.kind == "invalid" for issue in self.issues)

    @property
    def duplicates(self):
        return sum(issue.kind == "duplicate" for issue in self.issues)

    @property
    def skipped(self):
        return len(self.issues)


def validate_headers(raw):
    if raw is None:
        raise CSVImportError("The CSV is empty. A header row is required.")
    headers = tuple(value.strip() for value in raw)
    if set(headers) == set(SUMMARY_HEADERS):
        raise CSVImportError("This is an aggregate summary, not asset records. Use Inventory > Export CSV.")
    if not all(headers):
        raise CSVImportError("Every column needs a nonempty header.")
    if len(set(headers)) != len(headers):
        raise CSVImportError("Duplicate CSV headers are not allowed.")
    unexpected = set(headers) - ALLOWED_HEADERS
    missing = REQUIRED_HEADERS - set(headers)
    problems = []
    if missing:
        problems.append("Missing required columns: " + ", ".join(sorted(missing)))
    if unexpected:
        problems.append("Unexpected columns: " + ", ".join(sorted(unexpected)))
    if problems:
        raise CSVImportError("; ".join(problems) + ". See the supported CSV format in the user guide.")
    return headers


def decode_cell(value):
    """Undo the documented inventory export's spreadsheet-safety escaping."""
    if value.startswith("''") or (value.startswith("'") and value[1:].lstrip().startswith(("=", "+", "-", "@"))):
        return value[1:]
    return value


def serial_keys(connection):
    return {row[0] for row in connection.execute("SELECT serial_key FROM assets WHERE serial_key IS NOT NULL")}


def prepare_import(database, source):
    """Validate a frozen file snapshot; neither create nor modify a database."""
    source, database = Path(source), Path(database).absolute()
    with connect(database, read_only=True) as connection:
        known = serial_keys(connection)
    records, issues, first_rows = [], [], []
    seen = {}
    total = 0
    blank_serials = 0
    try:
        with source.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            headers = validate_headers(next(reader, None))
            while True:
                row_number = reader.line_num + 1
                row = next(reader, None)
                if row is None:
                    break
                if not row:  # Physical empty lines are not asset records.
                    continue
                total += 1
                outcome = "Valid"
                try:
                    if len(row) != len(headers):
                        raise ValidationError(f"Expected {len(headers)} fields; found {len(row)}. Check quoting/commas.")
                    if any("\x00" in value for value in row):
                        raise ValidationError("NUL characters are not supported.")
                    cells = dict(zip(headers, row, strict=True))
                    fields = {key: decode_cell(cells.get(header, "")) for header, key in ASSET_COLUMNS if key}
                    values = validate_asset(fields)
                    serial = values["serial_key"]
                    if serial is not None and serial in known:
                        outcome = "Duplicate"
                        issues.append(RowIssue(row_number, "duplicate", "Serial already exists in the database; skipped."))
                    elif serial is not None and serial in seen:
                        outcome = "Duplicate"
                        issues.append(RowIssue(row_number, "duplicate", f"Serial repeats row {seen[serial]}; skipped."))
                    else:
                        if serial is not None:
                            seen[serial] = row_number
                        else:
                            blank_serials += 1
                        records.append(ImportRecord(row_number, tuple(fields.items())))
                except ValidationError as error:
                    outcome = "Invalid"
                    issues.append(RowIssue(row_number, "invalid", str(error)))
                if len(first_rows) < 10:
                    first_rows.append(PreviewRow(row_number, tuple(row), outcome))
    except UnicodeError as error:
        raise CSVImportError("The CSV is not valid UTF-8. Save it as CSV UTF-8 and try again.") from error
    except csv.Error as error:
        raise CSVImportError(f"Malformed CSV near line {reader.line_num}: {error}") from error
    warnings = ["Duplicates are skipped, never updated. Asset IDs are regenerated by SQLite."]
    missing_optional = [header for header, key in ASSET_COLUMNS if key and header not in headers]
    if missing_optional:
        warnings.append("Columns absent from this file will be blank: " + ", ".join(missing_optional) + ".")
    if blank_serials:
        warnings.append(f"{blank_serials} valid rows have no serial. They cannot be deduplicated; importing again adds them again.")
    return ImportPreview(source, database, headers, total, tuple(records), tuple(issues), tuple(first_rows), tuple(warnings))


def import_prepared(database, preview):
    """Insert only confirmed snapshot rows in one transaction, rechecking serials."""
    if Path(database).absolute() != preview.database:
        raise CSVImportError("The preview belongs to a different inventory. Prepare it again.")
    issues = list(preview.issues)
    inserted = 0
    with connect(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        known = serial_keys(connection)
        for record in preview.records:
            # Reuse exactly the manual-entry rules, including current-year bounds.
            values = validate_asset(dict(record.fields))
            serial = values["serial_key"]
            if serial is not None and serial in known:
                issues.append(RowIssue(record.row_number, "duplicate", "Serial added since preview; skipped."))
                continue
            insert_validated_asset(connection, values)
            inserted += 1
            if serial is not None:
                known.add(serial)
        # The connection context commits all rows together, or rolls back on error.
    return ImportResult(preview.total, inserted, tuple(sorted(issues, key=lambda issue: issue.row_number)))
