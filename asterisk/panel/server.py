#!/usr/bin/env python3
"""Uttera call panel — a read-only web view over an Asterisk PBX.

It joins the CDR (`cdr-csv/Master.csv`) with the per-call files the Uttera
recordings connector leaves in the monitor directory (`<uniqueid>.wav`,
`<uniqueid>.txt`, and `<uniqueid>-analysis.json` or the older
`<uniqueid>-description.txt`), and serves a call list with transcript and
intelligence. The administrator can, on demand, ask api.uttera.ai for a summary
or a signed PDF report of a specific call.

Design goals:
  * Standard library only — no pip install. Copy it onto the PBX and run it.
  * Read-only over the PBX data. It never writes to the monitor dir or the CDR.
  * Binds to localhost by default; put it behind the customer's HTTPS proxy.
  * HTTP Basic auth, because it exposes recordings (personal data).

Config comes from the environment (see uttera-panel.env.example). The API key is
never in the source and never in the dialplan.
"""
from __future__ import annotations

import base64
import csv
import hmac
import json
import mimetypes
import os
import ssl
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

# ── configuration ───────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))

def env(name, default=""):
    return os.environ.get(name, default)

CDR_PATH    = env("PANEL_CDR", "/var/log/asterisk/cdr-csv/Master.csv")
MONITOR_DIR = env("PANEL_MONITOR", "/var/spool/asterisk/monitor")
API_BASE    = env("UTTERA_API", "https://api.uttera.ai").rstrip("/")
API_KEY     = env("UTTERA_API_KEY", "")
LANG_CODE   = env("UTTERA_LANG", "es")
MODEL       = env("UTTERA_MODEL", "whisper-1")
ADMIN_USER  = env("PANEL_USER", "admin")
ADMIN_PASS  = env("PANEL_PASS", "")
BIND        = env("PANEL_BIND", "127.0.0.1")
PORT        = int(env("PANEL_PORT", "8973"))
# Extensions <= this many digits are treated as internal, to guess direction.
EXT_MAXLEN  = int(env("PANEL_EXT_MAXLEN", "4"))
# How much of the (append-only) CDR tail to read for the default window.
TAIL_BYTES  = int(env("PANEL_TAIL_BYTES", str(2 * 1024 * 1024)))
# A .wav smaller than this is an empty recording: an unanswered call leaves a
# 0-second file that is just the WAV header (44 bytes). The recordings connector
# uses the same idea (it drops recordings under 2 KB rather than transcribe
# silence). Below this we treat the call as having no recording.
MIN_WAV_BYTES = int(env("PANEL_MIN_WAV", "2048"))

# cdr-csv column order (Asterisk cdr_csv). userfield may be absent on old PBXs.
CDR_FIELDS = ["accountcode", "src", "dst", "dcontext", "clid", "channel",
              "dstchannel", "lastapp", "lastdata", "start", "answer", "end",
              "duration", "billsec", "disposition", "amaflags", "uniqueid",
              "userfield"]


