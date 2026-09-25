"""
title: Uttera Voice AI
author: Uttera Labs
author_url: https://uttera.ai
funding_url: https://uttera.ai
version: 0.2.0
license: MIT
description: EU-hosted, OpenAI-compatible voice AI. Transcribe and summarise calls (with speaker diarization, tone and a signed PDF report), translate recordings, read text aloud in ~30 languages, score pronunciation, and generate sound effects, sound scenes and music. Full parity with Uttera's public API. Audio is processed in Spain, discarded after answering and never used for training.
requirements: requests
"""

import base64
import json
import requests
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        base_url: str = Field(
            default="https://api.uttera.ai/v1",
            description="Uttera API base URL (OpenAI-compatible).",
        )
        timeout: int = Field(
            default=600,
            description="Per-request timeout in seconds (audio and music can be long).",
        )
        api_key: str = Field(
            default="",
            description="Uttera API key, e.g. sk-echo-xxxxxxxx — get one at https://app.uttera.ai . On a single-user instance set it here; on a shared instance leave it blank and let each user set their own in User Valves.",
            json_schema_extra={"placeholder": "sk-echo-..."},
        )

    class UserValves(BaseModel):
        api_key: str = Field(
            default="",
            description="Your personal Uttera API key, e.g. sk-echo-xxxxxxxx — get one at https://app.uttera.ai . Overrides the tool's global key.",
            json_schema_extra={"placeholder": "sk-echo-..."},
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
            key = getattr(self.valves, "api_key", "") or ""
        if not key:
            raise Exception(
                "No Uttera API key set. Paste your key (sk-echo-...) in this tool's "
                "Valves (gear icon) or in your User Valves. Create one at "
                "https://app.uttera.ai"
            )
        return key

    def _headers(self, __user__, extra=None) -> dict:
        h = {"Authorization": f"Bearer {self._key(__user__)}"}
        if extra:
            h.update(extra)
        return h

    def _fetch(self, url: str):
        """Download an https audio URL. Attachments do NOT reach the backend."""
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

    def _err(self, r) -> str:
        """A readable message from a non-2xx API response (plan gates, 4xx…)."""
        try:
            j = r.json()
            msg = j.get("error") or j.get("detail") or j.get("message") or r.text
            if isinstance(msg, dict):
                msg = msg.get("message") or json.dumps(msg)
        except Exception:
            msg = r.text
        return f"Uttera API error {r.status_code}: {str(msg)[:400]}"

    async def _emit_audio(self, __event_emitter__, audio: bytes, mime: str, caption: str):
        """Show an audio player in the chat, as an HTML *embed* (NOT a 'message':
        Open WebUI renders message content as sanitised Markdown, which dumps the
        base64 on screen). The 'embeds' event renders HTML in a sandboxed iframe,
        where the data-URI audio plays."""
        if __event_emitter__ is None:
            return
        b64 = base64.b64encode(audio).decode()
        html = (
            f'<p style="font:14px system-ui;margin:0 0 .4rem">{caption}</p>'
            f'<audio controls preload="metadata" style="width:100%"'
            f' src="data:{mime};base64,{b64}"></audio>'
        )
        await __event_emitter__(
            {"type": "embeds", "data": {"embeds": [html], "replace": False}}
        )

    async def _emit_pdf(self, __event_emitter__, pdf_b64: str, filename: str, caption: str):
        """Offer a generated PDF as a download link, via an 'embeds' HTML block."""
        if __event_emitter__ is None:
            return
        html = (
            f'<p style="font:14px system-ui;margin:0 0 .4rem">{caption}</p>'
            f'<a download="{filename}" href="data:application/pdf;base64,{pdf_b64}"'
            f' style="font:14px system-ui;display:inline-block;padding:.5rem .9rem;'
            f'border:1px solid #888;border-radius:8px;text-decoration:none">'
            f'⬇️ {filename}</a>'
        )
        await __event_emitter__(
            {"type": "embeds", "data": {"embeds": [html], "replace": False}}
        )

    # ══ audio → text ═════════════════════════════════════════════════════
    def transcribe_audio(self, audio_url: str, language: str = "", __user__: dict = {}) -> str:
        """
        Transcribe a recording to plain text. Best for short clips when you want
        the literal words; for anything past a couple of minutes prefer
        summarise_recording (transcript + who spoke + tone in one upload).
        The audio MUST be an https URL Uttera can download; a file attached to the
        chat will NOT work, so ask the user for a direct link.
        :param audio_url: https URL to the audio (wav/mp3/m4a/ogg/flac/opus/webm).
        :param language: optional ISO code (e.g. "es") to force the language; empty = auto-detect.
        """
        content, name = self._fetch(audio_url)
        data = {"model": "whisper-1"}
        if language:
            data["language"] = language
        r = requests.post(f"{self.valves.base_url}/audio/transcriptions",
                          headers=self._headers(__user__),
                          files={"file": (name, content)}, data=data,
                          timeout=self.valves.timeout)
        if not r.ok:
            return self._err(r)
        try:
            return r.json().get("text", "")
        except Exception:
            return r.text

    def summarise_recording(self, audio_url: str, language: str = "", __user__: dict = {}) -> str:
        """
        Transcribe AND analyse a recording in one call: full transcript, who spoke
        when (diarization), the tone, and a structured summary (what it is, key
        points, concrete data, what to do). Best for calls, meetings, lectures or
        interviews. Requires a Professional plan or above. For a SIGNED PDF report,
        use signed_report instead. The audio_url MUST be an https URL Uttera can
        download (a chat attachment will not work).
        :param language: optional ISO code to force the transcript language.
        """
        content, name = self._fetch(audio_url)
        ruta = "/summarize" + (f"?language={language}" if language else "")
        r = requests.post(f"{self.valves.base_url}{ruta}",
                          headers=self._headers(__user__),
                          files={"file": (name, content)}, timeout=self.valves.timeout)
        if not r.ok:
            return self._err(r)
        try:
            j = r.json()
        except Exception:
            return r.text
        out = j.get("summary", "") or r.text
        u = j.get("usage", {})
        if u:
            out += f"\n\n_(Uttera credits: {u.get('credits', '?')})_"
        return out

    async def signed_report(self, audio_url: str, title: str = "",
                            __user__: dict = {}, __event_emitter__=None) -> str:
        """
        Produce a cryptographically SIGNED PDF report of a recorded call or meeting:
        transcript, who spoke when, tone and a structured summary, in a PDF that
        Uttera signs and that ANYONE can verify (public-key) at /v1/reports/verify.
        Requires a Developer plan or above; the report itself is free. If the plan
        does not include it, the analysis is still returned with a note. The
        audio_url MUST be an https URL Uttera can download. A download link for the
        PDF is shown in the chat.
        :param title: optional title to print on the report.
        """
        content, name = self._fetch(audio_url)
        extra = {}
        if title:
            extra["X-Report-Title-B64"] = base64.b64encode(title.encode("utf-8")).decode("ascii")
        r = requests.post(f"{self.valves.base_url}/summarize?report=pdf",
                          headers=self._headers(__user__, extra),
                          files={"file": (name, content)}, timeout=self.valves.timeout)
        if not r.ok:
            return self._err(r)
        j = r.json()
        out = j.get("summary", "") or ""
        rep = j.get("report") or {}
        pdf_b64 = rep.get("pdf_base64")
        if not pdf_b64:
            avisos = j.get("avisos") or j.get("warnings") or []
            nota = "; ".join(avisos) if isinstance(avisos, list) else str(avisos)
            return out + "\n\n_(No signed PDF produced. " + (
                nota or "The signed PDF report requires the Developer plan or above.") + ")_"
        fname = rep.get("filename") or "uttera-report.pdf"
        await self._emit_pdf(__event_emitter__, pdf_b64, fname,
                             "\U0001f4c4 " + (title or "Signed call report"))
        fp = rep.get("content_fingerprint") or rep.get("pdf_sha256") or ""
        out += ("\n\n_(Signed PDF ready above — verifiable by anyone at "
                "/v1/reports/verify" + (f", fingerprint {fp[:16]}…" if fp else "") + ")_")
        return out

    def identify_speakers(self, audio_url: str, __user__: dict = {}) -> str:
        """
        Diarization: who speaks and when. Returns the segments with their speaker
        label and start/end times. The audio_url MUST be an https URL.
        """
        content, name = self._fetch(audio_url)
        r = requests.post(f"{self.valves.base_url}/audio/diarize",
                          headers=self._headers(__user__),
                          files={"file": (name, content)}, timeout=self.valves.timeout)
        return r.text if r.ok else self._err(r)

    def translate_recording(self, audio_url: str, target_language: str, __user__: dict = {}) -> str:
        """
        Translate a recording into another language: text, and where the plan
        allows it, voice. The audio_url MUST be an https URL.
        :param target_language: a code such as en, es, fr, de.
        """
        content, name = self._fetch(audio_url)
        r = requests.post(f"{self.valves.base_url}/translate",
                          headers=self._headers(__user__),
                          files={"file": (name, content)},
                          data={"target_language": target_language},
                          timeout=self.valves.timeout)
        return r.text if r.ok else self._err(r)

    def analyze_pronunciation(self, audio_url: str, text: str, language: str = "es",
                              explain: bool = True, __user__: dict = {}) -> str:
        """
        Compare a recording against the sentence it was meant to say, phoneme by
        phoneme. Returns the accuracy, both IPA strings (expected vs heard) and the
        grouped errors (type substitution|missing|extra, expected, heard, times,
        words). explain=False skips the written explanation and is far cheaper.
        The audio_url MUST be an https URL.
        :param text: the sentence the speaker was supposed to say.
        :param language: language code of the sentence (default "es").
        """
        content, name = self._fetch(audio_url)
        r = requests.post(f"{self.valves.base_url}/pronunciation",
                          headers=self._headers(__user__),
                          files={"file": (name, content)},
                          data={"text": text, "language": language,
                                "explain": "true" if explain else "false"},
                          timeout=self.valves.timeout)
        return r.text if r.ok else self._err(r)

    # ══ text / prompt → audio (shown as a player in the chat) ════════════
    async def text_to_speech(self, text: str, voice: str = "alloy", language: str = "",
                             __user__: dict = {}, __event_emitter__=None) -> str:
        """
        Read text aloud in a natural voice (~30 languages, inferred from the text).
        Call list_voices for the full catalogue. An audio player is shown in the
        chat. ⚠ Line breaks are billed as ~1.3 s pauses each — strip them from
        formatted text first.
        :param voice: a voice name (alloy, echo, fable, onyx, nova, shimmer, or any from list_voices).
        :param language: optional ISO code to force the language.
        """
        body = {"model": "tts-1", "input": text, "voice": voice, "response_format": "mp3"}
        if language:
            body["language"] = language
        r = requests.post(f"{self.valves.base_url}/audio/speech",
                          headers=self._headers(__user__), json=body,
                          timeout=self.valves.timeout)
        if not r.ok:
            return self._err(r)
        await self._emit_audio(__event_emitter__, r.content, "audio/mpeg", f"\U0001f50a {voice}")
        return f"Generated speech with the '{voice}' voice ({len(r.content)} bytes)."

    async def generate_sound_effect(self, description: str, seconds: float = 10.0,
                                    seed: int = -1, __user__: dict = {},
                                    __event_emitter__=None) -> str:
        """
        Generate a single sound effect from a description (a door, rain, footsteps).
        Up to 30 seconds. Requires a paid plan (Startup and up). The description
        works better in English. A fixed seed reproduces the same sound. The player
        is shown in the chat.
        """
        body = {"prompt": description, "seconds": seconds, "translate": True}
        if seed >= 0:
            body["seed"] = seed
        r = requests.post(f"{self.valves.base_url}/audio/sfx",
                          headers=self._headers(__user__), json=body,
                          timeout=self.valves.timeout)
        if not r.ok:
            return self._err(r)
        await self._emit_audio(__event_emitter__, r.content, "audio/wav", f"\U0001f3a7 {description}")
        return f"Generated a {seconds:g}s sound effect: {description}."

    async def generate_music(self, description: str, seconds: float = 60.0, steps: int = 32,
                             seed: int = -1, __user__: dict = {}, __event_emitter__=None) -> str:
        """
        Generate a finished piece of music from a description. Up to ~380 s.
        Requires a paid plan (Startup and up). ⚠ BOTH controls cost: price = length
        × steps, so 380 s at 128 steps is ~8× a 60 s at 32. Naming a style,
        instruments and BPM helps far more than "something upbeat". The player is
        shown in the chat.
        """
        body = {"prompt": description, "seconds": seconds, "steps": steps, "translate": True}
        if seed >= 0:
            body["seed"] = seed
        r = requests.post(f"{self.valves.base_url}/audio/music",
                          headers=self._headers(__user__), json=body,
                          timeout=self.valves.timeout)
        if not r.ok:
            return self._err(r)
        await self._emit_audio(__event_emitter__, r.content, "audio/wav", f"\U0001f3b5 {description}")
        return f"Generated {seconds:g}s of music: {description}."

    def plan_sound_scene(self, description: str, seconds: float = 20.0, __user__: dict = {}) -> str:
        """
        Turn a long description into sound events placed in time. Generates NO audio
        (so it costs almost nothing): use it before generate_sound_scene to see, or
        let the user correct, what will be made. Returns JSON with `events`, each
        with `start`, `duration` and `prompt`.
        """
        r = requests.post(f"{self.valves.base_url}/audio/sfx/plan",
                          headers=self._headers(__user__),
                          json={"prompt": description, "seconds": seconds},
                          timeout=self.valves.timeout)
        return r.text if r.ok else self._err(r)

    async def generate_sound_scene(self, plan: str, __user__: dict = {},
                                   __event_emitter__=None) -> str:
        """
        Generate every event of a plan and mix them into one scene. `plan` is the
        JSON that plan_sound_scene returned (edited if you want). This is the step
        that costs — each event is a generation. Requires a paid plan (Startup up).
        The mixed scene is shown as a player in the chat.
        """
        try:
            cuerpo = json.loads(plan) if isinstance(plan, str) else plan
        except Exception as e:
            return f"`plan` must be the JSON returned by plan_sound_scene: {e}"
        r = requests.post(f"{self.valves.base_url}/audio/sfx/scene",
                          headers=self._headers(__user__), json=cuerpo,
                          timeout=self.valves.timeout)
        if not r.ok:
            return self._err(r)
        d = r.json()
        if "mix" not in d:
            return f"The scene came back without a mix: {r.text[:200]}"
        await self._emit_audio(__event_emitter__, base64.b64decode(d["mix"]),
                               "audio/wav", "\U0001f39b️ sound scene")
        return "Generated the sound scene (mix shown above)."

    # ══ helpers that inform a decision ═══════════════════════════════════
    def verify_report(self, report: str, __user__: dict = {}) -> str:
        """
        Check whether a signed Uttera report is genuine and unmodified. `report` is
        the report's JSON. Verifying is a public-key operation, so it proves the
        document came from Uttera and has not been altered.
        """
        try:
            cuerpo = json.loads(report) if isinstance(report, str) else report
        except Exception as e:
            return f"`report` must be the report's JSON: {e}"
        r = requests.post(f"{self.valves.base_url}/reports/verify",
                          headers=self._headers(__user__), json=cuerpo,
                          timeout=self.valves.timeout)
        return r.text if r.ok else self._err(r)

    def list_voices(self, __user__: dict = {}) -> str:
        """List the available text-to-speech voices and the language each one speaks."""
        r = requests.get(f"{self.valves.base_url}/audio/voices",
                         headers=self._headers(__user__), timeout=self.valves.timeout)
        return r.text if r.ok else self._err(r)

    def last_call_cost(self, __user__: dict = {}) -> str:
        """
        What the previous API call actually cost, in credits, broken down. Worth
        checking before running something many times, to tell the user honestly
        what a batch will cost.
        """
        r = requests.get(f"{self.valves.base_url}/usage/last",
                         headers=self._headers(__user__), timeout=self.valves.timeout)
        return r.text if r.ok else self._err(r)
