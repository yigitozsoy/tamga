"""tamga logosu: Göktürk "t" harfi (𐱃, Orhun AT), Segoe UI Historic yazı tipinden çizilir.
Üretir: tamga/assets/logo.png (beyaz, saydam; arayüzde renklendirilir) ve logo.ico (koyu zemin üstünde beyaz)."""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "tamga", "assets")
GLYPH = "\U00010C43"
FONT = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "seguihis.ttf")


def glyph(size, color=(255, 255, 255, 255)):
    font = ImageFont.truetype(FONT, size)
    im = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((size // 2, size // 4), GLYPH, font=font, fill=color)
    return im.crop(im.getbbox())


def main():
    os.makedirs(ASSETS, exist_ok=True)
    g = glyph(420)
    h = 306
    g = g.resize((max(1, round(g.width * h / g.height)), h), Image.LANCZOS)
    g.save(os.path.join(ASSETS, "logo.png"))

    big = 256
    ico = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(ico).rounded_rectangle((8, 8, big - 8, big - 8), radius=56, fill=(15, 15, 15, 255))
    s = glyph(400)
    gh = 150
    s = s.resize((max(1, round(s.width * gh / s.height)), gh), Image.LANCZOS)
    ico.alpha_composite(s, ((big - s.width) // 2, (big - gh) // 2))
    ico.save(os.path.join(ASSETS, "logo.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("logo tamam")


if __name__ == "__main__":
    main()
