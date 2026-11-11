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

```mermaid
erDiagram
    ASSETS {
        integer id PK
        text name
        text category
        text serial
        text serial_key UK
        integer purchase_year
        integer price_cents
        text status
        text assigned_to
        text location
        text notes
        text created_at
        text updated_at
    }
```

The system has one business entity. See the schema document for nullability,
money storage and internal SQLite metadata.

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

The enhancement adds no table or schema version. The report exporter remains;
`export_inventory` supplies the missing full-record interchange format.

```mermaid
flowchart LR
    Operator[Operator] -->|Select file| GUI[InventoryApp / native chooser]
    CSV[UTF-8 CSV] --> Parser[csv.reader / validate_headers]
    GUI -->|Worker prepares snapshot| Parser
    Parser --> Validator[Existing validate_asset]
    Validator --> Dedup[Serial duplicate detection]
    DB[(Existing assets table)] -->|Read-only serial keys| Dedup
    Dedup --> Preview[Immutable ImportPreview]
    Preview -->|Queue / main thread| Dialog[ImportPreviewDialog]
    Dialog -->|Explicit confirmation| Batch[import_prepared]
    Batch -->|Revalidate / recheck serials| Tx[BEGIN IMMEDIATE]
    Tx -->|Shared parameterized insert| DB
    Tx --> Result[Commit all or rollback all]
    Result -->|Queue / main thread| Views[Results and refreshed views]
```

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
