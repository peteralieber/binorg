Absolutely, Peter — here is **one single, complete, consolidated project page** that combines:

- All code files we’ve built  
- All features  
- All reasoning  
- All requirements  
- All architecture decisions  
- All thermal‑printer integration logic  
- All HTMX + Flask interactions  
- All item photo support  
- All QR generation + scanning  
- All label printing logic (including Nimot B1 Pro BLE raster printing)  

This is a **full project blueprint**, ready to drop into a Copilot Page.

I’ve structured it cleanly so you can scroll, understand, and build from it.

---

# 🧩 Home Inventory System — Full Project Blueprint  
**Flask + HTMX + SQLite + QR Codes + Nimot B1 Pro Thermal Printing + Item Photos**

A complete, server‑rendered, HTMX‑enhanced home inventory system designed for simplicity, durability, and long‑term maintainability. Runs on your home server, works on any device, and prints labels directly to your Nimot B1 Pro via Bluetooth.

---

# 🧠 Project Philosophy  
This project is intentionally built around:

### **1. Server‑rendered HTML**  
No SPA, no React, no client-side state.  
Flask renders HTML; HTMX swaps fragments.

### **2. Minimal JavaScript**  
Only used for QR scanning and BLE printing triggers.

### **3. Durable architecture**  
SQLite + Flask + HTMX = zero complexity, maximum longevity.

### **4. Full offline capability**  
Everything runs on your home network.

### **5. Thermal printing integration**  
Direct BLE printing to Nimot B1 Pro using raster images.

### **6. Family-friendly UX**  
Scan → view bin → add items → print labels.

---

# 🧱 Requirements Summary  
### Functional Requirements  
- Create bins  
- Generate QR codes for bins  
- Scan QR codes to open bins  
- Add/edit/delete items  
- Upload item photos  
- Search items  
- Print labels (QR only or QR + text + photo)  
- Print all labels  
- Print via Nimot B1 Pro Bluetooth  

### Technical Requirements  
- Python 3  
- Flask  
- HTMX  
- SQLite  
- Pillow  
- Bleak (BLE printing)  
- QRCode library  
- Minimal JS for scanning  
- Raster conversion for thermal printing  

---

# 📁 Project Structure

```
inventory_app/
│
├── app.py
├── db.py
├── models.py
│
├── static/
│   ├── css/
│   │   ├── styles.css
│   │   └── print.css
│   ├── js/
│   │   ├── qr_scanner.js
│   │   └── printer.js
│   ├── qr/
│   └── photos/
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── bin.html
│   ├── bin_items.html
│   ├── item_row.html
│   ├── edit_item.html
│   ├── create_bin.html
│   ├── scan.html
│   └── print_labels.html
│
└── requirements.txt
```

---

# 🐍 Full `app.py` (Main Application)

