#!/usr/bin/env python3
"""Uttera through the official OpenAI SDK. Only base_url and api_key change.

    pip install openai
    export UTTERA_API_KEY=sk-echo-...
    python3 python.py
"""
import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["UTTERA_API_KEY"],
    base_url=os.environ.get("UTTERA_API", "https://api.uttera.ai") + "/v1",
    # Uttera holds the connection for up to 7200 s so long recordings finish.
    # The SDK default is far shorter and cuts off jobs that were going fine.
    timeout=7200.0,
)

# ── text to speech ──
speech = client.audio.speech.create(
    model="tts-1", voice="nova", input="Your order ships tomorrow."
)
with open("out.mp3", "wb") as f:
    f.write(speech.content)
print("wrote out.mp3 (%d bytes)" % len(speech.content))

# ── speech to text, on the file we just produced ──
with open("out.mp3", "rb") as f:
    text = client.audio.transcriptions.create(
        model="whisper-1", file=f, response_format="text"
    )
print("transcript:", text.strip() if isinstance(text, str) else text)
