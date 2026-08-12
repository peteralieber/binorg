"""Nimot-compatible ESC/POS raster label generation and BLE transport."""

from pathlib import Path

from bleak import BleakClient
from PIL import Image, ImageDraw, ImageFont


def generate_label_image(qr_path: Path, name: str, description: str) -> Image.Image:
    width, padding = 384, 16
    qr = Image.open(qr_path).convert("1").resize((180, 180))
    font = ImageFont.load_default()
    text = "\n".join(part for part in (name, description) if part)
    canvas = Image.new("1", (width, 1), 1)
    text_box = ImageDraw.Draw(canvas).multiline_textbbox((0, 0), text, font=font, align="center")
    text_height = text_box[3] - text_box[1]
    label = Image.new("1", (width, 180 + text_height + padding * 3), 1)
    draw = ImageDraw.Draw(label)
    label.paste(qr, ((width - qr.width) // 2, padding))
    draw.multiline_text(
        (width // 2, 180 + padding * 2), text, font=font, fill=0, anchor="ma", align="center"
    )
    return label


def convert_image_to_raster(image: Image.Image) -> bytes:
    image = image.convert("1")
    width, height = image.size
    if width % 8:
        raise ValueError("Label image width must be divisible by eight.")
    raster = bytearray()
    pixels = image.load()
    for y in range(height):
        for x in range(0, width, 8):
            byte = 0
            for bit in range(8):
                if pixels[x + bit, y] == 0:
                    byte |= 1 << (7 - bit)
            raster.append(byte)
    return bytes(raster)


async def print_bin_label(
    address: str, characteristic: str, qr_path: Path, name: str, description: str
) -> None:
    image = generate_label_image(qr_path, name, description)
    raster = convert_image_to_raster(image)
    width, height = image.size
    header = bytes(
        (0x1B, 0x40, 0x1D, 0x76, 0x30, 0x00, width // 8, 0x00, height & 0xFF, height >> 8)
    )
    async with BleakClient(address) as client:
        await client.write_gatt_char(characteristic, header + raster)
