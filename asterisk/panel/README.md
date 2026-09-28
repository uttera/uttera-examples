# Uttera call panel

*[Versión en castellano](README.es.md)*

A small, read-only web view of your PBX call log. It joins the CDR with the
transcripts and intelligence the [recordings](../recordings/) connector already
leaves next to each `.wav`, and shows one row per call with its transcript,
sentiment, speakers and caller profile. For the calls the administrator needs,
one click asks `api.uttera.ai` for a narrative **summary** or a **signed PDF**.

```
server.py    stdlib only, no pip install. Reads the CDR + the monitor dir.
panel.html   the page it serves.
```

It is the panel we run in production, with the site-specific bits removed.

## What it needs

Your PBX is already recording calls, and the recordings connector is already
writing `<uniqueid>.txt` and `<uniqueid>-analysis.json` (or the older
`-description.txt`) next to each `<uniqueid>.wav`. This panel reads those plus
the CDR (`cdr-csv/Master.csv`). It **never writes** to them.

## Install

```bash
sudo mkdir -p /opt/uttera-panel
sudo cp server.py panel.html /opt/uttera-panel/
sudo cp uttera-panel.env.example /etc/uttera/panel.env
sudo chmod 600 /etc/uttera/panel.env          # it holds your API key
sudoedit /etc/uttera/panel.env                # set PANEL_PASS at least
sudo cp uttera-panel.service /etc/systemd/system/
sudo systemctl enable --now uttera-panel
```

It binds to `127.0.0.1:8973`. Put it behind your own HTTPS reverse proxy — it
serves recordings and transcripts, which are personal data.

## What costs a day to find out

**One row per call, not one per Dial leg.** Asterisk writes a CDR record per
Dial attempt and per app step, all sharing the call's `uniqueid` and a single
recording. The panel collapses them: answered if any leg answered, duration =
the longest leg, start = the earliest. Without this a ring group shows the same
call a dozen times.

**The big CDR is read from the tail.** `Master.csv` grows without bound and is
append-only, so the recent view seeks to the last couple of MB instead of
parsing the whole file. `PANEL_TAIL_BYTES` controls how far back.

**Direction is a guess.** cdr-csv does not record inbound/outbound. The panel
infers it from who is an internal extension (`PANEL_EXT_MAXLEN`). Adjust it to
your dial plan.

**The signed PDF needs a paid plan.** The transcript and the intelligence come
from files you already have, no key required. The on-demand **summary** and
**signed PDF** call `api.uttera.ai`; the PDF report (`report=pdf`) needs a
Developer plan or above. The key goes in `panel.env`, never in the dialplan.

**Auth is not optional.** With `PANEL_PASS` empty the panel is open, and it
serves call recordings. Set it, and keep the panel on localhost behind TLS.
