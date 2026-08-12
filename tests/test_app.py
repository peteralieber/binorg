import io
from pathlib import Path

import pytest

from app import create_app, get_db


@pytest.fixture()
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "inventory.sqlite",
            "UPLOAD_FOLDER": tmp_path / "photos",
            "QR_FOLDER": tmp_path / "qr",
        }
    )
    app.teardown_appcontext_funcs.clear()
    app.teardown_appcontext(lambda error: get_db().close())
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def create_bin(client, name="Garage"):
    return client.post("/bins/new", data={"name": name, "description": "Tools"})


def test_creating_bin_generates_qr_code(client, app):
    response = create_bin(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/bins/1")
    with app.app_context():
        assert get_db().execute("SELECT qr_code_path FROM bins").fetchone()[0] == "qr/bin-1.png"
    assert (Path(app.config["QR_FOLDER"]) / "bin-1.png").exists()


def test_item_lifecycle_and_search(client):
    create_bin(client)
    response = client.post(
        "/bins/1/items",
        data={"name": "Hammer", "description": "Claw hammer", "quantity": "2"},
    )
    assert b"Hammer" in response.data
    response = client.post(
        "/items/1/edit",
        data={"name": "Mallet", "description": "Rubber", "quantity": "3"},
    )
    assert b"Mallet" in response.data
    assert b"Garage" in client.get("/search?q=Mallet").data
    assert b"No items in this bin" in client.post("/items/1/delete").data


def test_photo_upload_and_validation(client, app):
    create_bin(client)
    response = client.post(
        "/bins/1/items",
        data={"name": "Tape", "photo": (io.BytesIO(b"image"), "tape.png")},
    )
    assert response.status_code == 200
    assert len(list(Path(app.config["UPLOAD_FOLDER"]).iterdir())) == 1
    response = client.post(
        "/bins/1/items",
        data={"name": "Bad", "photo": (io.BytesIO(b"bad"), "bad.exe")},
    )
    assert response.status_code == 400


def test_not_found_and_unconfigured_printer(client):
    assert client.get("/bins/99").status_code == 404
    create_bin(client)
    assert client.post("/bins/1/print_combined").status_code == 503