```python
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import qrcode
import os
import uuid
import asyncio
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
from bleak import BleakClient

app = Flask(__name__)

DB_PATH = "inventory.db"
QR_DIR = "static/qr"
PHOTO_DIR = "static/photos"
PRINTER_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
PRINTER_MAC = "XX:XX:XX:XX:XX:XX"  # Replace with your Nimot B1 Pro MAC


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------------------
# Home Page
# ------------------------------
@app.route("/")
def index():
    db = get_db()
    bins = db.execute("SELECT * FROM bins").fetchall()
    return render_template("index.html", bins=bins)


# ------------------------------
# Create Bin
# ------------------------------
@app.route("/bins/new", methods=["GET", "POST"])
def create_bin():
    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]

        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO bins (name, description) VALUES (?, ?)", (name, description))
        bin_id = cursor.lastrowid
        db.commit()

        # Generate QR code
        qr_path = os.path.join(QR_DIR, f"bin_{bin_id}.png")
        img = qrcode.make(str(bin_id))
        img.save(qr_path)

        cursor.execute("UPDATE bins SET qr_code_path = ? WHERE id = ?", (qr_path, bin_id))
        db.commit()

        return redirect(url_for("view_bin", bin_id=bin_id))

    return render_template("create_bin.html")


# ------------------------------
# View Bin
# ------------------------------
@app.route("/bins/<int:bin_id>")
def view_bin(bin_id):
    db = get_db()
    bin_data = db.execute("SELECT * FROM bins WHERE id = ?", (bin_id,)).fetchone()
    items = db.execute("SELECT * FROM items WHERE bin_id = ?", (bin_id,)).fetchall()
    return render_template("bin.html", bin=bin_data, items=items)


# ------------------------------
# Add Item
# ------------------------------
@app.route("/bins/<int:bin_id>/items", methods=["POST"])
def add_item(bin_id):
    name = request.form["name"]
    description = request.form["description"]
    quantity = request.form.get("quantity", 1)

    photo = request.files.get("photo")
    photo_path = None

    if photo:
        filename = secure_filename(f"{uuid.uuid4()}_{photo.filename}")
        full_path = os.path.join(PHOTO_DIR, filename)
        photo.save(full_path)
        photo_path = full_path

    db = get_db()
    db.execute(
        "INSERT INTO items (bin_id, name, description, quantity, photo_path) VALUES (?, ?, ?, ?, ?)",
        (bin_id, name, description, quantity, photo_path),
    )
    db.commit()

    items = db.execute("SELECT * FROM items WHERE bin_id = ?", (bin_id,)).fetchall()
    return render_template("bin_items.html", items=items)


# ------------------------------
# Edit Item
# ------------------------------
@app.route("/items/<int:item_id>/edit", methods=["GET"])
def edit_item_form(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return render_template("edit_item.html", item=item)


@app.route("/items/<int:item_id>/edit", methods=["POST"])
def edit_item(item_id):
    name = request.form["name"]
    description = request.form["description"]
    quantity = request.form["quantity"]

    photo = request.files.get("photo")
    db = get_db()

    if photo:
        filename = secure_filename(f"{uuid.uuid4()}_{photo.filename}")
        full_path = os.path.join(PHOTO_DIR, filename)
        photo.save(full_path)
        db.execute("""
            UPDATE items 
            SET name = ?, description = ?, quantity = ?, photo_path = ?
            WHERE id = ?
        """, (name, description, quantity, full_path, item_id))
    else:
        db.execute("""
            UPDATE items 
            SET name = ?, description = ?, quantity = ?
            WHERE id = ?
        """, (name, description, quantity, item_id))

    db.commit()

    item = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return render_template("item_row.html", item=item)


@app.route("/items/<int:item_id>/cancel")
def cancel_edit(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return render_template("item_row.html", item=item)


# ------------------------------
# Delete Item
# ------------------------------
@app.route("/items/<int:item_id>/delete", methods=["POST"])
def delete_item(item_id):
    db = get_db()
    bin_id = db.execute("SELECT bin_id FROM items WHERE id = ?", (item_id,)).fetchone()["bin_id"]
    db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()

    items = db.execute("SELECT * FROM items WHERE bin_id = ?", (bin_id,)).fetchall()
    return render_template("bin_items.html", items=items)


# ------------------------------
# Search
# ------------------------------
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    db = get_db()

    if query:
        items = db.execute("""
            SELECT items.*, bins.name AS bin_name
            FROM items
            JOIN bins ON items.bin_id = bins.id
            WHERE items.name LIKE ? OR items.description LIKE ?
        """, (f"%{query}%", f"%{query}%")).fetchall()
    else:
        items = []

    return render_template("search_results.html", items=items, query=query)


# ------------------------------
# QR Scan Page
# ------------------------------
@app.route("/scan")
def scan_page():
    return render_template("scan.html")


@app.route("/scan/<int:bin_id>")
def scan_redirect(bin_id):
    return redirect(url_for("view_bin", bin_id=bin_id))


# ------------------------------
# Printable Label Sheets
# ------------------------------
@app.route("/bins/<int:bin_id>/print")
def print_bin_labels(bin_id):
    db = get_db()
    bin_data = db.execute("SELECT * FROM bins WHERE id = ?", (bin_id,)).fetchone()
    return render_template("print_labels.html", bins=[bin_data])


@app.route("/bins/print_all")
def print_all_labels():
    db = get_db()
    bins = db.execute("SELECT * FROM bins").fetchall()
    return render_template("print_labels.html", bins=bins)


# ------------------------------
# Combined QR + Text + Photo Label (BLE Printing)
# ------------------------------
def generate_label_image(qr_path, name, description, photo_path=None):
    canvas_width = 384
    padding = 20

    qr = Image.open(qr_path).convert("1").resize((200, 200))
    font = ImageFont.load_default()

    dummy = Image.new("1", (canvas_width, 100))
    draw = ImageDraw.Draw(dummy)
    name_w, name_h = draw.textsize(name, font=font)
    desc_w, desc_h = draw.textsize(description, font=font)

    photo_h = 150 if photo_path else 0

    total_height = 200 + name_h + desc_h + photo_h + padding * 4
    img = Image.new("1", (canvas_width, total_height), 1)
    draw = ImageDraw.Draw(img)

    img.paste(qr, ((canvas_width - 200) // 2, padding))

    text_y = 200 + padding * 2
    draw.text(((canvas_width - name_w) // 2, text_y), name, font=font, fill=0)
    text_y += name_h + 10
    draw.text(((canvas_width - desc_w) // 2, text_y), description, font=font, fill=0)

    if photo_path:
        photo = Image.open(photo_path).convert("1").resize((150, 150))
        img.paste(photo, ((canvas_width - 150) // 2, text_y + desc_h + 20))

    return img


def convert_image_to_raster(img):
    width, height = img.size
    pixels = img.load()
    raster = bytearray()

    for y in range(height):
        row = 0
        for x in range(width):
            if pixels[x, y] == 0:
                row |= (1 << (7 - (x % 8)))
            if x % 8 == 7:
                raster.append(row)
                row = 0
        if width % 8 != 0:
            raster.append(row)

    return raster, width, height


async def print_label(address, qr_path, name, description, photo_path):
    img = generate_label_image(qr_path, name, description, photo_path)
    raster, width, height = convert_image_to_raster(img)

    header = bytearray([
        0x1B, 0x40,
        0x1D, 0x76, 0x30, 0x00,
        width // 8, 0x00,
        height & 0xFF, (height >> 8) & 0xFF
    ])

    data = header + raster

    async with BleakClient(address) as client:
        await client.write_gatt_char(PRINTER_UUID, data)


@app.route("/bins/<int:bin_id>/print_combined", methods=["POST"])
def print_combined(bin_id):
    db = get_db()
    bin_data = db.execute("SELECT * FROM bins WHERE id = ?", (bin_id,)).fetchone()

    asyncio.run(print_label(
        PRINTER_MAC,
        bin_data["qr_code_path"],
        bin_data["name"],
        bin_data["description"],
        None
    ))

    return "Printed combined label!"


if __name__ == "__main__":
    os.makedirs(QR_DIR, exist_ok=True)
    os.makedirs(PHOTO_DIR, exist_ok=True)
    app.run(debug=True)
```

