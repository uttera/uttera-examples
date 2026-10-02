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
  * It never modifies the recordings or the CDR. The only thing it writes is the
    summary it just paid api.uttera.ai for, cached as `<uniqueid>-summary.json`
    next to the recording so the same call is never billed for a summary twice.
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
# Where the panel WRITES the summaries and PDFs it generates on demand. Reads also
# look in MONITOR_DIR, where the recordings wrapper drops <uid>-summary.json. The
# default is the monitor dir (natural: next to the recording). But a hardened unit
# runs the panel read-only over the spool (ProtectSystem=strict), so there point
# PANEL_CACHE at a writable directory — e.g. the service's StateDirectory.
CACHE_DIR   = env("PANEL_CACHE", "") or MONITOR_DIR

# Email submission (sending the signed PDF). Credentials live in the environment
# (panel.env, 600), NEVER in settings.json or the UI. With a user+pass the panel
# authenticates (STARTTLS) to the submission host, so the mail is accepted as an
# authenticated client (DMARC is skipped for authenticated senders) instead of
# relying on IP/LAN-trust relaying — a compromised LAN host without the credential
# cannot send as the domain. Without a user it falls back to a plain local handoff.
SMTP_HOST = env("PANEL_SMTP_HOST", "127.0.0.1")
try:
    SMTP_PORT = int(env("PANEL_SMTP_PORT", "25") or "25")
except ValueError:
    SMTP_PORT = 25
SMTP_USER = env("PANEL_SMTP_USER", "")
SMTP_PASS = env("PANEL_SMTP_PASS", "")

# Audit log. This is a restricted listing of call recordings (GDPR-sensitive), so
# every access to sensitive data is logged with WHO (authenticated user), from
# WHERE (client IP), WHAT (action + call uid / email recipient) and WHEN. Written
# to a dedicated append-only file (systemd LogsDirectory, writable under
# ProtectSystem=strict) and mirrored to stderr/journald.
AUDIT_LOG = env("PANEL_AUDIT_LOG", "/var/log/uttera-panel/audit.log")
API_BASE    = env("UTTERA_API", "https://api.uttera.ai").rstrip("/")
API_KEY     = env("UTTERA_API_KEY", "")
LANG_CODE   = env("UTTERA_LANG", "es")
MODEL       = env("UTTERA_MODEL", "whisper-1")
ADMIN_USER  = env("PANEL_USER", "admin")
ADMIN_PASS  = env("PANEL_PASS", "")


def _parse_users(raw):
    """PANEL_USERS='user:pass,user2:pass2' -> {user: pass}. These are read-only
    panel users: they can list calls, play audio, generate and email reports, but
    NOT open /settings (that stays with the admin, PANEL_USER)."""
    users = {}
    for item in (raw or "").split(","):
        u, sep, p = item.strip().partition(":")
        if sep and u.strip() and p.strip():
            users[u.strip()] = p.strip()
    return users


PANEL_USERS = _parse_users(env("PANEL_USERS", ""))
BIND        = env("PANEL_BIND", "127.0.0.1")
PORT        = int(env("PANEL_PORT", "8973"))
# Extensions <= this many digits are treated as internal, to guess direction.
EXT_MAXLEN  = int(env("PANEL_EXT_MAXLEN", "4"))
# Channel technologies: a call originated on a TRUNK is inbound; an internal
# endpoint dialing out through a trunk is outbound. Configurable because the trunk
# tech varies per PBX (DAHDI/ISDN here; could be a SIP trunk elsewhere).
TRUNK_TECH    = tuple(x.strip() for x in env("PANEL_TRUNK_TECH", "DAHDI").split(",") if x.strip())
INTERNAL_TECH = tuple(x.strip() for x in env("PANEL_INTERNAL_TECH", "SIP/,PJSIP/,Local/").split(",") if x.strip())
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
    """in/out from the CHANNEL technology, which is reliable; the src/dst extension
    heuristic is not — on OUTBOUND calls Asterisk presents the company's main
    number as src (not a short extension), so length alone misreads them as
    inbound. Rule: a call that ORIGINATED on a trunk is inbound; an internal
    endpoint dialing OUT through a trunk is outbound. Falls back to the extension
    heuristic for internal-to-internal calls."""
    chan = row.get("channel", "")
    dchan = row.get("dstchannel", "")
    is_trunk = lambda c: bool(TRUNK_TECH) and c.startswith(TRUNK_TECH)
    is_internal = lambda c: bool(INTERNAL_TECH) and c.startswith(INTERNAL_TECH)
    if is_trunk(chan):
        return "in"
    if is_internal(chan) and is_trunk(dchan):
        return "out"
    if is_trunk(dchan):
        return "out"
    src, dst = row.get("src", ""), row.get("dst", "")
    src_int = src.isdigit() and len(src) <= EXT_MAXLEN
    dst_int = dst.isdigit() and len(dst) <= EXT_MAXLEN
    if src_int and not dst_int:
        return "out"
    if dst_int and not src_int:
        return "in"
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


