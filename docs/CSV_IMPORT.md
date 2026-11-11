# CSV import and full inventory export

## Import a file

1. Open **Inventory > Import CSV** and select a CSV file. The native chooser
   offers CSV and all-file filters. Cancelling makes no changes.
2. Inspect the filename, total/valid/invalid/duplicate counts, first ten records
   and scrollable row errors. Row numbers are starting physical lines, including
   the header; a quoted multiline field can span several lines.
3. Click **Import Valid Records** to save only accepted records, or **Cancel**
   (also Escape/window close) to discard the preview. Confirmation defaults to
   neither importing nor overwriting. With zero valid records, import is disabled.
4. The results dialog reports the actual imported and skipped counts and lists
   all skipped rows. Close it to return to Inventory. All views are refreshed;
   Inventory filters reset to All so newly imported records are visible.

Preparation and insertion run in short-lived background threads. Only the main
thread accesses Tk. The window stays responsive. Closing the application or the
preview is temporarily prevented during a running operation, so a confirmed
transaction can finish safely. There is no persistent background service.

## CSV format

Use comma-separated UTF-8 or UTF-8 with BOM. LF and CRLF line endings work.
Quote fields containing commas, quotes or newlines using normal CSV rules
(e.g. `"Lab, Building A"`). Do not rename headers to internal SQL field names.
Header order may vary and outer header whitespace is ignored; names are
otherwise case-sensitive. Missing required, duplicate, blank or unknown headers
reject the whole file rather than guessing a mapping. Blank physical lines are
ignored; rows with missing/extra fields are invalid records.

| CSV header | Required | Internal field / rule |
| --- | --- | --- |
| Asset ID | No | Informational only; ignored, new SQLite IDs generated |
| Name | Yes | `name`: nonblank, at most 120 characters |
| Category | Yes | `category`: Desktop PC, Laptop, Router, Switch, Peripheral, Other |
| Serial number | No | `serial`: string, at most 100 characters; leading zeros retained |
| Year | Yes | `purchase_year`: four ASCII digits, 1900 through current year |
| Purchase price (SAR) | No | `purchase_price` converted to `price_cents`: nonnegative decimal, at most two fractional digits; no commas/currency symbols |
| Status | Yes | `status`: Available, Assigned, Under Maintenance, Retired |
| Assigned person | No | `assigned_to`: at most 120 characters |
| Location | No | `location`: at most 120 characters |
| Notes | No | `notes`: at most 4,000 characters |

Optional columns may be absent and optional cells may be empty. Empty price and
serial become NULL; other empty optional fields become empty strings. Manual
entry and CSV share the same validator, including trimming and price limits.
Use Peripheral for monitors; Monitor is not a supported category. Save serial
columns as text when editing in spreadsheets to avoid stripping zeros *before*
the application reads the file.

Minimal example:

```csv
Name,Category,Serial number,Year,Status
"Library, laptop",Laptop,000123,2024,Available
```

## Export compatibility

**Inventory > Export CSV** exports every inventory record and all editable
fields, independently of active filters. Use this format for a complete
export/reimport. Export requires a new filename and writes UTF-8 with BOM.
IDs and timestamps are not restored: imported rows get fresh database IDs and
creation timestamps. A CSV is a data interchange file; use **About > Back up
database** for a complete database backup including IDs and timestamps.

The original **Reports > Export CSV** still exports the current report.
Existing Aging equipment and Maintenance and repair CSVs can be imported using
Name/Category/Year/Status. Their calculated Age/Classification/Action columns
are accepted and ignored. They never contained serials, prices, assignments,
locations or notes; the preview explicitly warns those fields will be blank.
The aggregate Inventory summary CSV cannot become individual asset records and
is rejected with a message directing you to Inventory > Export CSV.

Spreadsheet safety: exports prefix formula-like text (`=`, `+`, `-`, `@`,
including after whitespace) with an apostrophe. Full inventory export also
doubles an existing leading apostrophe. Import reverses these documented
escapes, preserving a full inventory roundtrip. For hand-written CSV text that
literally starts with an apostrophe, double that first apostrophe to avoid
ambiguity. The original stored text is never modified by exporting.

## Duplicates, counts and recovery

Serials are compared after trimming and Unicode case folding, exactly as in
manual entry. The first *valid* occurrence in the file wins; subsequent valid
rows with the same serial and all existing database serials are skipped. Rows
that fail validation are classified as invalid first. No existing asset is
updated or deleted. Blank serials are allowed and cannot establish identity:
**reimporting serial-less rows creates more assets**, even with identical names.

Preview counts satisfy `total = valid + invalid + duplicates`. Insertion
rechecks serials while holding SQLite's write transaction. A serial registered
since preview is skipped and included in final duplicate counts. Final counts
satisfy `total = imported + invalid + duplicates` and
`skipped = invalid + duplicates`.

The prepared records are an immutable snapshot: changing the CSV after preview
does not change the confirmed batch. Prepare again to read an edited file.
Read/encoding/header/parser failures never insert anything. An unexpected
insertion/storage/constraint error rolls back **all accepted rows in the batch**,
keeps the preview open and offers retry or Cancel. Existing assets remain.
Check the error (permissions, free space, database lock), resolve it, then retry.
For row errors, cancel, correct the CSV and choose it again. There is no
partially committed batch to clean up. A refresh error after a successful commit
is explicitly reported as saved data; use F5 rather than reimporting blindly.

## Presentation demonstration

Use a fresh disposable inventory so the sample never touches your real data:

```sh
./scripts/run_linux.sh --database /tmp/cpit251-presentation-new.sqlite3
```

On Windows use a new path, e.g.
`python main.py --database "$env:TEMP\cpit251-presentation-new.sqlite3"`.
Choose a different name if that database already exists.

1. Import `examples/sample_inventory_50.csv`: 50 valid fictional assets with all
   six categories and all four statuses. Cancel once to demonstrate no writes;
   reopen and confirm to show 50 assets and updated dashboard counts.
2. Export from Inventory to a new filename. Reimport it into the same database:
   all 50 are duplicates and the import action is disabled. Into a new inventory,
   all 50 are valid (the automated roundtrip verifies the complete field values).
3. Select `examples/invalid_inventory.csv`. Against the 50-asset demo it shows
   total 7, valid 0, invalid 4, duplicates 3. In a fresh empty inventory it shows
   valid 2, invalid 4, duplicates 1; importing valid rows adds only two.
4. Show row-specific name/year/price/category errors and explain that skipping
   duplicate serials protects the existing inventory.
5. Explain the transaction and point to the automated rollback test; do not
   deliberately damage a real inventory to demonstrate a disk failure.
