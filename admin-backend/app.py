"""doudou 照片后台 - 上传/列表/删除
静态站根目录: /var/www/doudou  照片列表: data/photos.json
运行: waitress-serve --listen=127.0.0.1:8787 app:app
"""
import io
import json
import os
import time
import hashlib
import secrets
import threading

from flask import Flask, request, session, jsonify, send_file
from PIL import Image, ImageOps

BASE = "/var/www/doudou"
PHOTOS_JSON = os.path.join(BASE, "data", "photos.json")
JPG_DIR = os.path.join(BASE, "resource", "jpg")
THUMB_DIR = os.path.join(BASE, "resource", "thumbs")
PREVIEW_DIR = os.path.join(BASE, "resource", "previews")
CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif"}
MAX_FILE = 30 * 1024 * 1024  # 单文件 30MB
THUMB_MAX = 900              # 缩略图最长边（适配小带宽）
THUMB_Q = 75
PREVIEW_MAX = 1600           # 弹窗预览图最长边（适配小带宽）
PREVIEW_Q = 72

with open(CONF, "r", encoding="utf-8") as f:
    _cfg = json.load(f)
SECRET = _cfg["secret_key"]
PWD_HASH = _cfg["password_hash"]  # "salt$hex"

app = Flask(__name__)
app.secret_key = SECRET
app.config["MAX_CONTENT_LENGTH"] = 120 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# 登录失败限速：连续失败 5 次锁 5 分钟
_fail_lock = threading.Lock()
_fail = {"n": 0, "t": 0.0}


def _check_pw(pw: str) -> bool:
    try:
        salt, hexd = PWD_HASH.split("$", 1)
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
        return secrets.compare_digest(calc, hexd)
    except Exception:
        return False


def _locked() -> bool:
    with _fail_lock:
        return _fail["n"] >= 5 and time.time() - _fail["t"] < 300


def _fail_add():
    with _fail_lock:
        if time.time() - _fail["t"] > 300:
            _fail["n"] = 0
        _fail["n"] += 1
        _fail["t"] = time.time()


def _fail_reset():
    with _fail_lock:
        _fail["n"] = 0


def auth_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("auth"):
            return jsonify(ok=False, error="未登录"), 401
        return fn(*a, **kw)

    return wrapper


def load_photos():
    with open(PHOTOS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def save_photos(data):
    """先备份再原子写入"""
    os.makedirs(os.path.dirname(PHOTOS_JSON), exist_ok=True)
    if os.path.exists(PHOTOS_JSON):
        with open(PHOTOS_JSON, "r", encoding="utf-8") as f:
            bak = os.path.join(BASE, "data", "photos.json.bak")
            with open(bak, "w", encoding="utf-8") as g:
                g.write(f.read())
    tmp = PHOTOS_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PHOTOS_JSON)


def make_thumb(im: Image.Image, out_path: str):
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    im.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
    im.save(out_path, "WEBP", quality=THUMB_Q, method=4)


def make_preview(im: Image.Image, out_path: str):
    """弹窗预览图：1920px WebP，体积约为原图的 1/6，秒开"""
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    im.thumbnail((PREVIEW_MAX, PREVIEW_MAX), Image.LANCZOS)
    im.save(out_path, "WEBP", quality=PREVIEW_Q, method=4)


def unique_name(ext: str) -> str:
    t = time.strftime("%Y%m%d_%H%M%S")
    return "%s_%s%s" % (t, secrets.token_hex(2), ext)


@app.get("/api/check")
def check():
    return jsonify(ok=True, auth=bool(session.get("auth")))


@app.post("/api/login")
def login():
    if _locked():
        return jsonify(ok=False, error="失败次数过多，请 5 分钟后再试"), 429
    data = request.get_json(silent=True) or {}
    if _check_pw(str(data.get("password", ""))):
        _fail_reset()
        session.clear()
        session["auth"] = True
        session.permanent = True
        return jsonify(ok=True)
    _fail_add()
    return jsonify(ok=False, error="密码错误"), 401


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/photos")
@auth_required
def photos():
    return jsonify(ok=True, photos=load_photos())


@app.post("/api/upload")
@auth_required
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify(ok=False, error="没有收到文件"), 400
    today = time.strftime("%Y-%m-%d")
    data = load_photos()
    added, errors = [], []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext == ".jpeg":
            ext = ".jpg"
        if ext not in ALLOWED_EXT:
            errors.append({"file": f.filename, "error": "不支持的格式 " + ext})
            continue
        raw = f.read()
        if len(raw) > MAX_FILE:
            errors.append({"file": f.filename, "error": "文件超过 30MB"})
            continue
        try:
            im = Image.open(io.BytesIO(raw))
            im.load()
        except Exception:
            errors.append({"file": f.filename, "error": "无法解析为图片"})
            continue
        try:
            im = ImageOps.exif_transpose(im)
            if ext in (".gif",):
                im0 = im.convert("RGB")
            else:
                im0 = im
            # 统一转 JPEG 存原图（透明通道铺白底）
            if im0.mode in ("RGBA", "LA", "P"):
                im0 = im0.convert("RGBA")
                bg = Image.new("RGB", im0.size, (255, 255, 255))
                bg.paste(im0, mask=im0.split()[-1])
                im0 = bg
            elif im0.mode != "RGB":
                im0 = im0.convert("RGB")
            name = unique_name(".jpg")
            os.makedirs(JPG_DIR, exist_ok=True)
            os.makedirs(THUMB_DIR, exist_ok=True)
            os.makedirs(PREVIEW_DIR, exist_ok=True)
            im0.save(os.path.join(JPG_DIR, name), "JPEG", quality=90)
            make_thumb(im0, os.path.join(THUMB_DIR, os.path.splitext(name)[0] + ".webp"))
            make_preview(im0, os.path.join(PREVIEW_DIR, os.path.splitext(name)[0] + ".webp"))
            entry = {"src": "/resource/jpg/" + name, "title": today, "date": today}
            data.insert(0, entry)
            added.append(entry)
        except Exception as e:
            errors.append({"file": f.filename, "error": "处理失败: %s" % e})
    if added:
        save_photos(data)
    return jsonify(ok=True, added=added, errors=errors, total=len(data))


@app.post("/api/delete")
@auth_required
def delete():
    src = (request.get_json(silent=True) or {}).get("src", "")
    src = "/" + src.lstrip("/")
    if not src.startswith("/resource/jpg/") or ".." in src:
        return jsonify(ok=False, error="非法路径"), 400
    data = load_photos()
    idx = next((i for i, p in enumerate(data) if p.get("src") == src), None)
    if idx is None:
        return jsonify(ok=False, error="列表中不存在"), 404
    entry = data.pop(idx)
    name = os.path.basename(src)
    stem = os.path.splitext(name)[0]
    for p in (os.path.join(JPG_DIR, name),
              os.path.join(THUMB_DIR, stem + ".webp"),
              os.path.join(PREVIEW_DIR, stem + ".webp")):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass
    save_photos(data)
    return jsonify(ok=True, removed=entry, total=len(data))


@app.get("/admin")
def admin_page():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin.html"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8787)
