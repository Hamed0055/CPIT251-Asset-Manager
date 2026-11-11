# User guide

## Dashboard

The Dashboard opens first. It shows registered assets, operational equipment,
aging equipment and assets flagged for repair. Category and status tables
show both populated and empty groups. Use **Register asset**, **Open
inventory**, or **View reports**.

## Register, find and update equipment

1. Click **Register asset** or **Inventory > Add**. Enter name, category,
   purchase year and status. Default status is Available and the default year
   is the current year. Optional fields may be blank.
2. Enter prices such as `1200.50` in SAR with a decimal point and no
   thousands separator. The same serial cannot be registered twice, even with
   different case or extra outer spaces.
3. Click **Save asset**. The app assigns an ID such as `IT-000001`.
4. In Inventory, enter part of an ID, name or serial, then press Enter or click
   **Search**. Category, status and year filters combine with the search. Click
   **Clear** to reset them. Use **Refresh** or F5 to reload views. An asset
   outside the current filters may not appear immediately after saving.
5. Select a row and choose **Details**, or double-click it. Choose **Edit** to
   change it. The ID does not change.

## Delete with confirmation

Select one row, click **Delete**, and check the ID and name in the confirmation
dialog. The default answer is No. Choosing Yes permanently removes that record.
Use **About > Back up database** before deleting records you may need later.

## Reports and CSV

- **Inventory summary** shows totals, operational condition, category and
  status counts, and review counts.
- **Aging equipment** lists equipment five or more calendar years old.
- **Maintenance and repair** includes all non-operational equipment and
  operational equipment due for an age-based review. Repair rows appear first.
- **Export CSV** exports the table currently displayed. Use a new filename.
  Reports cover the full inventory, independent of Inventory tab filters.

Use **About** to check which database is active and create a separate backup.
See [Database Schema](DATABASE_SCHEMA.md) for the restore procedure.

## Import assets and export a reusable inventory

The Inventory tab now has adjacent **Import CSV** and **Export CSV** controls.
Import opens a native file chooser, then a preview. Check total, valid, invalid
and duplicate counts, the first ten rows and individual row errors. Cancel
leaves the database unchanged. **Import Valid Records** saves accepted rows as
one batch; the results show actual imported/skipped counts and refresh all views.
Duplicate serials are skipped and existing records are never overwritten.

Use the [complete CSV guide](CSV_IMPORT.md) for required/optional columns,
UTF-8 encoding, quoted fields, sample files, spreadsheet escaping and recovery.
Inventory export contains complete editable records. Detailed report exports
are also accepted but lack optional fields; aggregate summary reports cannot
be imported as assets. Back up the database before adding a large batch if you
want a restore point, especially for serial-less records that cannot be deduplicated.
