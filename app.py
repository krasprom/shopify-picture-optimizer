import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from rembg import new_session

from optimize import optimize_bytes

CACHE_DIR = Path(os.environ.get("OPTIMIZER_CACHE_DIR", "/var/cache/shopify-optimizer"))
MODEL_NAME = os.environ.get("OPTIMIZER_MODEL", "isnet-general-use")
# Хосты с самоподписанным сертификатом — проверку TLS отключаем ТОЛЬКО для них.
INSECURE_HOSTS = {"admin2.hardware-best.de", "admin2.sofortverkaufen.de"}
DOWNLOAD_TIMEOUT = 20
# Некоторые источники (например Wikimedia) отдают 403 на дефолтный UA requests.
DOWNLOAD_HEADERS = {"User-Agent": "shopify-picture-optimizer/1.0 (+https://github.com/krasprom/shopify-picture-optimizer)"}

_CONTENT_TYPE = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                 "png": "image/png", "webp": "image/webp"}

app = FastAPI()
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_session = None


def get_session():
    """Ленивая загрузка rembg-модели — чтобы импорт модуля в тестах не тянул ~170 МБ."""
    global _session
    if _session is None:
        _session = new_session(MODEL_NAME)
    return _session


class OptimizeRequest(BaseModel):
    url: str
    size: int = 1500
    padding: float = 0.08
    format: str = "jpg"


def _cache_key(req: "OptimizeRequest") -> str:
    raw = f"{req.url}|{req.size}|{req.padding}|{req.format}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fetch_image(url: str) -> bytes:
    host = urlparse(url).hostname or ""
    verify = host not in INSECURE_HOSTS
    resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT, verify=verify, headers=DOWNLOAD_HEADERS)
    resp.raise_for_status()
    return resp.content


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/optimize")
def optimize(req: OptimizeRequest):
    fmt = req.format.lower()
    content_type = _CONTENT_TYPE.get(fmt, "image/jpeg")
    cache_file = CACHE_DIR / f"{_cache_key(req)}.{fmt}"

    if cache_file.exists():
        return Response(content=cache_file.read_bytes(), media_type=content_type,
                        headers={"X-Cache": "hit", "X-Object-Detected": "unknown"})

    try:
        src = fetch_image(req.url)
    except Exception as e:
        return JSONResponse(status_code=502, content={"error": f"download failed: {e}"})

    try:
        out, detected = optimize_bytes(src, req.size, req.padding, fmt, get_session())
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"optimize failed: {e}"})

    cache_file.write_bytes(out)
    return Response(content=out, media_type=content_type,
                    headers={"X-Cache": "miss", "X-Object-Detected": str(detected).lower()})
