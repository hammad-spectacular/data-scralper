"""
build_assets.py
---------------
Downloads the real Eds Hair imagery from the live Shopify CDN and produces
optimised, responsive WebP assets for the rebuilt site.

Why this exists
---------------
The live site ships ~3.8 MB of imagery, including a 763 KB PNG hero banner,
with only 10/50 images using srcset and zero native lazy-loading. That is the
single biggest cause of its Lighthouse Performance score of 33.

This script:
  1. fetches each source image once (cached to disk),
  2. strips EXIF + converts to WebP,
  3. emits 400/800/1200 px variants,
  4. writes a manifest.json the HTML generator consumes.

Run:  python build_assets.py
"""

from __future__ import annotations

import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).parent
RAW = ROOT / "assets" / "raw"
OUT = ROOT / "assets" / "img"
MANIFEST = ROOT / "assets" / "manifest.json"

CDN = "https://edshair.co.uk/cdn/shop/files/"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}

# name -> (remote path, target widths)
# The 2048x originals are the master; we downscale from those for max quality.
IMAGES = {
    "hero":         ("Eds-Hair-Brazilian-Blowout-Blondes-2_2048x.jpg", [640, 960, 1440]),
    "hero-mobile":  ("Eds-Hair-Brazilian-Blowout-Blondes-2_2048x.jpg", [640, 960]),
    "blowout":      ("Eds-Hair-Brazilian-Blowout-Blowdry-HH2_1200x.jpg", [640, 960]),
    "beforeafter":  ("Eds-Hair-Brazilian-Blowdry-Before-After-Blonde_2048x.jpg", [640, 960]),
    "colour":       ("Eds-Hair-Colour-HH3_1200x.jpg", [640, 960]),
    "colour2":      ("Eds-Hair-Colour-2_2048x.jpg", [640, 960]),
    "styling":      ("Eds-Hair-Styling_1200x.jpg", [640, 960]),
    "cuts":         ("Eds-Hair-Cuts-2_2048x.jpg", [640, 960]),
    "texture":      ("Ed_sHair2_7b5bfdc7-0dc3-44b5-9d44-d2c9083f4a04_1200x.jpg", [480, 800]),
    "gift":         ("ABC_Social_Media_6_HR_2_1200x.JPEG", [640, 960]),
    "contact":      ("Eds-Hair-Contact-Us-03_2048x.jpg", [640, 960]),
    "portrait":     ("Eds-Hair-Magale-Testimonial-2_2048x.jpg", [320, 640]),
    "redhead":      ("Testimonial-Redheads_2048x.jpg", [320, 640]),
    "blonde":       ("Eds-Hair-Testimonials-Blonde_2048x.jpg", [320, 640]),
    "product-ghd-black":  ("ghd_Sculpt_Black_580x@2x.png", [400, 600]),
    "product-ghd-white":  ("ghd_Sculpt_White_580x@2x.png", [400, 600]),
    "product-k18":        ("MAIN_K18_Salon_Blowout_At_Home_Set__77901_580x@2x.webp", [400, 600]),
    "product-abc":        ("ABC-Beautifying-Rich-Oil-Bottle-teaser_580x@2x.webp", [400, 600]),
    "product-ghd-speed":  ("744_PDP_GalleryImage_1_UK_Roundel_580x@2x.jpg", [400, 600]),
    "product-ghd-speed2": ("745_PDP_GalleryImage_Speed_1_Global_580x@2x.jpg", [400, 600]),
    "product-ghd-743":    ("743_PDP_GalleryImage_1_Global_580x@2x.jpg", [400, 600]),
    "logo":               ("EdsHair_Brandmark_32bWeb_280x@2x.png", [280, 560]),
}


def fetch(name: str, remote: str) -> Path:
    """Download a source image once and cache it locally as raw bytes."""
    dest = RAW / f"{name}{Path(remote).suffix.lower()}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = CDN + remote
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            print(f"  fetched {name:22} {len(r.content):>9,} B")
            return dest
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                print(f"  FAILED {name}: {e}")
                return dest
            time.sleep(2 * (attempt + 1))
    return dest


def optimise(name: str, src: Path, widths: list[int]) -> dict:
    """Convert one source into WebP variants. Returns the manifest entry."""
    entry: dict = {"widths": [], "files": [], "ratio": 1.0}
    if not src.exists() or src.stat().st_size == 0:
        return entry

    try:
        im = Image.open(src)
        im.load()
    except Exception as e:  # noqa: BLE001
        print(f"  UNREADABLE {name}: {e}")
        return entry

    # Normalise orientation, drop metadata (EXIF GPS bloat), convert to RGB.
    from PIL import ImageOps

    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "P", "LA"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")

    entry["ratio"] = round(im.width / im.height, 4)

    for w in widths:
        if w > im.width:
            w = im.width
        out = im if w == im.width else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        fname = f"{name}-{w}.webp"
        dest = OUT / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        out.save(dest, "WEBP", quality=78, method=6)
        if w not in entry["widths"]:
            entry["widths"].append(w)
            entry["files"].append(fname)

    print(f"  optimised {name:22} {im.width}x{im.height} -> {entry['widths']}")
    return entry


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    print("Downloading source images...")
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(lambda kv: fetch(kv[0], kv[1][0]), IMAGES.items()))

    print("Optimising to WebP...")
    manifest: dict = {}
    for name, (remote, widths) in IMAGES.items():
        src = RAW / f"{name}{Path(remote).suffix.lower()}"
        manifest[name] = optimise(name, src, widths)

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    total = sum(f.stat().st_size for f in OUT.glob("*.webp"))
    print(f"\nTotal optimised image payload: {total:,} bytes ({total/1024:.0f} KB)")
    print(f"Manifest -> {MANIFEST}")


if __name__ == "__main__":
    main()