# ── CDR reading ─────────────────────────────────────────────────────────────
def _tail(path, max_bytes):
    """Return the last max_bytes of a file as text, aligned to a line start."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    start = max(0, size - max_bytes)
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read()
    if start:  # drop a possibly partial first line
        nl = data.find(b"\n")
        data = data[nl + 1:] if nl >= 0 else data
    return data.decode("utf-8", "replace")


def _direction(row):
    """Best-effort in/out. cdr-csv doesn't record it, so we guess from who is an
    internal extension. Documented as a heuristic; the customer can flip it."""
    src, dst = row.get("src", ""), row.get("dst", "")
    src_int = src.isdigit() and len(src) <= EXT_MAXLEN
    dst_int = dst.isdigit() and len(dst) <= EXT_MAXLEN
    if src_int and not dst_int:
        return "out"
    if dst_int and not src_int:
        return "in"
    # fall back on the channel technology prefix
    return "out" if src_int else "in"


import re as _re
_RE_EXT_NUM = _re.compile(r"(?<!\d)\d{9,}(?!\d)")


def _is_external(row):
    """External call = a party with a 9+ digit number (to or from), or a
    resolved name in src/dst. Internal parties are short numeric extensions.
    The name lookup overwrites src with the name and the real number survives
    only in the channel fields, so those are scanned too."""
    for f in ("src", "dst"):
        if _re.search(r"[A-Za-z]", row.get(f, "")):
            return True
    for f in ("src", "dst", "channel", "dstchannel"):
        if _RE_EXT_NUM.search(row.get(f, "")):
            return True
    return False


def read_calls(limit=200):
    """Parse the CDR tail into call dicts, newest first, ONE row per call.

    Asterisk writes a CDR record per Dial leg / per app step, all sharing the
    call's `uniqueid` and a single `<uniqueid>.wav` recording. We collapse those
    legs into one call: answered if any leg answered, duration = the longest leg,
    start = the earliest leg. Otherwise a ring group shows the same call a dozen
    times."""
    text = _tail(CDR_PATH, TAIL_BYTES)
    if not text:
        return []
    rows = []
    for parts in csv.reader(text.splitlines()):
        if not parts or len(parts) < 17:
            continue
        rows.append({CDR_FIELDS[i]: parts[i]
                     for i in range(min(len(parts), len(CDR_FIELDS)))})
    rows.reverse()  # newest first

    porcall, orden = {}, []
    for row in rows:
        uid = row.get("uniqueid", "")
        if not uid:
            continue
        if uid not in porcall and len(orden) >= limit:
            continue  # ya tenemos suficientes llamadas distintas
        billsec = _int(row.get("billsec") or row.get("duration"))
        answered = row.get("disposition", "") == "ANSWERED"
        extern = _is_external(row)
        c = porcall.get(uid)
        if c is None:
            porcall[uid] = {
                "id": uid,
                "src": row.get("src", ""),
                "dst": row.get("dst", ""),
                "clid": row.get("clid", "").strip('"'),
                "dir": _direction(row),
                "start": row.get("start", ""),
                "dur_s": billsec,
                "disp": row.get("disposition", ""),
                "external": extern,
                "_answered": answered,
            }
            orden.append(uid)
        else:
            if billsec > c["dur_s"]:
                c["dur_s"] = billsec
            if extern:
                c["external"] = True
            if answered and not c["_answered"]:
                c["_answered"] = True
                c["disp"] = "ANSWERED"
            # los legs vienen de nuevo a viejo: el ultimo que se ve es el mas
            # antiguo -> su `start` es el inicio real de la llamada.
            if row.get("start"):
                c["start"] = row["start"]

    out = []
    for uid in orden[:limit]:
        c = porcall[uid]
        c.pop("_answered", None)
        c["has_audio"] = _has_recording(uid)
        c["has_text"] = os.path.exists(_p(uid, ".txt"))
        # Sentimiento ligero para la lista (pill + filtro). Solo si hay analisis.
        cls, txt = _light_sentiment(uid) if c["has_text"] else (None, None)
        c["senti"], c["senti_txt"] = cls, txt
        out.append(c)
    return out


_NEG = {"angry", "sad", "fearful", "disgusted"}
_POS = {"happy", "surprised"}


def _light_sentiment(uid):
    """(clase, texto) del sentimiento global, o (None, None). Lee el analisis
    del propio directorio (no llama a la API)."""
    intel = load_intel(uid)
    s = intel.get("sentiment") if isinstance(intel, dict) else None
    if not isinstance(s, dict) or not s.get("label"):
        return None, None
    lab = s["label"]
    conf = s.get("confidence")
    cls = "neg" if lab in _NEG else "pos" if lab in _POS else "neu"
    txt = lab + ((" %.2f" % conf) if isinstance(conf, (int, float)) else "")
    return cls, txt


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


# ── per-call files ──────────────────────────────────────────────────────────
def _p(uid, suffix):
    return os.path.join(MONITOR_DIR, uid + suffix)


def _has_recording(uid):
    """True only if the .wav has real content. An unanswered call leaves a
    0-second file (just the 44-byte WAV header), which is not a recording."""
    try:
        return os.path.getsize(_p(uid, ".wav")) >= MIN_WAV_BYTES
    except OSError:
        return False


def load_transcript(uid):
    for suffix in (".txt",):
        path = _p(uid, suffix)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    t = f.read().strip()
                if t and t != "[transcribing...]":
                    return t
            except OSError:
                pass
    return ""


def load_intel(uid):
    """Return the analysis dict (sentiment/profile/diarize/summary) from the
    new `-analysis.json` or the older `-description.txt` (line + '---' + JSON)."""
    js = _p(uid, "-analysis.json")
    if os.path.exists(js):
        try:
            with open(js, "r", encoding="utf-8", errors="replace") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    desc = _p(uid, "-description.txt")
    if os.path.exists(desc):
        try:
            with open(desc, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            head, _, body = raw.partition("---")
            data = {}
            body = body.strip()
            if body:
                try:
                    data = json.loads(body)
                except ValueError:
                    data = {}
            if "summary" not in data and head.strip():
                data["summary"] = head.strip()
            return data
        except OSError:
            pass
    return {}


def call_detail(uid):
    return {
        "id": uid,
        "transcript": load_transcript(uid),
        "intel": load_intel(uid),
        "has_audio": _has_recording(uid),
    }


# ── Uttera API (summary / signed PDF) ───────────────────────────────────────
def _multipart(wav_path):
    boundary = "----uttera" + base64.b16encode(os.urandom(8)).decode()
    nl = b"\r\n"
    buf = bytearray()

    def field(name, value):
        buf.extend(b"--" + boundary.encode() + nl)
        buf.extend(('Content-Disposition: form-data; name="%s"' % name).encode() + nl + nl)
        buf.extend(value.encode() + nl)

    field("model", MODEL)
    field("language", LANG_CODE)
    with open(wav_path, "rb") as f:
        audio = f.read()
    buf.extend(b"--" + boundary.encode() + nl)
    buf.extend(b'Content-Disposition: form-data; name="file"; filename="call.wav"' + nl)
    buf.extend(b"Content-Type: audio/wav" + nl + nl)
    buf.extend(audio + nl)
    buf.extend(b"--" + boundary.encode() + b"--" + nl)
    return bytes(buf), "multipart/form-data; boundary=" + boundary


def api_summarize(uid, report=False):
    """POST the call audio to /v1/summarize (optionally ?report=pdf)."""
    wav = _p(uid, ".wav")
    if not os.path.exists(wav):
        return {"error": "no_audio", "message": "No recording for this call."}
    if not API_KEY:
        return {"error": "no_api_key", "message": "UTTERA_API_KEY is not set."}
    body, ctype = _multipart(wav)
    url = API_BASE + "/v1/summarize" + ("?report=pdf" if report else "")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + API_KEY)
    req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        return {"error": "http_%d" % e.code, "message": detail}
    except Exception as e:  # noqa: BLE001
        return {"error": "request_failed", "message": str(e)}


# ── HTTP server ─────────────────────────────────────────────────────────────
def _load_page():
    try:
        with open(os.path.join(HERE, "panel.html"), "r", encoding="utf-8") as f:
            return f.read().encode("utf-8")
    except OSError:
        return b"<h1>panel.html missing</h1>"


class Handler(BaseHTTPRequestHandler):
    server_version = "UtteraPanel/0.1"

    # -- helpers --
    def _authed(self):
        if not ADMIN_PASS:
            return True  # no password configured: open (dev only)
        h = self.headers.get("Authorization", "")
        if not h.startswith("Basic "):
            return False
        try:
            user, _, pw = base64.b64decode(h[6:]).decode("utf-8").partition(":")
        except Exception:  # noqa: BLE001
            return False
        return (hmac.compare_digest(user, ADMIN_USER)
                and hmac.compare_digest(pw, ADMIN_PASS))

    def _deny(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Uttera panel"')
        self.end_headers()

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_audio(self, uid):
        path = _p(uid, ".wav")
        if not os.path.exists(path):
            self._json({"error": "not_found"}, 404)
            return
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            if a:
                start = int(a)
            if b:
                end = int(b)
            end = min(end, size - 1)
        length = end - start + 1
        code = 206 if rng else 200
        self.send_response(code)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Accept-Ranges", "bytes")
        if rng:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Content-Length", str(length))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                remaining -= len(chunk)

    def _serve_pdf(self, uid):
        res = api_summarize(uid, report=True)
        b64 = (res.get("report") or {}).get("pdf_base64") if isinstance(res, dict) else None
        if not b64:
            self._json({"error": "no_report", "detail": res}, 502)
            return
        try:
            pdf = base64.b64decode(b64)
        except Exception:  # noqa: BLE001
            self._json({"error": "bad_pdf"}, 502)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition",
                         'inline; filename="informe-%s.pdf"' % uid)
        self.send_header("Content-Length", str(len(pdf)))
        self.end_headers()
        self.wfile.write(pdf)

    # -- routing --
    def do_GET(self):
        if not self._authed():
            return self._deny()
        u = urlparse(self.path)
        path = u.path
        if path in ("/", "/index.html"):
            data = _load_page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/calls":
            qs = parse_qs(u.query)
            limit = min(500, _int((qs.get("limit") or ["200"])[0]) or 200)
            return self._json({"calls": read_calls(limit)})
        if path.startswith("/api/call/"):
            uid = unquote(path[len("/api/call/"):])
            return self._json(call_detail(uid))
        if path.startswith("/api/audio/"):
            uid = unquote(path[len("/api/audio/"):])
            return self._serve_audio(uid)
        if path.startswith("/api/report/"):
            uid = unquote(path[len("/api/report/"):])
            return self._serve_pdf(uid)
        self._json({"error": "not_found"}, 404)

    def do_POST(self):
        if not self._authed():
            return self._deny()
        u = urlparse(self.path)
        if u.path.startswith("/api/summary/"):
            uid = unquote(u.path[len("/api/summary/"):])
            return self._json(api_summarize(uid, report=False))
        self._json({"error": "not_found"}, 404)

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    mimetypes.init()
    if not ADMIN_PASS:
        sys.stderr.write("WARNING: PANEL_PASS empty — panel is UNAUTHENTICATED.\n")
    srv = ThreadingHTTPServer((BIND, PORT), Handler)
    sys.stderr.write("Uttera panel on http://%s:%d  (CDR=%s, monitor=%s)\n"
                     % (BIND, PORT, CDR_PATH, MONITOR_DIR))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
