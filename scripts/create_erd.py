"""Generate an editable draw.io ERD from the implemented SQLite v2 schema."""
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory

from src.database import connect, initialize

ROOT = Path(__file__).resolve().parents[1]


def build(destination):
    with TemporaryDirectory() as name:
        database = Path(name) / "schema.sqlite3"
        initialize(database)
        with connect(database) as connection:
            columns = {table: list(connection.execute(f"PRAGMA table_info({table})"))
                       for table in ("categories", "locations", "assets")}
            foreign_keys = list(connection.execute("PRAGMA foreign_key_list(assets)"))
    assert {(r[3], r[2], r[4], r[6]) for r in foreign_keys} == {
        ("category_id", "categories", "id", "RESTRICT"), ("location_id", "locations", "id", "RESTRICT")}
    document = ET.Element("mxfile", host="app.diagrams.net", type="device", version="31.7.0")
    diagram = ET.SubElement(document, "diagram", name="CPIT251 schema 2", id="relational-v2")
    model = ET.SubElement(diagram, "mxGraphModel", dx="1500", dy="1000", grid="1", gridSize="10",
                          page="1", pageScale="1", pageWidth="1500", pageHeight="1000", background="#ffffff")
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    def cell(key, label, x, y, width, height, style, parent="1"):
        item = ET.SubElement(root, "mxCell", id=key, value=label, style=style, vertex="1", parent=parent)
        ET.SubElement(item, "mxGeometry", x=str(x), y=str(y), width=str(width), height=str(height), **{"as": "geometry"})
        return item

    text = "text;html=0;whiteSpace=wrap;align=left;verticalAlign=middle;strokeColor=none;fillColor=none;fontFamily=Arial;fontColor=#101010;"
    cell("title", "CPIT251  /  RELATIONAL INVENTORY", 60, 30, 1380, 55, text+"fontSize=30;fontStyle=1;")
    cell("subtitle", "Implemented schema v2  |  SQLite 3.37+  |  exactly three STRICT application tables", 60, 90, 1380, 45, text+"fontSize=18;")
    position = {"categories": (60, 190, 440), "locations": (60, 520, 440), "assets": (750, 190, 690)}
    titles = {"categories": "CATEGORY  /  categories", "locations": "LOCATION  /  locations", "assets": "ASSET  /  assets"}
    row_height, header = 37, 48
    for table, rows in columns.items():
        x, y, width = position[table]
        height = header + len(rows)*row_height
        cell(table, titles[table], x, y, width, height,
             "swimlane;startSize=48;horizontal=1;rounded=0;collapsible=0;container=1;"
             "fontFamily=Arial;fontSize=20;fontStyle=1;fontColor=#101010;fillColor=#e8effa;"
             "swimlaneFillColor=#ffffff;strokeColor=#202020;strokeWidth=2;align=left;spacingLeft=14;")
        for index, row in enumerate(rows):
            _, name, datatype, not_null, default, pk = row
            flags = ["PK"] if pk else []
            if name.endswith("_id"):
                flags.append("FK")
            if (table != "assets" and name == "name") or name == "serial_key":
                flags.append("UNIQUE")
            if table == "assets" and pk:
                flags.append("AUTOINCREMENT")
            flags.append("NOT NULL" if not_null or pk else "NULL allowed")
            if default is not None:
                flags.append("default " + str(default))
            label = f"{name}   :   {datatype}    [ {', '.join(flags)} ]"
            cell(f"{table}-{name}", label, 0, header+index*row_height, width, row_height,
                 text+"fontSize=15;spacingLeft=14;", table)

    def edge(key, source, target, label, exit_y, entry_y):
        item = ET.SubElement(root, "mxCell", id=key, value=label, edge="1", parent="1", source=source, target=target,
            style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;strokeWidth=2;strokeColor=#202020;"
                  "startArrow=none;endArrow=none;fontFamily=Arial;fontSize=15;fontColor=#101010;labelBackgroundColor=#ffffff;"
                  f"exitX=1;exitY={exit_y};exitDx=0;exitDy=0;entryX=0;entryY={entry_y};entryDx=0;entryDy=0;")
        ET.SubElement(item, "mxGeometry", relative="1", **{"as": "geometry"})

    edge("category-asset", "categories-id", "assets-category_id", "1 category per asset\n0..* assets per category", 0.5, 0.5)
    edge("location-asset", "locations-id", "assets-location_id", "0..1 location per asset\n0..* assets per location", 0.5, 0.5)
    cell("fk1", "assets.category_id -> categories.id\nNOT NULL  |  ON DELETE RESTRICT", 60, 340, 620, 85, text+"fontSize=17;")
    cell("fk2", "assets.location_id -> locations.id\nNullable  |  ON DELETE RESTRICT", 60, 670, 620, 85, text+"fontSize=17;")
    cell("notes", "INTEGRITY AND DISPLAY\nPK = primary key   |   FK = foreign key   |   0..* = zero or many\nEach application connection enables foreign_keys before its transaction.\nLocations: trim whitespace + Unicode casefold identity; retain first display spelling.\nNo stored operational flag: status and age continue to drive the existing reports.",
         60, 810, 1380, 155, text+"fontSize=18;spacingTop=0;")
    Path(destination).write_text(ET.tostring(document, encoding="unicode")+"\n", encoding="utf-8")


if __name__ == "__main__":
    build(ROOT / "docs/diagrams/inventory-v2.drawio")
