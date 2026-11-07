#!/usr/bin/env python3
"""Render a self-contained Kindle Scribe grayscale dashboard from demo JSON."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

W, H = 1860, 2480
BG, INK, MUTED, RULE, CARD = 250, 30, 112, 207, 239


def font(size, bold=False, serif=False):
    families = (["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "DejaVuSerif.ttf"] if serif
                else (["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"] if bold
                      else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"]))
    for path in families:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def fit(draw, text, x, y, max_width, size=48, fill=INK, bold=False):
    current = size
    while current > 22 and draw.textbbox((0, 0), text, font=font(current, bold))[2] > max_width:
        current -= 3
    draw.text((x, y), text, font=font(current, bold), fill=fill)


def render(data, output, timestamp):
    im = Image.new("L", (W, H), BG)
    d = ImageDraw.Draw(im)
    left, right = 115, W - 115
    d.text((left, 90), "FIELD NOTES  /  DAILY DISPLAY", font=font(36, True), fill=MUTED)
    d.text((right - 365, 90), "KINDLE SCRIBE", font=font(36), fill=MUTED)
    d.line((left, 161, right, 161), fill=INK, width=5)
    d.text((left, 230), timestamp.strftime("%A, %B %-d"), font=font(67), fill=INK)
    d.text((left, 323), timestamp.strftime("%Y"), font=font(64), fill=MUTED)
    d.text((left, 422), "Your day,", font=font(150, serif=True), fill=INK)
    d.text((left, 587), "at a glance.", font=font(150, serif=True), fill=INK)

    # Weather and date modules. All values come from the local JSON fixture.
    d.rounded_rectangle((left, 880, right, 1270), radius=26, fill=CARD)
    d.text((left+55, 925), "WEATHER  /  DEMONSTRATION", font=font(32, True), fill=MUTED)
    temp = str(data["weather"]["temperature"])
    d.text((left+52, 1001), temp + "°", font=font(170), fill=INK)
    fit(d, data["weather"]["condition"], 650, 1070, 1000, 66, fill=INK)
    fit(d, data["weather"]["detail"], 650, 1170, 950, 36, fill=MUTED)
    # Sun illustration.
    cx, cy, rad = 1470, 1050, 66
    d.ellipse((cx-rad, cy-rad, cx+rad, cy+rad), outline=INK, width=8)
    for dx, dy in [(0,-108),(0,108),(-108,0),(108,0),(-78,-78),(-78,78),(78,-78),(78,78)]:
        length = (dx**2+dy**2)**.5
        sx, sy = cx+dx*0.83, cy+dy*0.83
        ex, ey = cx+dx*1.12, cy+dy*1.12
        d.line((sx,sy,ex,ey), fill=INK, width=7)

    d.text((left, 1375), "TODAY'S AGENDA", font=font(48, True), fill=INK)
    d.line((left, 1454, right, 1454), fill=RULE, width=3)
    for idx, event in enumerate(data["events"][:4]):
        y = 1510 + idx * 153
        d.text((left+4, y+7), str(event["time"]), font=font(49, True), fill=MUTED)
        fit(d, str(event["title"]), 385, y+7, right-385, 63, fill=INK)
        d.line((left, y+115, right, y+115), fill=RULE, width=2)

    d.text((left, 2228), "Small updates. A quieter screen.", font=font(51, serif=True), fill=INK)
    d.line((left, 2335, right, 2335), fill=INK, width=4)
    stamp = timestamp.strftime("%Y-%m-%d %H:%M JST")
    d.text((left, 2364), "SAMPLE DATA  ·  NOT A LIVE FORECAST", font=font(28, True), fill=MUTED)
    box = d.textbbox((0,0),stamp,font=font(28))
    d.text((right-(box[2]-box[0]),2364),stamp,font=font(28),fill=MUTED)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    # Grayscale 8-bit, no alpha, non-interlaced. Optimize makes an economical transfer.
    im.save(output, format="PNG", optimize=True)
    print(f"rendered {output}: {W}x{H}, {Path(output).stat().st_size:,} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="demo.json")
    parser.add_argument("--output", default="site/dashboard.png")
    args = parser.parse_args()
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    render(data, args.output, datetime.now(ZoneInfo("Asia/Tokyo")))