---

# 📄 All Templates  
*(Included exactly as used in the app)*

### `base.html`
```html
<!DOCTYPE html>
<html>
<head>
    <title>Inventory</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
<header>
    <h1>Home Inventory</h1>
    <nav>
        <a href="/">Bins</a>
        <a href="/bins/new">Create Bin</a>
        <a href="/scan">Scan</a>
        <a href="/bins/print_all" target="_blank">Print All Labels</a>
    </nav>
</header>

<main>
    {% block content %}{% endblock %}
</main>
</body>
</html>
```

### `index.html`
```html
{% extends "base.html" %}
{% block content %}
<h2>All Bins</h2>

<input 
    type="text"
    placeholder="Search items..."
    hx-get="/search"
    hx-trigger="keyup changed delay:300ms"
    hx-target="#search-results"
    hx-swap="innerHTML">

<div id="search-results"></div>

<ul>
{% for bin in bins %}
    <li><a href="/bins/{{ bin.id }}">{{ bin.name }}</a></li>
{% endfor %}
</ul>
{% endblock %}
```

### `create_bin.html`
```html
{% extends "base.html" %}
{% block content %}
<h2>Create New Bin</h2>

<form method="POST">
    <label>Name</label>
    <input name="name">

    <label>Description</label>
    <input name="description">

    <button type="submit">Create</button>
</form>
{% endblock %}
```

