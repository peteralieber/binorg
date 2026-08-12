# Binorg

Binorg is a small, self-hosted home-inventory app. Create labeled bins, record their contents and item photos, search across bins, scan a QR label to open its bin, and print browser or Bluetooth thermal labels.

## Features

- Bin creation with per-bin QR codes
- HTMX item creation, editing, and deletion
- Image uploads for common web image formats
- Cross-bin item search
- Browser-printable QR labels
- Nimot B1 Pro-compatible ESC/POS raster output over Bluetooth Low Energy

## Run locally

Binorg requires Python 3.10 or later and Bluetooth support only when using thermal printing.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app app run
```

Open `http://127.0.0.1:5000`. The SQLite database is stored in Flask's instance directory. Uploaded photos and generated QR images are stored under `static/`.

## Thermal printer setup

Set the Nimot's Bluetooth address before starting the application:

```sh
export BINORG_PRINTER_ADDRESS='AA:BB:CC:DD:EE:FF'
flask --app app run
```

`BINORG_PRINTER_CHARACTERISTIC` can override the default writable GATT characteristic. The app sends an ESC/POS raster image; confirm your printer supports that protocol and characteristic.

## Tests

```sh
pip install pytest
pytest
```

## Notes

The scanner uses the browser `BarcodeDetector` API and camera permission. On unsupported browsers, scan the label with any QR scanner; the QR code contains the bin's direct URL.
