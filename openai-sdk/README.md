# Uttera with the OpenAI SDK

Uttera speaks the same dialect as OpenAI for transcription and speech: same
routes, same parameter names, same voice names. **Anything written for the
OpenAI API works by changing two lines** — the base URL and the key.

These examples are run against the live API before being published here. The
Python one below was executed with the official `openai` package (3.13.0),
unpatched: it generates the audio, transcribes it back, and gets the original
text.

| File | Runtime |
|---|---|
| `python.py` | Python, `pip install openai` |
| `node.mjs` | Node 20+, `npm install openai` |
| `curl.sh` | Nothing but `curl` |

```bash
export UTTERA_API_KEY=sk-echo-...
python3 python.py
```

## What is and is not compatible

| Works unchanged | Ours only |
|---|---|
| `POST /v1/audio/transcriptions` | `POST /v1/summarize` |
| `POST /v1/audio/speech` | `POST /v1/translate` |
| Voices `alloy` `echo` `fable` `nova` `onyx` `shimmer` | `?extras=` voice analysis |
| | `GET /v1/usage/last` |

The extra endpoints don't get in the way of anything: a client that ignores them
behaves exactly as it would against OpenAI.

## One thing to change beyond the URL

**The timeout.** Uttera holds the connection open for up to 7200 s so long
recordings finish; SDK defaults are far shorter and will cut off a job that was
going perfectly. Pass `timeout=7200` when you build the client if you handle
recordings longer than a few minutes.