MAX_SCAN_BYTES = int(env("PANEL_MAX_SCAN", str(96 * 1024 * 1024)))


def _read_window(since):
    """Read enough of the chronological, append-only CDR tail to cover `since`.
    Grows the window from the end until the oldest line reaches `since`, capped
    at MAX_SCAN_BYTES so a very old date never loads the whole 279 MB at once."""
    if not since:
        return _tail(CDR_PATH, TAIL_BYTES)
    try:
        size = os.path.getsize(CDR_PATH)
    except OSError:
        return ""
    want = TAIL_BYTES
    while True:
        text = _tail(CDR_PATH, want)
        first_date = None
        for parts in csv.reader(text.splitlines()):
            if len(parts) >= 10 and parts[9]:
                first_date = parts[9][:10]
                break
        if (first_date is None or first_date <= since
                or want >= size or want >= MAX_SCAN_BYTES):
            return text
        want = min(want * 4, size, MAX_SCAN_BYTES)


def read_calls(limit=200, since=None, until=None):
    """Parse the CDR into call dicts, newest first, ONE row per call, optionally
    within the date range [since, until] (YYYY-MM-DD, inclusive).

    Asterisk writes a CDR record per Dial leg / per app step, all sharing the
    call's `uniqueid` and a single `<uniqueid>.wav` recording. We collapse those
    legs into one call: answered if any leg answered, duration = the longest leg,
    start = the earliest leg. Otherwise a ring group shows the same call a dozen
    times."""
    text = _read_window(since)
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
        day = row.get("start", "")[:10]
        if since and day and day < since:
            continue
        if until and day and day > until:
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
        c["has_text"] = bool(load_transcript(uid))
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


def _cp(uid, suffix):
    """Path for a panel-written cache file (CACHE_DIR)."""
    return os.path.join(CACHE_DIR, uid + suffix)


def _cache_paths(uid, suffix):
    """Both places a cached sidecar may live: the panel's CACHE_DIR and the
    monitor dir (where the recordings wrapper writes summaries). Deduplicated."""
    seen, out = set(), []
    for p in (_cp(uid, suffix), _p(uid, suffix)):
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _has_recording(uid):
    """True only if the .wav has real content. An unanswered call leaves a
    0-second file (just the 44-byte WAV header), which is not a recording."""
    try:
        return os.path.getsize(_p(uid, ".wav")) >= MIN_WAV_BYTES
    except OSError:
        return False


def _is_placeholder(t):
    """True si el .txt no es una transcripcion real, sino un marcador de "sin
    texto": el motor/conector deja mensajes como "[transcribing...]" o
    "No se ha podido extraer el texto (respuesta vacia)" cuando el STT vuelve
    vacio. Se compara por el INICIO para no confundir una frase real."""
    low = t.strip().lower()
    if low in ("", "[transcribing...]"):
        return True
    for m in ("no se ha podido extraer el texto", "no speech detected"):
        if low.startswith(m):
            return True
    return False


def load_transcript(uid):
    for suffix in (".txt",):
        path = _p(uid, suffix)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    t = f.read().strip()
                if t and not _is_placeholder(t):
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


def _summary_text(js):
    """Pull the summary string out of a stored /v1/summarize response, using the
    same fallback chain the front-end applies to the on-demand response."""
    if not isinstance(js, dict):
        return ""
    datos = js.get("datos") if isinstance(js.get("datos"), dict) else {}
    return (js.get("summary") or js.get("resumen")
            or datos.get("summary") or datos.get("resumen")
            or js.get("text") or "")


