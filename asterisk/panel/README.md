# Uttera call panel

*[Versión en castellano](README.es.md)*

A small, read-only web view of your PBX call log. It joins the CDR with the
transcripts and intelligence the [recordings](../recordings/) connector already
leaves next to each `.wav`, and shows one row per call with its transcript,
sentiment, speakers and caller profile. For the calls the administrator needs,
one click asks `api.uttera.ai` for a narrative **summary** or a **signed PDF**.

```
server.py     stdlib only, no pip install. Reads the CDR + the monitor dir.
panel.html    the call list and detail view it serves.
settings.html the /settings page: headers, logo and pipeline options.
```

It is the panel we run in production, with the site-specific bits removed. The
UI ships in four languages (Spanish, English, French, German); it picks one from
the browser and remembers the choice.

## What it looks like

The call list with a call open — transcript, sentiment, speaker split and the
caller profile, plus the on-demand summary and the signed-PDF button:

![Uttera call panel, Spanish, light theme](docs/img/panel-es.png)

Every string is translated and it has a dark theme; the same panel in English,
on a call the model flagged negative:

![Uttera call panel, English, dark theme](docs/img/panel-en-dark.png)

The Settings page — default view, call-summary automation, custom vocabulary,
and the headers that brand the panel and the signed PDF report:

![Settings page](docs/img/settings-en.png)

*(Screenshots are a demo PBX with synthetic calls — no real call data.)*

## What it needs

Your PBX is already recording calls, and the recordings connector is already
writing `<uniqueid>.txt` and `<uniqueid>-analysis.json` (or the older
`-description.txt`) next to each `<uniqueid>.wav`. This panel reads those plus
the CDR (`cdr-csv/Master.csv`). It **never writes** to them.

## Install

```bash
sudo mkdir -p /opt/uttera-panel
sudo cp server.py panel.html settings.html /opt/uttera-panel/
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
infers it from the channel technology first — a call originated on a trunk is
inbound, an internal channel dialling a trunk is outbound — and falls back to
extension length when the channels are ambiguous. On a trunk that presents your
own main number as the caller ID for outbound calls, the length rule alone
mislabels them as inbound, which is why the technology check comes first. Tune
`PANEL_TRUNK_TECH`, `PANEL_INTERNAL_TECH` and `PANEL_EXT_MAXLEN` to your dial
plan.

**Settings live in a JSON file, not the code.** The `/settings` page writes the
panel/report headers, the uploaded logo and the recording-pipeline options
(auto-summary on/off, a minimum-transcript length, and a custom vocabulary fed
to speech recognition) to `PANEL_SETTINGS`. The recordings connector reads the
same file, so summaries and vocabulary can be changed without touching either.

**The signed PDF needs a paid plan.** The transcript and the intelligence come
from files you already have, no key required. The on-demand **summary** and
**signed PDF** call `api.uttera.ai`; the PDF report (`report=pdf`) needs a
Developer plan or above. The key goes in `panel.env`, never in the dialplan.

**A summary and a report are each billed once.** When you press *Generate
summary*, the panel caches the response as `<uniqueid>-summary.json` next to the
recording; reopen the call and it shows the stored summary with the button
disabled. The signed PDF is cached the same way, as `<uniqueid>-report.pdf`: a
second press serves that exact file instead of paying for a fresh one — which,
because the model is not deterministic, would come back as a *different* report.
The button then reads *View signed report*. To force a new one after changing
the branding, request `/api/report/<id>?force=1`. The auto-summary pipeline
writes the same summary sidecar, so the two summary paths share one cache.

**Auth is not optional.** With `PANEL_PASS` empty the panel is open, and it
serves call recordings. Set it, and keep the panel on localhost behind TLS.
