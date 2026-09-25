# Uttera in Open WebUI

Two ways to use [Uttera](https://uttera.ai) from [Open WebUI](https://openwebui.com),
and you probably want both.

## 1. Native voice — talk to your models by voice, in Uttera's voices

Uttera is OpenAI-compatible, so Open WebUI's built-in **Audio** settings talk to
it directly. Point STT and TTS at Uttera and you get the real thing with **no
code**: the **read-aloud** button plays Uttera's voice, the microphone is
transcribed by Uttera, and Open WebUI's **Call mode** (the headphones icon in the
chat) becomes a full **spoken conversation** — you talk, the model answers out
loud in an Uttera voice.

**Admin Panel → Settings → Audio:**

- **Speech-to-Text (STT)** → Engine **OpenAI**, API Base URL
  `https://api.uttera.ai/v1`, API Key your Uttera key (`sk-echo-…`),
  STT Model `whisper-1`.
- **Text-to-Speech (TTS)** → Engine **OpenAI**, API Base URL
  `https://api.uttera.ai/v1`, API Key your Uttera key, TTS Model `tts-1`
  (or `tts-1-hd`), Voice `alloy` / `echo` / `fable` / `onyx` / `nova` / `shimmer`.

That's the whole setup — the same base-URL swap you'd do in any OpenAI SDK
(see [`../openai-sdk/`](../openai-sdk/)). It **replaces OpenAI for STT/TTS**
across the whole UI, including the mic → text and the Call/voice mode. No tool
needed for this part.

Under the hood these are plain HTTP calls you can make from anywhere:

```bash
# TTS: text -> speech
curl -s https://api.uttera.ai/v1/audio/speech \
  -H "Authorization: Bearer $UTTERA_KEY" -H "Content-Type: application/json" \
  -d '{"model":"tts-1","voice":"nova","input":"Hola, esto es Uttera."}' -o hello.mp3

# STT: speech -> text
curl -s https://api.uttera.ai/v1/audio/transcriptions \
  -H "Authorization: Bearer $UTTERA_KEY" \
  -F model=whisper-1 -F file=@hello.mp3
```

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

### ⚠ Turn on Native function calling (important for local models)

A capable model must **actually call** these tools instead of describing them.
With a local model like **`gpt-oss:120b`** (and similar), Open WebUI's default
prompt-based tool mode is unreliable — the model tends to hand-roll a CLI or a
LaTeX document instead of calling the tool. Fix it by switching to **Native**
function calling:

- Per chat: the **Controls** panel (top-right sliders) → **Advanced Params** →
  **Function Calling → Native**. Or
- Per model: create/edit a model preset and set Function Calling to **Native**.

Hosted models with strong tool use (OpenAI, Anthropic, etc.) call the tools fine
in either mode.

### Use it

Enable the tool on a chat and ask, e.g.:

- "Summarise this call and give me the signed PDF: `https://…/meeting.mp3`"
- "Who speaks when in `https://…/panel.wav`?"
- "Make a 10-second rain sound effect" · "Compose 30 seconds of calm piano"

### One limit worth knowing

The audio **comes in by URL**: the recording must be an **https URL** Uttera can
download; a file dragged into the chat does **not** reach a tool's backend (true
of any hosted assistant, not just Open WebUI). Give the model a link. Speech the
other way round (mic → text) works natively via section 1.

Some capabilities need a paid plan (sound/music: Startup and up; signed PDF
report: Developer and up). If your plan doesn't include one, the tool says so
instead of failing silently.

The Tool's calls are run against the live Uttera API before publishing. Get a key
at [app.uttera.ai](https://app.uttera.ai).
