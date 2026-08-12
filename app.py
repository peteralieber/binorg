"""Home inventory web application."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import uuid
from pathlib import Path

import qrcode
from flask import Flask, abort, current_app, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from printer import print_bin_label


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=Path(app.instance_path) / "inventory.sqlite",
        UPLOAD_FOLDER=Path(app.static_folder) / "photos",
        QR_FOLDER=Path(app.static_folder) / "qr",
        PRINTER_ADDRESS=os.environ.get("BINORG_PRINTER_ADDRESS"),
        PRINTER_CHARACTERISTIC=os.environ.get(
            "BINORG_PRINTER_CHARACTERISTIC", "0000ffe1-0000-1000-8000-00805f9b34fb"
        ),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["QR_FOLDER"]).mkdir(parents=True, exist_ok=True)
    with app.app_context():
        init_db()
    app.teardown_appcontext(close_db)

    @app.route("/")
    def index():
        return render_template("index.html", bins=query_db("SELECT * FROM bins ORDER BY name"))

    @app.route("/bins/new", methods=("GET", "POST"))
    def create_bin():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            if not name:
                return (
                    render_view(
                        "create_bin_page.html",
                        "fragments/create_bin_form.html",
                        error="A bin name is required.",
                    ),
                    400,
                )
            db = get_db()
            cursor = db.execute(
                "INSERT INTO bins (name, description) VALUES (?, ?)", (name, description)
            )
            db.commit()
            bin_id = cursor.lastrowid
            qr_filename = f"bin-{bin_id}.png"
            qrcode.make(url_for("scan_redirect", bin_id=bin_id, _external=True)).save(
                Path(current_app.config["QR_FOLDER"]) / qr_filename
            )
            db.execute("UPDATE bins SET qr_code_path = ? WHERE id = ?", (f"qr/{qr_filename}", bin_id))
            db.commit()
            return redirect(url_for("view_bin", bin_id=bin_id))
        return render_view("create_bin_page.html", "fragments/create_bin_form.html")

    @app.route("/bins/<int:bin_id>")
    def view_bin(bin_id: int):
        bin_data = get_bin(bin_id)
        return render_view(
            "bin_page.html",
            "fragments/bin.html",
            bin=bin_data,
            items=query_db("SELECT * FROM items WHERE bin_id = ? ORDER BY name", (bin_id,)),
        )

    @app.route("/bins/<int:bin_id>/items", methods=("POST",))
    def add_item(bin_id: int):
        get_bin(bin_id)
        name = request.form.get("name", "").strip()
        if not name:
            return "An item name is required.", 400
        quantity = request.form.get("quantity", "1")
        try:
            quantity = max(0, int(quantity))
        except ValueError:
            return "Quantity must be a whole number.", 400
        photo_path = save_photo(request.files.get("photo"))
        db = get_db()
        db.execute(
            """INSERT INTO items (bin_id, name, description, quantity, photo_path)
               VALUES (?, ?, ?, ?, ?)""",
            (bin_id, name, request.form.get("description", "").strip(), quantity, photo_path),
        )
        db.commit()
        return render_template(
            "bin_items.html",
            items=query_db("SELECT * FROM items WHERE bin_id = ? ORDER BY name", (bin_id,)),
        )

    @app.route("/items/<int:item_id>/edit", methods=("GET", "POST"))
    def edit_item(item_id: int):
        item = get_item(item_id)
        if request.method == "GET":
            return render_template("edit_item.html", item=item)
        name = request.form.get("name", "").strip()
        if not name:
            return "An item name is required.", 400
        try:
            quantity = max(0, int(request.form.get("quantity", "1")))
        except ValueError:
            return "Quantity must be a whole number.", 400
        photo_path = save_photo(request.files.get("photo")) or item["photo_path"]
        db = get_db()
        db.execute(
            """UPDATE items SET name = ?, description = ?, quantity = ?, photo_path = ?
               WHERE id = ?""",
            (name, request.form.get("description", "").strip(), quantity, photo_path, item_id),
        )
        db.commit()
        return render_template("item_row.html", item=get_item(item_id))

    @app.route("/items/<int:item_id>/cancel")
    def cancel_edit(item_id: int):
        return render_template("item_row.html", item=get_item(item_id))

    @app.route("/items/<int:item_id>/delete", methods=("POST",))
    def delete_item(item_id: int):
        item = get_item(item_id)
        db = get_db()
        db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        db.commit()
        return render_template(
            "bin_items.html",
            items=query_db("SELECT * FROM items WHERE bin_id = ? ORDER BY name", (item["bin_id"],)),
        )

    @app.route("/search")
    def search():
        query = request.args.get("q", "").strip()
        items = []
        if query:
            like_query = f"%{query}%"
            items = query_db(
                """SELECT items.*, bins.name AS bin_name FROM items
                   JOIN bins ON bins.id = items.bin_id
                   WHERE items.name LIKE ? OR items.description LIKE ? ORDER BY items.name""",
                (like_query, like_query),
            )
        return render_template("search_results.html", items=items, query=query)

    @app.route("/scan")
    def scan_page():
        return render_view("scan_page.html", "fragments/scan.html")

    @app.route("/scan/<int:bin_id>")
    def scan_redirect(bin_id: int):
        get_bin(bin_id)
        return redirect(url_for("view_bin", bin_id=bin_id))

    @app.route("/bins/<int:bin_id>/print")
    def print_bin_labels(bin_id: int):
        return render_template("print_labels.html", bins=[get_bin(bin_id)])

    @app.route("/bins/print_all")
    def print_all_labels():
        return render_template("print_labels.html", bins=query_db("SELECT * FROM bins ORDER BY name"))

    @app.route("/bins/<int:bin_id>/print_combined", methods=("POST",))
    def print_combined(bin_id: int):
        bin_data = get_bin(bin_id)
        address = current_app.config["PRINTER_ADDRESS"]
        if not address:
            return "Set BINORG_PRINTER_ADDRESS before printing.", 503
        try:
            asyncio.run(
                print_bin_label(
                    address,
                    current_app.config["PRINTER_CHARACTERISTIC"],
                    Path(current_app.static_folder) / bin_data["qr_code_path"],
                    bin_data["name"],
                    bin_data["description"],
                )
            )
        except Exception:
            current_app.logger.exception("Thermal printer request failed")
            return "Unable to print the label. Check the printer connection.", 502
        return "Label sent to printer."

    return app


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_error=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    get_db().executescript(
        """
        CREATE TABLE IF NOT EXISTS bins (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            qr_code_path TEXT
        );
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            bin_id INTEGER NOT NULL REFERENCES bins(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity >= 0),
            photo_path TEXT
        );
        """
    )
    get_db().commit()


def query_db(query: str, parameters: tuple = ()) -> list[sqlite3.Row]:
    return get_db().execute(query, parameters).fetchall()


def render_view(page_template: str, fragment_template: str, **context):
    template = fragment_template if request.headers.get("HX-Request") == "true" else page_template
    return render_template(template, **context)


def get_bin(bin_id: int) -> sqlite3.Row:
    bin_data = get_db().execute("SELECT * FROM bins WHERE id = ?", (bin_id,)).fetchone()
    if bin_data is None:
        abort(404)
    return bin_data


def get_item(item_id: int) -> sqlite3.Row:
    item = get_db().execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        abort(404)
    return item


def save_photo(photo) -> str | None:
    if photo is None or not photo.filename:
        return None
    filename = secure_filename(photo.filename)
    if not filename:
        return None
    extension = Path(filename).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        abort(400, "Photos must be JPG, PNG, GIF, or WebP files.")
    stored_name = f"{uuid.uuid4().hex}{extension}"
    photo.save(Path(current_app.config["UPLOAD_FOLDER"]) / stored_name)
    return f"photos/{stored_name}"


app = create_app()


if __name__ == "__main__":
    app.run()