### `bin.html`
```html
{% extends "base.html" %}
{% block content %}
<h2>{{ bin.name }}</h2>
<p>{{ bin.description }}</p>

<img src="/{{ bin.qr_code_path }}" width="150">

<a href="/bins/{{ bin.id }}/print" target="_blank">Print QR Labels</a>

<button
    hx-post="/bins/{{ bin.id }}/print_combined"
    hx-target="#print-status"
    hx-swap="innerHTML">
    Print Combined Label
</button>

<div id="print-status"></div>

<h3>Items</h3>
<div id="item-list">
    {% include "bin_items.html" %}
</div>

<h3>Add Item</h3>
<form 
    hx-post="/bins/{{ bin.id }}/items"
    hx-target="#item-list"
    hx-swap="innerHTML"
    enctype="multipart/form-data">

    <input name="name" placeholder="Item name">
    <input name="description" placeholder="Description">
    <input name="quantity" type="number" value="1">
    <input type="file" name="photo">

    <button type="submit">Add</button>
</form>
{% endblock %}
```

### `bin_items.html`
```html
<ul>
{% for item in items %}
    <li id="item-{{ item.id }}">
        {{ item.name }} — {{ item.quantity }}

        {% if item.photo_path %}
            <br><img src="/{{ item.photo_path }}" width="120">
        {% endif %}

        <button 
            hx-get="/items/{{ item.id }}/edit"
            hx-target="#item-{{ item.id }}"
            hx-swap="outerHTML">
            Edit
        </button>

        <button
            hx-post="/items/{{ item.id }}/delete"
            hx-target="#item-list"
            hx-swap="innerHTML">
            Delete
        </button>
    </li>
{% endfor %}
</ul>
```

### `item_row.html`
```html
<li id="item-{{ item.id }}">
    {{ item.name }} — {{ item.quantity }}

    {% if item.photo_path %}
        <br><img src="/{{ item.photo_path }}" width="120">
    {% endif %}

    <button 
        hx-get="/items/{{ item.id }}/edit"
        hx-target="#item-{{ item.id }}"
        hx-swap="outerHTML">
        Edit
    </button>

    <button
        hx-post="/items/{{ item.id }}/delete"
        hx-target="#item-list"
        hx-swap="innerHTML">
        Delete
    </button>
</li>
```

### `edit_item.html`
```html
<li id="item-{{ item.id }}">
    <form 
        hx-post="/items/{{ item.id }}/edit"
        hx-target="#item-{{ item.id }}"
        hx-swap="outerHTML"
        enctype="multipart/form-data">

        <input name="name" value="{{ item.name }}">
        <input name="description" value="{{ item.description }}">
        <input name="quantity" type="number" value="{{ item.quantity }}">

        {% if item.photo_path %}
            <img src="/{{ item.photo_path }}" width="120"><br>
        {% endif %}

        <input type="file" name="photo">

        <button type="submit">Save</button>
        <button 
            type="button"
            hx-get="/items/{{ item.id }}/cancel"
            hx-target="#item-{{ item.id }}"
            hx-swap="outerHTML">
            Cancel
        </button>
    </form>
</li>
```

### `scan.html`
```html
{% extends "base.html" %}
{% block content %}
<h2>Scan a Bin QR