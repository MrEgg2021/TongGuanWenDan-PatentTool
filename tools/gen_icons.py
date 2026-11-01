from PIL import Image, ImageDraw
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
ASSETS_DIR = os.path.join(ROOT_DIR, "resources", "assets")
SRC_NAME = "logo.png"
SRC_PATH = os.path.join(ASSETS_DIR, SRC_NAME)

if not os.path.exists(SRC_PATH):
    raise SystemExit(f"源图像不存在: {SRC_PATH}")

img = Image.open(SRC_PATH).convert("RGBA")

w, h = img.size
side = min(w, h)
left = (w - side) // 2
top = (h - side) // 2
img = img.crop((left, top, left + side, top + side))

size = 512
img = img.resize((size, size), Image.Resampling.LANCZOS)

mask = Image.new("L", (size, size), 0)
mask_draw = ImageDraw.Draw(mask)
radius = int(size * 0.2)
mask_draw.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)

rounded = Image.new("RGBA", (size, size))
rounded.paste(img, (0, 0), mask=mask)

png_out = os.path.join(ASSETS_DIR, "logo_round.png")
rounded.save(png_out, format="PNG")

ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
ico_out = os.path.join(ASSETS_DIR, "app_icon.ico")
rounded.save(ico_out, format="ICO", sizes=ico_sizes)

print(f"已生成圆角 PNG: {png_out}")
print(f"已生成 ICO 图标: {ico_out}")
