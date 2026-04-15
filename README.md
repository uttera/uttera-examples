# uttera-examples

<p align="center">
  <img src="docs/img/banner.png" alt="uttera.ai — The voice layer for your AI" width="800">
</p>

Integration examples, code samples, and end-to-end demos for the
[Uttera](https://uttera.ai) voice stack.

> **Uttera is OpenAI-compatible.** In most cases you don't need a custom
> SDK — the official `openai` Python/Node SDKs work directly by
> overriding `base_url`. The examples in this repo show you how.

## What's here

```
uttera-examples/
├── openai-sdk/          Use the OpenAI SDK with Uttera (Python, Node, curl)
├── home-assistant/      Local voice for Home Assistant via Wyoming protocol
├── docker-compose/      Turn-key self-hosted stack (TTS + STT + reverse proxy)
├── voice-cloning/       Pro-tier voice cloning workflows
├── streaming/           Realtime streaming TTS demos
├── dubbing-pipeline/    Whisper → translation → TTS pipeline
└── benchmarks/          Load-test scripts used in our blog posts
```

Each directory has its own `README.md` with step-by-step instructions.

## Quickstart — the 30-second tour

### Python (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.uttera.ai/v1",
    api_key="YOUR_UTTERA_API_KEY",
)

# Text-to-Speech
speech = client.audio.speech.create(
    model="tts-1", voice="alloy",
    input="Hello from Uttera.",
)
with open("out.mp3", "wb") as f:
    f.write(speech.content)

# Speech-to-Text
with open("audio.wav", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="whisper-1", file=f,
    )
print(transcript.text)
```

### Node.js (OpenAI SDK)

```javascript
import OpenAI from "openai";
import fs from "fs";

const client = new OpenAI({
  baseURL: "https://api.uttera.ai/v1",
  apiKey: process.env.UTTERA_API_KEY,
});

const speech = await client.audio.speech.create({
  model: "tts-1", voice: "alloy",
  input: "Hello from Uttera.",
});
fs.writeFileSync("out.mp3", Buffer.from(await speech.arrayBuffer()));
```

### cURL

```bash
curl https://api.uttera.ai/v1/audio/speech \
  -H "Authorization: Bearer $UTTERA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-1","voice":"alloy","input":"Hello from Uttera."}' \
  --output speech.mp3
```

## Running against a local server

The same examples work against a self-hosted Uttera server — just change
the `base_url`:

```python
client = OpenAI(base_url="http://localhost:5100/v1", api_key="sk-local")
```

See [uttera-tts-hotcold](https://github.com/uttera/uttera-tts-hotcold) and
[uttera-stt-hotcold](https://github.com/uttera/uttera-stt-hotcold) for the
self-hosted servers (Apache-2.0, run on consumer GPUs).

## Contributing

Contributions welcome — especially new integrations with popular
frameworks and runtimes. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE).

---

*Uttera /ˈʌt.ər.ə/ — from the English verb "to utter" (to speak aloud).
Also the backronym **U**niversal **T**ext **T**ransformer **E**ngine for
**R**ealtime **A**I.*
