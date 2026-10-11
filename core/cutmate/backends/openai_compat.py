import os
from pathlib import Path

import requests

from ..errors import BackendError
from ..transcript import Transcript, Word
from .upload import encode_for_upload


class OpenAICompatBackend:
    """Groq and OpenAI share the OpenAI transcription API (verbose_json + word granularity)."""

    def __init__(self, name: str, url: str, key_env: str, model: str, limit_bytes: int):
        self.name, self.url, self.key_env, self.model, self.limit_bytes = name, url, key_env, model, limit_bytes

    def transcribe(self, wav: Path, language: str, prompt: str | None = None) -> Transcript:
        key = os.environ.get(self.key_env)
        if not key:
            raise BackendError(f"{self.key_env} is not set. Set it in your shell profile and restart Claude Code "
                               f"(README → Transcription), or run /cutmate:setup to pick another backend.")
        up = encode_for_upload(wav, self.limit_bytes, self.name)
        data = [("model", self.model), ("language", language), ("response_format", "verbose_json"),
                ("timestamp_granularities[]", "word"), ("temperature", "0")]
        if prompt:
            data.append(("prompt", prompt))
        try:
            with open(up, "rb") as f:
                r = requests.post(self.url, headers={"Authorization": f"Bearer {key}"}, data=data,
                                  files={"file": (up.name, f, "audio/mpeg")}, timeout=900)
        except requests.RequestException as e:
            raise BackendError(f"{self.name}: request failed ({e.__class__.__name__}). Check your connection.") from None
        if r.status_code == 401:
            raise BackendError(f"{self.name}: API key rejected (401). Check {self.key_env}.")
        if r.status_code == 429:
            raise BackendError(f"{self.name}: rate limit or quota hit (429). Wait a minute or switch backend.")
        if not r.ok:
            raise BackendError(f"{self.name}: HTTP {r.status_code}: {r.text[:300]}")
        body = r.json()
        if not isinstance(body.get("words"), list):
            raise BackendError(f"{self.name}: response has no word timestamps (model {self.model}). "
                               f"Switch backend with /cutmate:setup.")
        words = [Word(w["word"].strip(), float(w["start"]), float(w["end"])) for w in body["words"] if w["word"].strip()]
        return Transcript(language, sorted(words, key=lambda w: w.start), self.name)