def load_summary(uid):
    """Return the auto-generated summary text from the `<uid>-summary.json`
    sidecar (written by the wrapper when auto_summary is on, or by the panel the
    first time a summary is requested on demand), or "" if absent."""
    for js in _cache_paths(uid, "-summary.json"):
        if os.path.exists(js):
            try:
                with open(js, "r", encoding="utf-8", errors="replace") as f:
                    return _summary_text(json.load(f))
            except (OSError, ValueError):
                pass
    return ""


def store_summary(uid, res):
    """Cache a successful /v1/summarize response as `<uid>-summary.json` in
    CACHE_DIR, so an on-demand summary is billed once: the next time the call is
    opened, load_summary() finds it and the panel shows it with the button
    already disabled. Same sidecar the recordings wrapper writes (in MONITOR_DIR)
    when auto_summary is on — load_summary reads both. Best-effort: never
    overwrite a good cache with an error, and a write failure (read-only mount,
    permissions) must not break the reply."""
    if not isinstance(res, dict) or res.get("error") or not _summary_text(res):
        return
    path = _cp(uid, "-summary.json")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def load_pdf(uid):
    """Return the cached signed PDF for a call, or None."""
    for path in _cache_paths(uid, "-report.pdf"):
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return f.read()
            except OSError:
                pass
    return None


def store_pdf(uid, pdf):
    """Cache a generated signed PDF as `<uid>-report.pdf` in CACHE_DIR. The report
    is billed once: pressing the button again serves this exact file instead of
    paying api.uttera.ai for a fresh one — which, since the model is not
    deterministic, would come back as a *different* report. Best-effort: a write
    failure must not break the download."""
    if not pdf:
        return
    path = _cp(uid, "-report.pdf")
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(pdf)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def call_detail(uid):
    return {
        "id": uid,
        "transcript": load_transcript(uid),
        "intel": load_intel(uid),
        "summary": load_summary(uid),
        "has_report": load_pdf(uid) is not None,
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


def api_summarize(uid, report=False, extra_headers=None):
    """POST the call audio to /v1/summarize (optionally ?report=pdf).
    extra_headers carries the report branding (X-Report-Title-B64, -Client-B64,
    -Logo) for the signed PDF."""
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
    for k, v in (extra_headers or {}).items():
        if v:
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        return {"error": "http_%d" % e.code, "message": detail}
    except Exception as e:  # noqa: BLE001
        return {"error": "request_failed", "message": str(e)}


# ── Settings (list defaults + report branding), stored server-side ───────────
def _node_info():
    """Asterisk version + hostname for the header subtitle. Computed once."""
    import socket
    import subprocess
    ver = "?"
    try:
        out = subprocess.run(["asterisk", "-V"], capture_output=True, text=True, timeout=3).stdout.strip()
        ver = out.replace("Asterisk", "").strip().split("~")[0].strip() or "?"
    except Exception:  # noqa: BLE001
        pass
    try:
        host = socket.gethostname()
    except Exception:  # noqa: BLE001
        host = "?"
    return {"asterisk_version": ver, "hostname": host}


NODE_INFO = _node_info()
SETTINGS_PATH = env("PANEL_SETTINGS", "/etc/uttera/panel-settings.json")
LOGO_MAX_BYTES = 32 * 1024              # same cap the report engine enforces
LOGO_MAX_W, LOGO_MAX_H = 1600, 400

_DEFAULT_SETTINGS = {
    "defaults": {"rec": True, "ext": True, "txt": False, "range_days": 1},
    "report": {"title": "", "company": "", "logo_b64": ""},
    # auto_summary drives the recording pipeline (speech-recog-asterisk-wrapper),
    # not the panel UI: when true the wrapper generates <uid>-summary.json on each
    # new call; when false summaries stay on demand (the "Generar resumen" button).
    # min_summary_chars: skip the auto summary when the transcript is shorter than
    # this (trivial calls like "open the door"); on-demand is never gated.
    # vocabulary: custom terms the STT wrapper adds to Whisper's initial_prompt
    # (on top of the call's contact data) so names/jargon transcribe correctly.
    "pipeline": {"auto_summary": False, "min_summary_chars": 400, "vocabulary": ""},
    # email: send the signed PDF to a FIXED list of recipients (a dropdown in the
    # UI), so a report can only go to vetted inboxes and never "leaves the office".
    # Empty by default — the recipients are configured in /settings and live in the
    # deployment's settings.json, never in this shared code (the public example
    # ships with no addresses).
    "email": {"enabled": False, "from": "", "recipients": [],
              "subject": "Informe de llamada — {caller} ({time})",
              "body": "Adjunto el informe firmado de la llamada de {caller}, del {time} "
                      "(duración {duration}).\n\n-- {company}"},
    # Custom links shown in the panel top bar (e.g. an external CDR listing or
    # another app). Empty by default — the actual links live in the deployment's
    # settings.json, never in this shared code.
    "links": [],
}


def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    d = dict(_DEFAULT_SETTINGS["defaults"])
    d.update(s.get("defaults") or {})
    r = dict(_DEFAULT_SETTINGS["report"])
    r.update(s.get("report") or {})
    p = dict(_DEFAULT_SETTINGS["pipeline"])
    p.update(s.get("pipeline") or {})
    e = dict(_DEFAULT_SETTINGS["email"])
    e.update(s.get("email") or {})
    if not isinstance(e.get("recipients"), list):
        e["recipients"] = []
    links = s.get("links")
    if not isinstance(links, list):
        links = []
    return {"defaults": d, "report": r, "pipeline": p, "email": e, "links": links}


def save_settings(s):
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SETTINGS_PATH)


