"""
title: Uttera Voice AI
author: Uttera Labs
author_url: https://uttera.ai
funding_url: https://uttera.ai
version: 0.1.0
license: MIT
description: EU-hosted, OpenAI-compatible voice AI. Transcribe recordings, summarise a call/meeting with speaker diarization and tone, read text aloud in ~30 languages, and generate sound effects and music. Audio is processed in Spain, discarded after answering and never used for training.
requirements: requests
"""

import base64
import requests
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        base_url: str = Field(
            default="https://api.uttera.ai/v1",
            description="Uttera API base URL (OpenAI-compatible).",
        )
        timeout: int = Field(
            default=300,
            description="Per-request timeout in seconds (audio can be long).",
        )

    class UserValves(BaseModel):
        api_key: str = Field(
            default="",
            description="Your personal Uttera API key (sk-...). Get one at https://app.uttera.ai",
        )

    def __init__(self):
        self.valves = self.Valves()

    # ── helpers ──────────────────────────────────────────────────────────
    def _key(self, __user__) -> str:
        key = ""
        if __user__ and isinstance(__user__, dict):
            uv = __user__.get("valves")
            key = getattr(uv, "api_key", "") if uv else ""
        if not key:
            raise Exception(
                "No Uttera API key set. Open this tool's settings and paste your "
                "key (sk-...). You can create one at https://app.uttera.ai"
            )
        return key

    def _headers(self, __user__) -> dict:
        return {"Authorization": f"Bearer {self._key(__user__)}"}

    def _fetch(self, url: str) -> bytes:
        if not url.lower().startswith(("http://", "https://")):
            raise Exception(
                "The audio must be an https URL that Uttera can download. A file "
                "attached to the chat does not work: Uttera's servers never receive "
                "those bytes. Ask the user for a direct download link."
            )
        r = requests.get(url, timeout=self.valves.timeout)
        r.raise_for_status()
        name = url.rsplit("/", 1)[-1].split("?")[0] or "audio"
        return r.content, name

    async def _emit_audio(self, __event_emitter__, mp3: bytes, caption: str):
        """Show an audio player straight in the chat (bypasses the model)."""
        if __event_emitter__ is None:
            return
        b64 = base64.b64encode(mp3).decode()
        html = (
            f"<p>{caption}</p>"
            f'<audio controls src="data:audio/mpeg;base64,{b64}"></audio>'
        )
        await __event_emitter__({"type": "message", "data": {"content": html}})

    # ── audio → text ─────────────────────────────────────────────────────
    def transcribe_audio(
        self, audio_url: str, language: str = "", __user__: dict = {}
    ) -> str:
        """
        Transcribe an audio recording to plain text. The audio MUST be an https URL
        that Uttera can download; a file attached to the chat will NOT work, so ask
        the user for a direct link if they only have a local file.
        :param audio_url: https URL to the audio (wav/mp3/m4a/ogg/flac/opus/webm).
        :param language: optional ISO code (e.g. "es") to force the language; empty = auto-detect.
        """
        content, name = self._fetch(audio_url)
        data = {"model": "whisper-1"}
        if language:
            data["language"] = language
        r = requests.post(
            f"{self.valves.base_url}/audio/transcriptions",
            headers=self._headers(__user__),
            files={"file": (name, content)},
            data=data,
            timeout=self.valves.timeout,
        )
        r.raise_for_status()
        try:
            return r.json().get("text", "")
        except Exception:
            return r.text

    def summarise_recording(self, audio_url: str, __user__: dict = {}) -> str:
        """
        Transcribe AND analyse a recording in a single call: full transcript, who
        spoke when (diarization), the tone, and a structured summary (what it is,
        key points, concrete data, and what to do). Best for calls, meetings,
        lectures or interviews longer than a couple of minutes. The audio_url MUST
        be an https URL Uttera can download (a chat attachment will not work).
        Requires a Professional plan or above.
        """
        content, name = self._fetch(audio_url)
        r = requests.post(
            f"{self.valves.base_url}/summarize",
            headers=self._headers(__user__),
            files={"file": (name, content)},
            timeout=self.valves.timeout,
        )
        r.raise_for_status()
        try:
            j = r.json()
        except Exception:
            return r.text
        out = j.get("summary", "")
        u = j.get("usage", {})
        if u:
            out += f"\n\n_(Uttera credits: {u.get('credits', '?')})_"
        return out

    def list_voices(self, __user__: dict = {}) -> str:
        """List the available text-to-speech voices and the language each one speaks."""
        r = requests.get(
            f"{self.valves.base_url}/audio/voices",
            headers=self._headers(__user__),
            timeout=self.valves.timeout,
        )
        r.raise_for_status()
        return r.text

    # ── text/prompt → audio (emitted as a player in the chat) ────────────
    async def text_to_speech(
        self,
        text: str,
        voice: str = "alloy",
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        Read text aloud in a natural voice. The language is inferred from the text
        (~30 languages). Best for a sentence or a short paragraph. An audio player
        is shown directly in the chat.
        :param voice: alloy, echo, fable, onyx, nova or shimmer.
        """
        r = requests.post(
            f"{self.valves.base_url}/audio/speech",
            headers=self._headers(__user__),
            json={"model": "tts-1", "input": text, "voice": voice, "response_format": "mp3"},
            timeout=self.valves.timeout,
        )
        r.raise_for_status()
        await self._emit_audio(__event_emitter__, r.content, f"🔊 {voice}")
        return f"Generated speech with the '{voice}' voice ({len(r.content)} bytes)."

    async def generate_sound_effect(
        self,
        description: str,
        seconds: float = 8.0,
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        Generate a single sound effect from a description (a door, rain, footsteps).
        Up to 30 seconds. Requires a paid Uttera plan (Startup and up). The player is
        shown in the chat.
        """
        r = requests.post(
            f"{self.valves.base_url}/audio/sfx",
            headers=self._headers(__user__),
            json={"prompt": description, "seconds": seconds, "translate": True},
            timeout=self.valves.timeout,
        )
        r.raise_for_status()
        await self._emit_audio(__event_emitter__, r.content, f"🎧 {description}")
        return f"Generated a {seconds:g}s sound effect: {description}."

    async def generate_music(
        self,
        description: str,
        seconds: float = 30.0,
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        Generate a finished piece of music from a description. Up to ~6 minutes.
        Naming a style, instruments and BPM helps far more than "something upbeat".
        Requires a paid Uttera plan (Startup and up). The player is shown in the chat.
        """
        r = requests.post(
            f"{self.valves.base_url}/audio/music",
            headers=self._headers(__user__),
            json={"prompt": description, "seconds": seconds, "translate": True},
            timeout=self.valves.timeout,
        )
        r.raise_for_status()
        await self._emit_audio(__event_emitter__, r.content, f"🎵 {description}")
        return f"Generated {seconds:g}s of music: {description}."
