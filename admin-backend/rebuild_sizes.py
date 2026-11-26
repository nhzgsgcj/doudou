"""按新尺寸重建缩略图与预览图（适配 2Mbps 小带宽服务器）
缩略图: 900px  q75  (~30-40KB)
预览图: 1600px q72  (~80-120KB)
用法: /opt/doudou-admin/venv/bin/python rebuild_sizes.py
"""
import os
from PIL import Image, ImageOps

BASE = "/var/www/doudou"
JPG_DIR = os.path.join(BASE, "resource", "jpg")
THUMB_DIR = os.path.join(BASE, "resource", "thumbs")
PREVIEW_DIR = os.path.join(BASE, "resource", "previews")

THUMB_MAX, THUMB_Q = 900, 75
PREVIEW_MAX, PREVIEW_Q = 1600, 72

os.makedirs(THUMB_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)

files = [f for f in os.listdir(JPG_DIR) if f.lower().endswith((".jpg", ".jpeg"))]
n = len(files)
for i, f in enumerate(files, 1):
    stem = os.path.splitext(f)[0]
    try:
        im = Image.open(os.path.join(JPG_DIR, f))
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGB":
            im = im.convert("RGB")
        t = im.copy()
        t.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
        t.save(os.path.join(THUMB_DIR, stem + ".webp"), "WEBP", quality=THUMB_Q, method=6)
        p = im.copy()
        p.thumbnail((PREVIEW_MAX, PREVIEW_MAX), Image.LANCZOS)
        p.save(os.path.join(PREVIEW_DIR, stem + ".webp"), "WEBP", quality=PREVIEW_Q, method=6)
    except Exception as e:
        print("失败:", f, e, flush=True)
    if i % 20 == 0:
        print("%d/%d" % (i, n), flush=True)

def total(d):
    return sum(os.path.getsize(os.path.join(d, x)) for x in os.listdir(d)) / 1048576

print("缩略图总量: %.1fMB (平均 %.0fKB)" % (total(THUMB_DIR), total(THUMB_DIR) * 1024 / n))
print("预览图总量: %.1fMB (平均 %.0fKB)" % (total(PREVIEW_DIR), total(PREVIEW_DIR) * 1024 / n))
