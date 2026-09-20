# Uttera for n8n

Audio for your workflows: transcribe recordings, turn text into speech,
translate, summarise, and generate sound effects and music — from one node.

![Uttera](nodo/nodes/Uttera/uttera.svg)

## What the node does

| Operation | What you get |
|---|---|
| **Transcribe Audio** | The text of a recording, with optional tone, speaker profile and diarisation **in the same call** — the audio is uploaded once |
| **Summarise Recording** | Summary, full transcript, tone and who spoke when |
| **Translate Recording** | A recording turned into another language |
| **Text to Speech** | mp3, wav, opus or flac from a text |
| **Sound Effect** | A clip from a description: a door, rain, footsteps |
| **Music** | A finished piece, up to 6 min 20 s |

## Install

Community nodes panel in n8n, or:

```bash
npm install n8n-nodes-uttera
```

Then add your API key as an **Uttera API** credential. Get one free at
[app.uttera.ai](https://app.uttera.ai) — no card needed.

## Two things worth knowing

**Analysis comes free of a second upload.** Asking for tone, speaker profile or
diarisation alongside a transcription puts them in the *same* request. Asking
separately uploads the audio again and transcribes it twice.

**Sound effects and music need a paid plan**, from Startup up, and everything
generated carries an inaudible watermark required by Article 50(2) of the EU AI
Act. For music the price is **length multiplied by steps**, so 128 steps costs
four times 32 — the node says so on the field itself.

## Where the audio goes

Processed on our own hardware in Spain. It is discarded once answered, and it
never trains any model. Details at [uttera.ai](https://uttera.ai).

## Licence

Apache-2.0
