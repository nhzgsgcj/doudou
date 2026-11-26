"""一次性脚本：为 resource/jpg/ 里所有原图批量生成 1920px WebP 预览图
用法: /opt/doudou-admin/venv/bin/python gen_previews.py
"""
import os
from PIL import Image, ImageOps

BASE = "/var/www/doudou"
JPG_DIR = os.path.join(BASE, "resource", "jpg")
PREVIEW_DIR = os.path.join(BASE, "resource", "previews")
MAX_SIDE, Q = 1920, 85

os.makedirs(PREVIEW_DIR, exist_ok=True)
files = [f for f in os.listdir(JPG_DIR) if f.lower().endswith((".jpg", ".jpeg"))]
done = skip = fail = 0
for f in files:
    stem = os.path.splitext(f)[0]
    out = os.path.join(PREVIEW_DIR, stem + ".webp")
    if os.path.exists(out):
        skip += 1
        continue
    try:
        im = Image.open(os.path.join(JPG_DIR, f))
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGB":
            im = im.convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        im.save(out, "WEBP", quality=Q, method=4)
        done += 1
        if done % 20 == 0:
            print("已生成 %d/%d" % (done + skip, len(files)), flush=True)
    except Exception as e:
        fail += 1
        print("失败:", f, e, flush=True)

total = sum(os.path.getsize(os.path.join(PREVIEW_DIR, x)) for x in os.listdir(PREVIEW_DIR))
print("完成: 新生成 %d, 已存在跳过 %d, 失败 %d" % (done, skip, fail))
print("预览图总量: %.1fMB" % (total / 1048576))
