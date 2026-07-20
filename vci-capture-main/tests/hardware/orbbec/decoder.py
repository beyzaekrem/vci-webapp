#!/usr/bin/env python3
import argparse
from pathlib import Path
from PIL import Image
import io

def looks_like_jpeg(b: bytes) -> bool:
    return len(b) >= 3 and b[0] == 0xFF and b[1] == 0xD8 and b[2] == 0xFF

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, required=True)
    ap.add_argument("--height", type=int, required=True)
    ap.add_argument("--dir", type=Path, default=Path("images"))
    ap.add_argument("--glob", default="color_*.mjpg")
    args = ap.parse_args()

    files = sorted((args.dir).glob(args.glob))
    if not files:
        print(f"no files matching {args.dir}/{args.glob}")
        return

    for p in files:
        data = p.read_bytes()

        if looks_like_jpeg(data):
            img = Image.open(io.BytesIO(data))
            out = p.with_suffix(".jpg")
            img.save(out, "JPEG")
            print("wrote", out)
            continue

        expected = args.width * args.height * 3
        if len(data) == expected:
            img = Image.frombytes("RGB", (args.width, args.height), data)
            out = p.with_suffix(".png")
            img.save(out)
            print("wrote", out)
            continue

        print(f"{p.name}: unknown payload ({len(data)} bytes) "
              f"— not JPEG magic and not {args.width}x{args.height} RGB888 ({expected} bytes)")

if __name__ == "__main__":
    main()
