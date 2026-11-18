
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
    category TEXT NOT NULL CHECK (category IN ('Desktop PC', 'Laptop', 'Router', 'Switch', 'Peripheral', 'Other')),
    serial TEXT CHECK (length(trim(serial)) BETWEEN 1 AND 100),
    serial_key TEXT UNIQUE CHECK ((serial IS NULL) = (serial_key IS NULL)),
    purchase_year INTEGER NOT NULL CHECK (purchase_year BETWEEN 1900 AND 9999),
    price_cents INTEGER CHECK (price_cents BETWEEN 0 AND 99999999999),
    status TEXT NOT NULL CHECK (status IN ('Available', 'Assigned', 'Under Maintenance', 'Retired')),
    assigned_to TEXT NOT NULL DEFAULT '' CHECK (length(assigned_to) <= 120),
    location TEXT NOT NULL DEFAULT '' CHECK (length(location) <= 120),
    notes TEXT NOT NULL DEFAULT '' CHECK (length(notes) <= 4000),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
) STRICT
;
CREATE INDEX assets_category_idx ON assets(category);
CREATE INDEX assets_status_idx ON assets(status);
CREATE INDEX assets_year_idx ON assets(purchase_year);
PRAGMA user_version = 1;
