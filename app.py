import re
from urllib.parse import quote, urlparse

import requests
from flask import Flask, Response, abort, jsonify, request
from flask_cors import CORS
from yt_dlp import YoutubeDL

app = Flask(__name__)
CORS(app)

PIN_RE = re.compile(r"^https?://([\w-]+\.)?(pinterest\.[a-z.]+|pin\.it)/", re.I)


def quality_label(h):
    if h >= 2160:
        return "4K"
    if h >= 1440:
        return "2K"
    if h >= 1080:
        return "Full HD"
    if h >= 720:
        return "HD"
    return "SD %sp" % h if h else "SD"


@app.get("/")
def home():
    return "OK"


@app.post("/api")
def api():
    data = request.get_json(silent=True) or {}
    link = (data.get("url") or "").strip()
    if not PIN_RE.match(link):
        return jsonify(error="Invalid link"), 400
    try:
        with YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as y:
            info = y.extract_info(link, download=False)
    except Exception:
        return jsonify(error="Could not fetch this pin"), 422

    base = request.host_url.rstrip("/")
    downloads, seen = [], set()
    for f in info.get("formats") or []:
        u = f.get("url")
        if not u or f.get("vcodec") in (None, "none"):
            continue
        if f.get("ext") != "mp4" or f.get("protocol") not in ("https", "http"):
            continue
        h = f.get("height") or 0
        label = quality_label(h)
        if label in seen:
            continue
        seen.add(label)
        downloads.append({"h": h, "label": label, "url": "%s/dl?u=%s&n=pinterest-video.mp4" % (base, quote(u, safe=""))})
    downloads.sort(key=lambda d: d["h"])

    if not downloads and info.get("url"):
        downloads.append({"label": "Download", "url": "%s/dl?u=%s&n=pinterest-video.mp4" % (base, quote(info["url"], safe=""))})
    if not downloads:
        return jsonify(error="No video found"), 404

    return jsonify(title=info.get("title") or "Your pin is ready", thumbnail=info.get("thumbnail") or "", downloads=downloads)


@app.get("/dl")
def dl():
    u = request.args.get("u", "")
    host = urlparse(u).hostname or ""
    if not (host == "pinimg.com" or host.endswith(".pinimg.com")):
        abort(400)
    name = re.sub(r"[^\w.-]", "", request.args.get("n", "pinterest-video.mp4")) or "video.mp4"
    r = requests.get(u, stream=True, timeout=20)
    return Response(
        r.iter_content(65536),
        content_type=r.headers.get("Content-Type", "video/mp4"),
        headers={"Content-Disposition": 'attachment; filename="%s"' % name},
    )
