# Transcribing the calls your PBX is already recording

*[Versión en castellano](README.es.md)*

This is the connector most people actually want, and it needs **no change to
your dialplan**. Your PBX is already writing `.wav` files somewhere. These two
scripts read them.

```
transcribe-recording.sh   one recording  → .txt + -analysis.json
bulk-reprocess.sh         a whole folder → whatever is still missing
```

It is the code we run in production, with the site-specific parts removed.

## Two ways to wire it

**As it happens.** MixMonitor can launch a command when it starts recording, so
the transcript is ready seconds after the call ends:

```
exten => s,n,MixMonitor(${MONITOR_FILE}.wav,b,transcribe-recording.sh ${UNIQUEID} &)
```

**After the fact.** A cron entry, and nothing in Asterisk changes at all:

```
*/10 * * * * RECORDINGS_DIR=/var/spool/asterisk/monitor /opt/uttera/bulk-reprocess.sh
```

The second one is how you start: point it at your recordings folder and you have
last week's calls transcribed without having touched the PBX.

## Configuration

Everything from the environment, or from `/etc/uttera/uttera.env`:

| Variable | Default | |
|---|---|---|
| `UTTERA_API_KEY` | — | **Required.** Your `sk-echo-…` key |
| `RECORDINGS_DIR` | `/var/spool/asterisk/monitor` | Where the `.wav` files are |
| `UTTERA_LANG` | `es` | Language of the calls |
| `UTTERA_ANALYSE` | `1` | `0` to transcribe only |
| `FILTER` | `-mtime -7` | Which files `bulk-reprocess.sh` considers |
| `WORKERS` | `5` | Recordings in parallel |

## What we learned running this

**Don't send near-silent audio.** Whisper does not return an empty string when
given silence — it invents a sentence, usually something like "Thanks for
watching", because that is what its training data is full of. Anything under
1 KB is skipped. You would pay for a hallucination and, worse, act on it.

**Tell a live recording from an old one.** While the call is up, MixMonitor is
still writing and the file grows; the script waits until the size stops changing.
For a file being reprocessed that wait is a wasted minute per recording, so
anything older than a minute skips it.

**One upload, not four.** `?extras=sentiment,profile,diarize` fans the analysis
out server-side over the audio that is already there. Our first version called
each analysis endpoint separately and uploaded the same recording four times.

**🔴 The date filter is the important line in the whole thing.** The first
version of the batch job had none and walked the entire archive on every pass.
The day we pointed it at a real backlog it queued years of calls at once and took
the analysis service down. *A batch job whose size depends on how long the system
has existed will eventually find a size nobody tested.* Widen the window
deliberately, once, rather than leaving it open by default.

**Lock the batch job.** Two overlapping runs upload the same recordings twice
and you pay twice.

**More workers is not faster.** Every stage of every request takes a concurrency
slot on your plan. Above that, you just earn `429`s.

## What comes out

```
1234.wav              the recording, untouched
1234.txt              the transcript
1234-analysis.json    tone, speaker profile and who spoke when — only the parts
                      that came back
```

From there it is your move: push it into a CRM, index it, summarise it. If what
you want is a summary rather than the raw text, use `/v1/summarize` instead — it
transcribes, analyses and summarises in a single request.
