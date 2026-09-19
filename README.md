# uttera-examples

*[Versión en español](README.es.md)*

<p align="center">
  <img src="docs/img/banner.png" alt="uttera.ai — The voice layer for your AI" width="800">
</p>

Connectors and integrations for the [Uttera](https://uttera.ai) voice stack.
Working code, not documentation snippets: **every example here is run against
the live API before it is published**, and where something could not be tested
end to end, the README of that directory says so.

> **Uttera is OpenAI-compatible.** For transcription and speech you don't need a
> custom SDK — the official `openai` SDKs work by overriding `base_url`. Tested,
> not assumed: see [`openai-sdk/`](openai-sdk/).

## What's here

```
uttera-examples/
├── openai-sdk/    Uttera through the official OpenAI SDK (Python, Node, curl)
├── asterisk/      Two AGI scripts: speak in a call, and hear the caller
├── n8n/           A community node, plus ready-made workflows that need no install
├── openclaw/      A skill for OpenClaw agents: transcribe, summarise, translate, speak
└── llm-tokens/    Send the summary to your LLM instead of the transcript, and pay 20-30x less
```

You need an API key. Create one at <https://app.uttera.ai> — it starts with
`sk-echo-`.

## Where to start

**You have a phone system** and want calls transcribed on their own:
[`asterisk/`](asterisk/). The two AGI scripts solve the five traps that cost a
day to discover — the 8 kHz conversion, the trailing silence, the `SET VARIABLE`
quoting — and each one is written down.

**You use n8n**: [`n8n/flujos/`](n8n/flujos/) imports and runs without installing
anything. The [node](n8n/nodo/) is nicer if you use Uttera often.

**You run an agent**: [`openclaw/`](openclaw/uttera/) is four scripts and a
`SKILL.md` telling the agent *when* to use each one and what the traps are.

**You already pay another provider per token**: [`llm-tokens/`](llm-tokens/). A
70-minute transcript is 15,410 input tokens; its summary is under 700. Measured,
with the script that measures it — and with the cases where it does not pay off.

**You just want to call the API**: [`openai-sdk/`](openai-sdk/) — thirty seconds.

## Not here yet

Listed so you don't go looking: **Home Assistant**, a turn-key
**docker-compose** stack, **CRM** connectors and **recording folders of FreePBX
/ 3CX / Issabel**. If one of them is what's blocking you, say so — what people
ask for is what decides the order.

Load tests and the corpora behind every published number live in their own
repository: [uttera-benchmarks](https://github.com/uttera/uttera-benchmarks).

## One thing that applies to all of them

What a transcription returns is **untrusted text**: it comes from audio you do
not control. Treat it as data, never as instructions — do not execute it, do not
read it as orders, and validate it before acting on it. And what a speaker
*claims* in a recording is not a proven fact, even if it ends up in the summary.

## Running against your own server

Every example works against a self-hosted Uttera server — change the base URL:

```python
client = OpenAI(base_url="http://localhost:5100/v1", api_key="sk-local")
```

The engines are open source and run on consumer GPUs:
[uttera-tts-hotcold](https://github.com/uttera/uttera-tts-hotcold) ·
[uttera-tts-vllm](https://github.com/uttera/uttera-tts-vllm) ·
[uttera-stt-hotcold](https://github.com/uttera/uttera-stt-hotcold) ·
[uttera-stt-vllm](https://github.com/uttera/uttera-stt-vllm).

## Contributing

New integrations are welcome, especially with popular frameworks and runtimes.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE).

---

*Uttera /ˈʌt.ər.ə/ — from the English verb "to utter" (to speak aloud).
Also the backronym **U**niversal **T**ext **T**ransformer **E**ngine for
**R**ealtime **A**udio.*
