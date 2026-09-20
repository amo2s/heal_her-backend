from PIL import Image

def make_watermark(source_path: str, output_path: str, opacity: float = 0.06):
    logo = Image.open(source_path).convert("RGBA")
    r, g, b, a = logo.split()
    a = a.point(lambda px: int(px * opacity))
    Image.merge("RGBA", (r, g, b, a)).save(output_path)

if __name__ == "__main__":
    make_watermark("src/static/branding/logo_header.png", "src/static/branding/logo_watermark.png")