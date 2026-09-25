# Uttera in Open WebUI

Two ways to use [Uttera](https://uttera.ai) from [Open WebUI](https://openwebui.com),
and you probably want both.

## 1. Native voice (no code) — the best path for plain speech

Uttera is OpenAI-compatible, so Open WebUI's built-in **Audio** settings talk to
it directly: the **read-aloud** button plays Uttera's voice and microphone input
is transcribed by Uttera — no tool, no prompt.

**Admin Panel → Settings → Audio:**

- **Text-to-Speech** → Engine **OpenAI**, API Base URL `https://api.uttera.ai/v1`,
  API Key your Uttera key (`sk-echo-…`), Model `tts-1` (or `tts-1-hd`), Voice
  `alloy` / `echo` / `fable` / `onyx` / `nova` / `shimmer`.
- **Speech-to-Text** → Engine **OpenAI**, API Base URL `https://api.uttera.ai/v1`,
  API Key your Uttera key, Model `whisper-1`.

That is the whole setup — the same base-URL swap as everywhere else, see
[`../openai-sdk/`](../openai-sdk/).

## 2. The Tool — everything Open WebUI has no button for

[`uttera_tool.py`](uttera_tool.py) is an Open WebUI **Tool** that lets the model
call Uttera for the whole voice stack, not just plain TTS/STT:

| Ask the model to… | Uttera endpoint |
|---|---|
| **Transcribe** a recording | `/v1/audio/transcriptions` |
| **Summarise** a call (transcript + who spoke + tone + summary) | `/v1/summarize` |
| Make a **signed PDF report** of a call (verifiable by anyone) | `/v1/summarize?report=pdf` |
| **Identify speakers** (who spoke when) | `/v1/audio/diarize` |
| **Translate** a recording | `/v1/translate` |
| **Score a pronunciation** (IPA, phoneme by phoneme) | `/v1/pronunciation` |
| **Read text aloud** | `/v1/audio/speech` |
| Generate a **sound effect** | `/v1/audio/sfx` |
| **Plan** a sound scene (no audio, cheap) | `/v1/audio/sfx/plan` |
| Generate and mix a **sound scene** | `/v1/audio/sfx/scene` |
| Generate **music** | `/v1/audio/music` |
| **Verify** a signed report | `/v1/reports/verify` |
| **List voices** | `/v1/audio/voices` |
| **Cost** of the last call | `/v1/usage/last` |

Generated audio (speech, effects, scenes, music) plays as a **player straight in
the chat**; a signed report comes as a **PDF download**.

### Install

Either:

- **Import** (no code): Workspace → Tools → the **Import** ↓ button → select
  [`uttera_tool.json`](uttera_tool.json). Or
- **Paste**: Workspace → Tools → **＋** → paste [`uttera_tool.py`](uttera_tool.py) → Save.

Then open the tool's **valves** (gear icon) and paste your Uttera API key
(`sk-echo-…`). On a shared instance each user sets their own under **User Valves**;
on a single-user instance the tool's **Valves** field is fine.

Enable the tool on a chat and ask, e.g.:

- "Summarise this call and give me the signed PDF: `https://…/meeting.mp3`"
- "Who speaks when in `https://…/panel.wav`?"
- "Make a 10-second rain sound effect" · "Compose 30 seconds of calm piano"

### Two limits worth knowing

- **Audio in comes by URL.** The recording must be an **https URL** Uttera can
  download; a file dragged into the chat does **not** reach a tool's backend
  (this is true of any hosted assistant, not just Open WebUI). Give the model a
  link. Speech the other way round (mic → text) works natively via section 1.
- Some capabilities need a paid plan (sound/music: Startup and up; signed PDF
  report: Developer and up). If your plan doesn't include one, the tool says so
  instead of failing silently.

The Tool's calls are run against the live Uttera API before publishing. Get a key
at [app.uttera.ai](https://app.uttera.ai).
