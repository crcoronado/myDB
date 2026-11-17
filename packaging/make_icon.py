"""Generates packaging/icon.png (1024x1024): database cylinder + magnifier. Needs Pillow."""
import os
from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# macOS-style rounded square background
d.rounded_rectangle((80, 80, S - 80, S - 80), radius=190, fill=(16, 58, 112, 255))
d.rounded_rectangle((80, 80, S - 80, S - 400), radius=190, fill=(24, 76, 140, 255))
d.rectangle((80, 450, S - 80, S - 400), fill=(24, 76, 140, 255))
# database cylinder
cx, top, w, h, disc = 430, 270, 440, 420, 110
body = (235, 242, 250, 255)
line = (16, 58, 112, 255)
d.rectangle((cx - w // 2, top + disc // 2, cx + w // 2, top + h), fill=body)
d.ellipse((cx - w // 2, top + h - disc // 2, cx + w // 2, top + h + disc // 2), fill=body)
for y in (top + h // 3 + 20, top + 2 * h // 3 + 10):
    d.arc((cx - w // 2, y - disc // 2, cx + w // 2, y + disc // 2), 0, 180, fill=line, width=14)
d.ellipse((cx - w // 2, top, cx + w // 2, top + disc), fill=(200, 215, 235, 255), outline=line, width=10)
# magnifier (saffron)
mx, my, r = 640, 640, 150
gold = (244, 172, 50, 255)
d.line((mx + 95, my + 95, mx + 205, my + 205), fill=gold, width=70)
d.ellipse((mx - r, my - r, mx + r, my + r), outline=gold, width=46, fill=(255, 255, 255, 90))
img.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png"))
print("ok")
