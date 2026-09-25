# Uttera in Open WebUI

Two ways to use [Uttera](https://uttera.ai) from [Open WebUI](https://openwebui.com),
and you probably want both.

## 1. Native voice (no code) — the best path for speech

Uttera is OpenAI-compatible, so Open WebUI's built-in **Audio** settings talk to
it directly. This gives you the real thing: the **read-aloud** button plays
Uttera's voice, and microphone input is transcribed by Uttera — no tool, no
prompt, it just works in the UI.

**Admin Panel → Settings → Audio:**

- **Text-to-Speech**
  - Engine: **OpenAI**
  - API Base URL: `https://api.uttera.ai/v1`
  - API Key: your Uttera key (`sk-...`)
  - TTS Model: `tts-1` (standard) or `tts-1-hd` (high quality, paid plans)
  - TTS Voice: `alloy`, `echo`, `fable`, `onyx`, `nova` or `shimmer`
- **Speech-to-Text**
  - Engine: **OpenAI**
  - API Base URL: `https://api.uttera.ai/v1`
  - API Key: your Uttera key
  - STT Model: `whisper-1`

That's the whole setup. It's the same base-URL swap as everywhere else — see
[`../openai-sdk/`](../openai-sdk/).

## 2. The Tool — for what Open WebUI has no button for

`uttera_tool.py` is an Open WebUI **Tool** that lets the model call Uttera for
things beyond plain TTS/STT: **summarise a recording** (transcript + who spoke
when + tone + a structured summary in one call), **transcribe from a URL**,
**generate sound effects** and **music**, and **list the voices**.

**Install:** Workspace → Tools → **＋** → paste the contents of
[`uttera_tool.py`](uttera_tool.py) → Save. Then open the tool's **valves** and
paste your Uttera API key (each user sets their own).

**Use it** by enabling the tool on a chat and asking, e.g.:

- "Summarise this call: `https://…/meeting.mp3`"
- "Transcribe `https://…/note.wav`"
- "Make a 10-second rain sound effect"
- "Compose 30 seconds of calm piano"

### One limit worth knowing

The audio tools need the recording as an **https URL** — a file dragged into the
chat does **not** reach Uttera's servers (Open WebUI, like any hosted assistant,
doesn't hand attachments to a tool's backend). Give the model a link. Speech
input the other way round (mic → text) works natively via section 1.

## Which do I pick?

- **Just want voice in/out?** Section 1. Thirty seconds, plays in the UI.
- **Want summaries, effects or music from the model?** Add the Tool too.

The Tool's API calls are run against the live Uttera API before publishing
(`/audio/voices`, `/audio/speech`, `/audio/transcriptions`, `/summarize`,
`/audio/sfx`, `/audio/music`). Get a key at
[app.uttera.ai](https://app.uttera.ai).