def _png_dims(data):
    """(w, h) of a PNG, or None. The report engine wants a PNG logo."""
    import struct
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    return None


def _report_headers():
    """Branding headers for /v1/summarize?report=pdf, from the saved settings."""
    r = load_settings()["report"]
    h = {}
    if r.get("title"):
        h["X-Report-Title-B64"] = base64.b64encode(r["title"].encode("utf-8")).decode()
    if r.get("company"):
        h["X-Report-Client-B64"] = base64.b64encode(r["company"].encode("utf-8")).decode()
    if r.get("logo_b64"):
        h["X-Report-Logo"] = r["logo_b64"]
    return h


def _call_fields(uid):
    """Best-effort (time, duration mm:ss, caller) for a call, for email templates.
    The uniqueid is `<epoch>.<seq>`, so the start time is derivable even if the CDR
    row has scrolled out of the scan window; duration and caller come from the CDR."""
    import time as _time
    when, dur, caller = "", "", ""
    day = None
    try:
        tstruct = _time.localtime(int(float(uid.split(".")[0])))
        when = _time.strftime("%Y-%m-%d %H:%M", tstruct)
        day = _time.strftime("%Y-%m-%d", tstruct)
    except Exception:  # noqa: BLE001
        pass
    try:
        for c in read_calls(limit=10000, since=day):
            if c.get("id") == uid:
                if c.get("start"):
                    when = c["start"]
                sec = c.get("dur_s") or 0
                dur = "%d:%02d" % (sec // 60, sec % 60)
                caller = (c.get("src") or "").strip() or (c.get("clid") or "").strip()
                break
    except Exception:  # noqa: BLE001
        pass
    return when, dur, caller


def send_report_email(uid, to, s):
    """Email the cached signed PDF to one of the configured recipients.

    The message is submitted over SMTP (a socket, not the sendmail binary — the
    service runs under ProtectSystem=strict, which makes the mail spool read-only).
    With PANEL_SMTP_USER/PASS set it authenticates over STARTTLS, so the relay
    accepts it as an authenticated sender (DMARC is skipped for authenticated
    clients) — not by trusting the source IP. The recipient MUST be in the
    server-side whitelist (settings.email.recipients): a client can only pick an
    address from the fixed dropdown, never send the report anywhere else. The PDF
    must already exist (generated on demand) — this never bills a fresh report."""
    import smtplib
    import ssl
    from email.message import EmailMessage

    email_cfg = s.get("email") or {}
    recipients = email_cfg.get("recipients") or []
    if not email_cfg.get("enabled") or not recipients:
        return 400, {"error": "email_disabled"}
    if to not in recipients:
        return 403, {"error": "recipient_not_allowed"}
    pdf = load_pdf(uid)
    if pdf is None:
        return 409, {"error": "no_report",
                     "message": "Genera primero el informe firmado."}
    sender = (email_cfg.get("from") or "").strip() or recipients[0]
    label = (s.get("report") or {}).get("company") or "Uttera"
    subj = email_cfg.get("subject") or "Informe de llamada {uid}"
    body = email_cfg.get("body") or "Adjunto el informe firmado de la llamada {uid}.\n\n-- {company}"
    when, dur, caller = _call_fields(uid)
    fill = lambda tpl: (tpl.replace("{uid}", uid).replace("{company}", label)
                        .replace("{time}", when).replace("{duration}", dur)
                        .replace("{caller}", caller))
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = fill(subj)
    msg.set_content(fill(body))
    msg.add_attachment(pdf, maintype="application", subtype="pdf",
                       filename="informe-%s.pdf" % uid)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            if SMTP_USER and SMTP_PASS:
                if smtp.has_extn("starttls"):
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
    except Exception as exc:  # noqa: BLE001
        return 500, {"error": "send_failed", "message": str(exc)}
    return 200, {"ok": True, "to": to}


# ── HTTP server ─────────────────────────────────────────────────────────────
def _load_page(name="panel.html"):
    try:
        with open(os.path.join(HERE, name), "r", encoding="utf-8") as f:
            return f.read().encode("utf-8")
    except OSError:
        return ("<h1>%s missing</h1>" % name).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "UtteraPanel/0.1"

    # -- helpers --
    def _auth_user(self):
        """Return the authenticated username, or None. The admin (PANEL_USER) has
        full access; PANEL_USERS entries are read-only (no /settings)."""
        if not ADMIN_PASS and not PANEL_USERS:
            return ADMIN_USER  # no password configured: open (dev only)
        h = self.headers.get("Authorization", "")
        if not h.startswith("Basic "):
            return None
        try:
            user, _, pw = base64.b64decode(h[6:]).decode("utf-8").partition(":")
        except Exception:  # noqa: BLE001
            return None
        if (ADMIN_PASS and hmac.compare_digest(user, ADMIN_USER)
                and hmac.compare_digest(pw, ADMIN_PASS)):
            return ADMIN_USER
        exp = PANEL_USERS.get(user)
        if exp is not None and hmac.compare_digest(pw, exp):
            return user
        return None

    def _basic_user(self):
        """The username offered in the Authorization header (for logging a failed
        attempt), or '-'. Never logs the password."""
        h = self.headers.get("Authorization", "")
        if not h.startswith("Basic "):
            return "-"
        try:
            return base64.b64decode(h[6:]).decode("utf-8").partition(":")[0] or "-"
        except Exception:  # noqa: BLE001
            return "-"

    def _audit(self, action, **kv):
        """Append-only audit line: when, who, from where, what. Best-effort to the
        audit file (survives) and always to stderr/journald."""
        import time as _t
        ip = self.client_address[0] if self.client_address else "-"
        user = getattr(self, "user", None) or "-"
        parts = [_t.strftime("%Y-%m-%dT%H:%M:%S%z"), "ip=" + ip, "user=" + user,
                 "action=" + action]
        for k, v in kv.items():
            v = str(v).replace("\n", " ").replace(" ", "_")[:200]
            parts.append("%s=%s" % (k, v or "-"))
        line = " ".join(parts)
        try:
            with open(AUDIT_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        sys.stderr.write("AUDIT " + line + "\n")

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

    def _serve_pdf(self, uid, force=False):
        pdf = None if force else load_pdf(uid)
        if pdf is None:
            res = api_summarize(uid, report=True, extra_headers=_report_headers())
            b64 = (res.get("report") or {}).get("pdf_base64") if isinstance(res, dict) else None
            if not b64:
                self._json({"error": "no_report", "detail": res}, 502)
                return
            try:
                pdf = base64.b64decode(b64)
            except Exception:  # noqa: BLE001
                self._json({"error": "bad_pdf"}, 502)
                return
            store_pdf(uid, pdf)      # bill the report once: same file on the next press
            store_summary(uid, res)  # the report response also carries the summary
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition",
                         'inline; filename="informe-%s.pdf"' % uid)
        self.send_header("Content-Length", str(len(pdf)))
        self.end_headers()
        self.wfile.write(pdf)

    # -- routing --
    def do_GET(self):
        who = self._auth_user()
        if who is None:
            self._audit("auth-fail", attempted=self._basic_user())
            return self._deny()
        self.user = who
        u = urlparse(self.path)
        path = u.path
        if path == "/settings" and who != ADMIN_USER:
            self._audit("forbidden", path=path)
            return self._json({"error": "forbidden",
                               "message": "Los ajustes son solo para el administrador."}, 403)
        if path in ("/", "/index.html", "/settings"):
            data = _load_page("settings.html" if path == "/settings" else "panel.html")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/settings":
            s = load_settings()
            r = s["report"]
            return self._json({"defaults": s["defaults"],
                               "pipeline": s["pipeline"],
                               "is_admin": who == ADMIN_USER,
                               "links": s["links"],
                               "email": {"enabled": bool(s["email"].get("enabled")),
                                         "from": s["email"].get("from", ""),
                                         "recipients": s["email"].get("recipients") or [],
                                         "subject": s["email"].get("subject", ""),
                                         "body": s["email"].get("body", "")},
                               "node": NODE_INFO,
                               "report": {"title": r.get("title", ""),
                                          "company": r.get("company", ""),
                                          "has_logo": bool(r.get("logo_b64"))}})
        if path == "/api/logo":
            r = load_settings()["report"]
            if not r.get("logo_b64"):
                return self._json({"error": "no_logo"}, 404)
            try:
                png = base64.b64decode(r["logo_b64"])
            except Exception:  # noqa: BLE001
                return self._json({"error": "bad_logo"}, 500)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png)))
            self.end_headers()
            self.wfile.write(png)
            return
        if path == "/api/calls":
            qs = parse_qs(u.query)
            limit = min(500, _int((qs.get("limit") or ["200"])[0]) or 200)

            def _fecha(k):
                v = (qs.get(k) or [""])[0][:10]
                return v if _re.match(r"^\d{4}-\d{2}-\d{2}$", v) else None
            return self._json({"calls": read_calls(limit, _fecha("since"),
                                                   _fecha("until"))})
        if path.startswith("/api/call/"):
            uid = unquote(path[len("/api/call/"):])
            self._audit("view-call", uid=uid)
            return self._json(call_detail(uid))
        if path.startswith("/api/audio/"):
            uid = unquote(path[len("/api/audio/"):])
            self._audit("play-recording", uid=uid)
            return self._serve_audio(uid)
        if path.startswith("/api/report/"):
            uid = unquote(path[len("/api/report/"):])
            force = (parse_qs(u.query).get("force") or ["0"])[0] == "1"
            self._audit("report", uid=uid, force=int(force))
            return self._serve_pdf(uid, force=force)
        self._json({"error": "not_found"}, 404)

    def _read_body(self, cap):
        n = _int(self.headers.get("Content-Length"))
        if n <= 0 or n > cap:
            return None
        return self.rfile.read(n)

    def _save_settings(self):
        raw = self._read_body(64 * 1024)
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, AttributeError):
            return self._json({"error": "bad_json"}, 400)
        s = load_settings()
        # Merge only the sections present in the body: a partial POST (e.g. the
        # "remove logo" button, which sends only clear_logo) must not reset the
        # other stored settings.
        if "defaults" in body:
            d = body.get("defaults") or {}
            s["defaults"]["rec"] = bool(d.get("rec"))
            s["defaults"]["ext"] = bool(d.get("ext"))
            s["defaults"]["txt"] = bool(d.get("txt"))
            try:
                s["defaults"]["range_days"] = max(1, min(365, int(d.get("range_days", 1))))
            except (TypeError, ValueError):
                pass
        if "report" in body:
            r = body.get("report") or {}
            s["report"]["title"] = str(r.get("title", ""))[:200]
            s["report"]["company"] = str(r.get("company", ""))[:200]
        if body.get("clear_logo"):
            s["report"]["logo_b64"] = ""
        if "pipeline" in body:
            pl = body.get("pipeline") or {}
            s["pipeline"]["auto_summary"] = bool(pl.get("auto_summary"))
            try:
                s["pipeline"]["min_summary_chars"] = max(0, min(5000, int(pl.get("min_summary_chars", 400))))
            except (TypeError, ValueError):
                pass
            if "vocabulary" in pl:
                s["pipeline"]["vocabulary"] = str(pl.get("vocabulary", ""))[:2000]
        if "email" in body:
            em = body.get("email") or {}
            s["email"]["enabled"] = bool(em.get("enabled"))
            s["email"]["from"] = str(em.get("from", "")).strip()[:200]
            clean = []
            for a in (em.get("recipients") or []):
                a = str(a).strip()[:200]
                # minimal sanity: a single address, no spaces; dedup; cap at 20
                if a and "@" in a and " " not in a and a not in clean and len(clean) < 20:
                    clean.append(a)
            s["email"]["recipients"] = clean
            if "subject" in em:
                s["email"]["subject"] = str(em.get("subject", ""))[:300]
            if "body" in em:
                s["email"]["body"] = str(em.get("body", ""))[:4000]
        if "links" in body:
            out = []
            for it in (body.get("links") or []):
                if not isinstance(it, dict):
                    continue
                label = str(it.get("label", "")).strip()[:80]
                url = str(it.get("url", "")).strip()[:300]
                if (label and (url.startswith("http://") or url.startswith("https://"))
                        and len(out) < 20):
                    out.append({"label": label, "url": url})
            s["links"] = out
        try:
            save_settings(s)
        except OSError as e:
            return self._json({"error": "save_failed", "message": str(e)}, 500)
        return self._json({"ok": True})

    def _save_logo(self):
        data = self._read_body(LOGO_MAX_BYTES + 4096)
        if not data:
            return self._json({"error": "empty"}, 400)
        if len(data) > LOGO_MAX_BYTES:
            return self._json({"error": "too_big",
                               "message": "El logo debe pesar 32 KB o menos."}, 413)
        dims = _png_dims(data)
        if dims is None:
            return self._json({"error": "not_png",
                               "message": "El logo debe ser un PNG."}, 415)
        if dims[0] > LOGO_MAX_W or dims[1] > LOGO_MAX_H:
            return self._json({"error": "dims",
                               "message": "Maximo %dx%d px." % (LOGO_MAX_W, LOGO_MAX_H)}, 413)
        s = load_settings()
        s["report"]["logo_b64"] = base64.b64encode(data).decode()
        try:
            save_settings(s)
        except OSError as e:
            return self._json({"error": "save_failed", "message": str(e)}, 500)
        return self._json({"ok": True, "w": dims[0], "h": dims[1]})

    def do_POST(self):
        who = self._auth_user()
        if who is None:
            self._audit("auth-fail", attempted=self._basic_user())
            return self._deny()
        self.user = who
        u = urlparse(self.path)
        if u.path.startswith("/api/summary/"):
            uid = unquote(u.path[len("/api/summary/"):])
            self._audit("summary", uid=uid)
            res = api_summarize(uid, report=False)
            store_summary(uid, res)  # cache so the same call is never billed twice
            return self._json(res)
        if u.path.startswith("/api/email/"):
            uid = unquote(u.path[len("/api/email/"):])
            if not _re.match(r"^[0-9.]+$", uid):
                return self._json({"error": "bad_uid"}, 400)
            raw = self._read_body(4096)
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, AttributeError):
                return self._json({"error": "bad_json"}, 400)
            to = str(body.get("to", "")).strip()
            code, res = send_report_email(uid, to, load_settings())
            self._audit("email-report", uid=uid, to=to, status=code)
            return self._json(res, code)
        if u.path == "/api/settings":
            if who != ADMIN_USER:
                self._audit("forbidden", path=u.path)
                return self._json({"error": "forbidden"}, 403)
            self._audit("settings-change")
            return self._save_settings()
        if u.path == "/api/logo":
            if who != ADMIN_USER:
                self._audit("forbidden", path=u.path)
                return self._json({"error": "forbidden"}, 403)
            self._audit("logo-change")
            return self._save_logo()
        self._json({"error": "not_found"}, 404)

    def log_message(self, fmt, *args):  # per-request line: ip user "request" status
        sys.stderr.write("%s %s %s\n" % (self.address_string(),
                                         getattr(self, "user", "-") or "-",
                                         fmt % args))


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
