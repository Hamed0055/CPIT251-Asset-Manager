# Architecture and editable diagrams

Tk callbacks own interaction, selection and status messages. They send plain
form strings and asset IDs to the service. The service invokes validation,
binds values, and returns SQLite rows. Reports turn one inventory snapshot
into counts or tabular rows. No SQL is constructed from raw user input.

## Component architecture

```mermaid
flowchart LR
    User[Inventory operator] --> GUI[Tkinter and ttk]
    Main[main.py] --> GUI
    Main --> C[config.py data path]
    GUI --> S[Asset service]
    S --> V[Form validation]
    S --> D[SQLite connection and schema]
    D --> File[(User inventory database)]
    GUI --> R[Reports and CSV]
    R --> Export[CSV file]
    GUI --> D
    Main --> D
    R --> S
    D --> Backup[SQLite backup file]
```

## Use cases

```mermaid
flowchart LR
    U[Inventory operator]
    subgraph App[Inventory Manager]
        Dashboard([View dashboard])
        Register([Register asset])
        Find([Search or filter assets])
        Details([Read asset details])
        Edit([Edit asset])
        Delete([Delete asset])
        Confirm([Confirm deletion])
        Reports([View reports])
        Export([Export current report])
        Backup([Back up inventory])
    end
    U --- Dashboard
    U --- Register
    U --- Find
    U --- Details
    U --- Edit
    U --- Delete
    Delete -. requires .-> Confirm
    U --- Reports
    U --- Export
    U --- Backup
```

## Entity relationship diagram

The editable [draw.io ERD](diagrams/inventory-v2.drawio) and
[high-resolution PNG](diagrams/inventory-v2.png) are generated from the actual
v2 table metadata by `scripts/create_erd.py`.

```mermaid
erDiagram
    CATEGORY ||--o{ ASSET : classifies
    LOCATION |o--o{ ASSET : contains
    CATEGORY {
        integer id PK
        text name UK
    }
    LOCATION {
        integer id PK
        text name UK
    }
    ASSET {
        integer id PK
        text name
        integer category_id FK
        integer location_id FK
        text serial
        text serial_key UK
        integer purchase_year
        integer price_cents
        text status
        text assigned_to
        text notes
        text created_at
        text updated_at
    }
```

CATEGORY, LOCATION and ASSET are database entities, not Python classes.
`category_id` is mandatory; `location_id` is optional. Both references use
ON DELETE RESTRICT. See DATABASE_SCHEMA.md for all constraints.

## Relational service flow

Tkinter GUI -> Asset Service -> SQLite Database. Forms read category choices
from categories and allow either an existing or new location name. Validation
keeps the established rules. Add/edit and confirmed CSV batches begin an
IMMEDIATE transaction before resolving names. The database helper looks up the
category ID and reuses or creates a trimmed/casefolded location. A blank
location becomes NULL. The asset insert/update and any new location commit or
roll back together. No GUI operator enters numerical foreign keys.

Read operations JOIN categories and LEFT JOIN optional locations, exposing the
same readable fields as v1 to tables, dashboards and CSV. Reports summarize the
joined snapshot; `report_from_database` loads it through that same service.

## Registration activity

```mermaid
flowchart TD
    A[Open Register asset] --> B[Enter fields]
    B --> C{Save or cancel?}
    C -->|Cancel| E[Close form]
    C -->|Save| D{Input valid?}
    D -->|No| F[Show explanation and preserve fields]
    F --> B
    D -->|Yes| G[Attempt parameterized insert]
    G --> H{Insert committed?}
    H -->|No| F
    H -->|Yes| I[Refresh and show generated asset ID]
```

## Asset management activity

```mermaid
flowchart TD
    A[Search or filter inventory] --> B[Select one row]
    B --> C{Choose action}
    C -->|Details| D[Open read-only asset]
    C -->|Edit| E[Validate and save changes]
    C -->|Delete| F{Operator confirms?}
    F -->|No| A
    F -->|Yes| G[Delete selected ID]
    G --> H[Refresh inventory and totals]
    E --> H
    D --> A
```

## Sequence for saving an edit

```mermaid
sequenceDiagram
    actor Operator
    participant Form as Tk edit form
    participant Service as Asset service
    participant Validate as Validator
    participant DB as SQLite
    Operator->>Form: Save asset
    Form->>Service: update_asset(path, id, fields)
    Service->>Validate: Validate and convert form strings
    alt Invalid input
        Validate-->>Form: ValidationError via service
        Form-->>Operator: Show message, keep form open
    else Valid input
        Validate-->>Service: Validated values
        Service->>DB: BEGIN IMMEDIATE and resolve category/location IDs
        Service->>DB: Bound UPDATE for asset ID
        alt Constraint, missing asset, or storage error
            DB-->>Service: Error or zero affected rows
            Service-->>Form: Rollback and report failure
            Form-->>Operator: Show error, keep form open
        else Success
            DB-->>Service: Commit
            Service-->>Form: Return
            Form-->>Operator: Refresh table and dashboard
        end
    end
```

