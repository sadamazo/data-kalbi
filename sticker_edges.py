"""Render the panel's sticker pixels with ANSI half blocks."""
from functools import lru_cache
import json
from pathlib import Path

RESET = "\033[0m"
STICKERS = Path(__file__).with_name("sticker_pixels.json")


@lru_cache(maxsize=1)
def pixel_sets():
    return json.loads(STICKERS.read_text(encoding="utf-8"))


def color_code(hex_color):
    return ";".join(str(int(hex_color[i:i + 2], 16)) for i in (0, 2, 4))


def sticker_rows(sticker):
    colors = [color_code(value) for value in sticker["colors"]]
    pixels = sticker["rows"]
    rendered = []
    for upper, lower in zip(pixels[::2], pixels[1::2]):
        row = []
        previous = None
        for top, bottom in zip(upper, lower):
            codes = []
            if top != ".":
                codes.append(f'38;2;{colors[ord(top) - ord("A")]}')
            if bottom != ".":
                mode = 38 if top == "." else 48
                codes.append(f'{mode};2;{colors[ord(bottom) - ord("A")]}')
            style = ";".join(codes)
            if style != previous:
                row.append(f"\033[0;{style}m" if style else RESET)
                previous = style
            row.append("▄" if top == "." and bottom != "." else "▀" if codes else " ")
        rendered.append("".join(row) + RESET)
    return rendered


def sticker_column(sticker, width, height, float_offset):
    rows = [" " * width] * height
    sprite = sticker_rows(sticker)
    start = (height - len(sprite)) // 2 + float_offset
    rows[start:start + len(sprite)] = sprite
    return rows


def with_sticker_edges(banner, columns, floating=False):
    sizes = pixel_sets()
    center_width = len(banner[0].partition("m")[2].partition(RESET)[0])
    width = max((int(size) for size in sizes if center_width + 4 + 2 * int(size) < columns), default=0)
    if not width:
        return banner
    stickers = sizes[str(width)]
    height = len(banner)
    left = sticker_column(stickers["left_face"], width, height, int(floating))
    right = sticker_column(stickers["right_face"], width, height, int(not floating))
    return [f"{a}  {row[4:]}  {b}" for a, row, b in zip(left, banner, right)]
