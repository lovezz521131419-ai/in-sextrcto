from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from urllib.parse import urlparse
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from parth_dl import get_info, DownloadError
from parth_dl.utils import select_format

app = FastAPI(title="AI Visual Studio Instagram Extractor", version="1.0.0")

# Restrict browser callers to the user's site by default. Add preview origins via env if needed.
origins = ["https://tekisss.netlify.app", "http://localhost:8888", "http://127.0.0.1:8888"]
origins += [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

class ExtractRequest(BaseModel):
    url: HttpUrl

# Lightweight per-process throttle; service should be used for personal, low-volume extraction.
_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "8"))


def validate_instagram_url(raw: str) -> str:
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or host not in ("instagram.com", "www.instagram.com", "m.instagram.com"):
        raise ValueError("请提供 instagram.com 的帖子链接。")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[0] not in ("p", "reel", "tv"):
        raise ValueError("目前只支持公开帖子 /p/、Reel /reel/ 或 IGTV /tv/ 链接，不支持个人主页、Stories 或 Highlights。")
    return f"https://www.instagram.com/{parts[0]}/{parts[1]}/"


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    with _lock:
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return False
        q.append(now)
    return True


@app.get("/health")
def health():
    return {"ok": True, "service": "ai-visual-studio-instagram-extractor", "version": app.version}


@app.post("/extract")
def extract(body: ExtractRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"ok": False, "error": "请求过于频繁，请稍等一分钟再试。"})
    try:
        url = validate_instagram_url(str(body.url))
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})

    try:
        info = get_info(url)
    except Exception as exc:
        message = str(exc)[:500]
        lower = message.lower()
        if any(term in lower for term in ("login", "checkpoint", "not available", "rate limit", "429", "403")):
            friendly = "Instagram 没有向当前未登录请求提供媒体数据，或触发访问限制。请稍后重试；本服务不会索取你的密码或绕过访问控制。"
        else:
            friendly = "提取失败：Instagram 可能返回登录墙、限制请求，或当前链接不可公开访问。详细信息：" + message
        return JSONResponse(status_code=422, content={"ok": False, "error": friendly})

    entries = info.get("entries") or []
    media_items = []
    for index, entry in enumerate(entries, start=1):
        kind = entry.get("kind") or "image"
        formats = entry.get("formats") or []
        if not formats:
            continue
        try:
            best = select_format(formats, "best")
        except Exception:
            best = max(formats, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0))
        item = {
            "index": index,
            "kind": kind,
            "url": best.get("url"),
            "width": best.get("width"),
            "height": best.get("height"),
            "format_id": best.get("format_id"),
        }
        if item["url"]:
            media_items.append(item)

    if not media_items:
        return JSONResponse(status_code=422, content={"ok": False, "error": "提取引擎没有返回可用的媒体文件地址。可能是登录墙、访问限制，或该帖子没有可公开读取的媒体。"})

    image_items = [item for item in media_items if item["kind"] == "image"]
    # For a single image post, older extractor versions may label entries differently; keep non-video media as preview candidates.
    if not image_items and info.get("type") == "image":
        image_items = media_items

    return {
        "ok": True,
        "data": {
            "id": info.get("id"),
            "title": info.get("title") or "",
            "uploader": info.get("uploader") or "",
            "type": info.get("type") or "unknown",
            "description": info.get("title") or "",
            "finalUrl": url,
            "images": [item["url"] for item in image_items],
            "mediaItems": media_items,
            "imageDetails": image_items,
            "methods": ["parth-dl public extractor"],
            "warnings": ["CDN 图片链接可能过期，请提取后尽快打开或保存。", "Instagram 提供的文件不一定等于作者上传前的原始文件。"],
        },
    }