## CSV feature: components and data flow (DFD level 1)

Schema v2 keeps CSV fields readable while normalizing persistent storage.
The full inventory exporter remains distinct from report-specific exports.

```mermaid
flowchart LR
    Operator[Operator] -->|Select file| GUI[InventoryApp / native chooser]
    CSV[UTF-8 CSV] --> Parser[csv.reader / validate_headers]
    GUI -->|Worker prepares snapshot| Parser
    Parser --> Validator[Existing validate_asset]
    Validator --> Dedup[Serial duplicate detection]
    DB[(D1: SQLite inventory store - assets, categories, locations)] -->|Read-only serial keys| Dedup
    Dedup --> Preview[Immutable ImportPreview]
    Preview -->|Queue / main thread| Dialog[ImportPreviewDialog]
    Dialog -->|Explicit confirmation| Batch[import_prepared]
    Batch -->|Revalidate / recheck serials| Tx[BEGIN IMMEDIATE]
    Tx -->|Resolve category and location, then insert asset| DB
    Tx --> Result[Commit all or rollback all]
    Result -->|Queue / main thread| Views[Results and refreshed views]
```

D1 is one logical persistent data store with three relational tables, not
three DFD processes. Parser, validation and batch insertion are processes.

This is the required pipeline: **CSV File -> CSV Parser -> Validation ->
Duplicate Detection -> SQLite Transaction -> GUI Refresh**. Preparation is
read-only. A transaction exists only after explicit confirmation. Worker results
cross `queue.Queue`; `root.after` polls on the Tk thread. SQLite connections are
created and closed in the thread doing the database work, never shared across
threads. Prior destroyed Tk widget cycles are finalized on the GUI thread before
launching a worker so worker allocations do not finalize old Tk variables.

## Class and module relationships for the final report

The application uses functions for services, rather than adding artificial
classes. The diagram distinguishes those modules from actual GUI/data classes.

```mermaid
classDiagram
    class InventoryApp {
        import_csv()
        run_csv_job()
        export_inventory()
        refresh()
    }
    class AssetDialog {
        fields
        field_widgets
        save()
    }
    class DatabaseModule {
        <<module>>
        connect()
        initialize()
        resolve_relationships()
        backup_database()
    }
    class ImportPreviewDialog {
        confirm()
        close()
        show_result()
        import_failed()
    }
    class CSVImportModule {
        <<module>>
        prepare_import()
        validate_headers()
        import_prepared()
    }
    class AssetServiceModule {
        <<module>>
        add_asset()
        insert_validated_asset()
        category_names()
        location_names()
        list_assets()
    }
    class ImportPreview {
        <<frozen dataclass>>
        source
        database
        total
        records
        issues
        first_rows
        warnings
    }
    class ImportRecord {
        <<frozen dataclass>>
        row_number
        fields
    }
    class RowIssue {
        <<frozen dataclass>>
        row_number
        kind
        message
    }
    class PreviewRow {
        <<frozen dataclass>>
        row_number
        values
        outcome
    }
    class ImportResult {
        <<frozen dataclass>>
        total
        inserted
        issues
    }
    InventoryApp --> AssetDialog
    AssetDialog --> AssetServiceModule
    AssetServiceModule --> DatabaseModule
    InventoryApp --> ImportPreviewDialog
    InventoryApp --> CSVImportModule
    ImportPreviewDialog --> ImportPreview
    ImportPreviewDialog --> ImportResult
    CSVImportModule --> AssetServiceModule
    CSVImportModule --> ImportPreview
    CSVImportModule --> ImportResult
    ImportPreview *-- ImportRecord
    ImportPreview *-- RowIssue
    ImportPreview *-- PreviewRow
    ImportResult *-- RowIssue
```

## CSV screen flow

```mermaid
flowchart TD
    Inventory[Inventory tab] --> Choose[Native file chooser]
    Choose -->|Cancel| Inventory
    Choose -->|Select| Prepare[Background read and validation]
    Prepare -->|Fatal file/header error| Error[Error message / no changes]
    Error --> Inventory
    Prepare --> Preview[Counts / first 10 rows / errors / duplicate policy]
    Preview -->|Cancel / Escape / close| Inventory
    Preview -->|Import Valid Records| Insert[Background atomic batch]
    Insert -->|Database failure| Retry[Rollback / show error / retain preview]
    Retry --> Preview
    Insert -->|Commit| Results[Actual counts / refreshed views]
    Results -->|Close| Inventory
```

Zero-valid previews disable Import. There is no overwrite/update branch.
The final report's testing section should reference the CSV acceptance matrix
in TEST_PLAN.md, including both chooser/preview cancellation and induced
transaction failure, rather than treating successful parsing as full acceptance.
