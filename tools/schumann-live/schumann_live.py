#!/usr/bin/env python3
"""Fail-closed, self-hosted Schumann spectrogram banner (no GitHub Actions).

BGS's *published* file time is NOT the observation time. The original chart
contains the observation date; this service does not OCR or manufacture it.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

SOURCE_URL = "https://geomag.bgs.ac.uk/images/currentSpectrogramCH1.jpg"
SOURCE_PAGE = "https://geomag.bgs.ac.uk/research/inductioncoils.html"
OUT = Path(os.environ.get("SCHUMANN_OUTPUT_DIR", "/data"))
HOST = os.environ.get("SCHUMANN_HOST", "127.0.0.1")
PORT = int(os.environ.get("SCHUMANN_PORT", "8765"))
REFRESH_SECONDS = max(3600, int(os.environ.get("SCHUMANN_REFRESH_SECONDS", "21600")))
MAX_BYTES = 5_000_000
MIN_WIDTH, MIN_HEIGHT = 350, 250
MAX_PIXELS = 8_000_000
FRESH_HOURS = 48
RETAIN_HOURS = 72

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirect refused: source URL must remain fixed")

def utc_now():
    return datetime.now(timezone.utc)

def parse_http_date(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None

def validate_source_image(content):
    if not (content.startswith(b"\xff\xd8") and len(content) <= MAX_BYTES):
        raise ValueError("Only bounded source JPEGs accepted")
    try:
        with Image.open(io.BytesIO(content)) as im:
            im.verify()
        with Image.open(io.BytesIO(content)) as im:
            if im.format != "JPEG":
                raise ValueError("Incorrect image format")
            w, h = im.size
            if w < MIN_WIDTH or h < MIN_HEIGHT or w * h > MAX_PIXELS:
                raise ValueError("Unexpected source dimensions")
            return im.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid source image") from exc

def fetch_bgs():
    req = Request(SOURCE_URL, headers={
        "User-Agent": "XGCS-Schumann-Profile/1.0 (research profile; 6h poll)",
        "Accept": "image/jpeg",
    })
    with build_opener(NoRedirect()).open(req, timeout=16) as response:
        if response.status != 200:
            raise ValueError("Unexpected upstream HTTP status")
        mime = response.headers.get_content_type()
        if mime not in ("image/jpeg", "image/jpg"):
            raise ValueError("Unexpected upstream content-type: " + mime)
        published = parse_http_date(response.headers.get("Last-Modified"))
        content = response.read(MAX_BYTES + 1)
    image = validate_source_image(content)
    return image, hashlib.sha256(content).hexdigest(), published

def font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()

def draw_banner(chart, state, published=None):
    # Matches the public systems-register design dimensions and palette.
    im = Image.new("RGB", (1000, 215), "#080c10")
    d = ImageDraw.Draw(im)
    d.polygon([(18,28),(28,18),(972,18),(982,28),(982,187),(972,197),(28,197),(18,187)], fill="#0d1319", outline="#34414d")
    for x,side in ((18,1),(982,-1)):
        for y,sy in ((18,1),(197,-1)):
            d.line((x,y,x+16*side,y),fill="#b8a06a",width=2)
            d.line((x,y,x,y+16*sy),fill="#b8a06a",width=2)
    d.text((42,33),"PUBLIC OPERATING PROFILE / XGCS",font=font(12),fill="#99a5af")
    d.text((42,68),"XANDER GRAY",font=font(43,True),fill="#e8edf2")
    d.text((44,135),"FOUNDER & CEO / SYSTEMS ARCHITECT",font=font(13),fill="#99a5af")
    d.text((44,155),"QUANTITATIVE MARKET RESEARCH",font=font(13),fill="#99a5af")
    d.rectangle((744,22,973,198),fill="#0b1016",outline="#34414d",width=1)
    d.text((753,27),"SCHUMANN / ESKDALEMUIR",font=font(10,True),fill="#b8a06a")
    if chart is not None:
        # Preserve the upstream plot/date axes; never draw invented data.
        thumb = chart.copy()
        thumb.thumbnail((213,133),Image.Resampling.LANCZOS)
        im.paste(thumb,(751+(215-thumb.width)//2,43+(133-thumb.height)//2))
    else:
        d.text((762,95),"NO VERIFIED DATA",font=font(13,True),fill="#e8edf2")
    indicator = {"CURRENT":"#75a98d","DELAYED":"#b8a06a","UNAVAILABLE":"#b88a8a"}[state]
    d.rectangle((754,177,761,186),fill=indicator)
    d.text((768,175),state+" / DAILY",font=font(10,True),fill=indicator)
    publication = "FILE MOD "+published.strftime("%Y-%m-%d UTC") if published else "FILE TIME UNKNOWN"
    d.text((753,189),publication,font=font(8),fill="#99a5af")
    return im

def age_hours(published, now):
    return (now - published).total_seconds() / 3600 if published else None

def classify(published, now, previous=None, digest=None):
    age = age_hours(published, now)
    if age is None or age < -2 or age > FRESH_HOURS:
        return "DELAYED"
    if previous and previous.get("sha256") == digest:
        prior = previous.get("checked_utc")
        try:
            seen = datetime.fromisoformat(prior)
            if (now - seen).total_seconds() > FRESH_HOURS * 3600:
                return "DELAYED"
        except (ValueError, TypeError):
            pass
    return "CURRENT"

def atomically_save(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + ".tmp")
    with open(temp,"wb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp,path)

def load_previous():
    try:
        return json.loads((OUT/"status.json").read_text())
    except (OSError, ValueError):
        return None

def refresh():
    now = utc_now()
    prev = load_previous()
    approved = os.environ.get("SCHUMANN_REUSE_APPROVED") == "yes"
    chart = None
    state = "UNAVAILABLE"
    digest, published, error = None, None, None
    if not approved:
        error = "Source chart reuse has not been authorized"
    else:
        try:
            chart,digest,published = fetch_bgs()
            state = classify(published,now,prev,digest)
        except (ValueError,HTTPError,URLError,OSError) as exc:
            error = type(exc).__name__ + ": " + str(exc)[:180]
    # An upstream failure never silently presents old data as current.
    # No carry-forward image is used in this initial conservative version.
    banner = draw_banner(chart,state,published)
    buf = io.BytesIO()
    banner.save(buf,format="PNG",optimize=True)
    meta = {
        "state":state,
        "station":"Eskdalemuir, UK / BGS / North induction coil",
        "source_page":SOURCE_PAGE,
        "source_image":SOURCE_URL,
        "observed_utc":None,  # Date is visible in image; no machine-readable timestamp.
        "source_file_last_modified_utc":published.isoformat() if published else None,
        "checked_utc":now.isoformat(),
        "sha256":digest,
        "error":error,
        "reuse_attested":approved,
        "meaning":"CURRENT means file publication age <=48h, NOT a verified exact observation timestamp.",
    }
    atomically_save(OUT/"profile-banner.png",buf.getvalue())
    atomically_save(OUT/"status.json",json.dumps(meta,indent=2).encode())
    return meta

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/profile-banner.png","/status.json","/healthz"):
            self.send_error(404)
            return
        if self.path == "/healthz":
            data = b"ok\n"
            mime = "text/plain"
        else:
            path = OUT / self.path.removeprefix("/")
            try:
                data = path.read_bytes()
            except OSError:
                self.send_error(503)
                return
            mime = "image/png" if path.suffix == ".png" else "application/json"
        self.send_response(200)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store, max-age=0")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(data)

def serve():
    refresh()
    def work():
        while True:
            time.sleep(REFRESH_SECONDS)
            try:
                refresh()
            except Exception as exc:
                # The server can still expose the last status; incident logged.
                print("refresh failure:",repr(exc),flush=True)
    threading.Thread(target=work,daemon=True).start()
    print("Listening on",HOST,PORT,flush=True)
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()

if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        print(json.dumps(refresh(),indent=2))
    else:
        serve()
