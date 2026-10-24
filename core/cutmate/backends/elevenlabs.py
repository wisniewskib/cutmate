import math
import os
from pathlib import Path

import requests

from ..errors import BackendError
from ..transcript import Transcript, Word
from .upload import encode_for_upload

URL = "https://api.elevenlabs.io/v1/speech-to-text"
KEY_ENV = "ELEVENLABS_API_KEY"


class ElevenLabsBackend:
    name = "elevenlabs"
    model = "scribe_v2"
    limit_bytes = 5_000_000_000

    def transcribe(self, wav: Path, language: str, prompt: str | None = None) -> Transcript:
        key = os.environ.get(KEY_ENV)
        if not key:
            raise BackendError(f"{KEY_ENV} is not set. Set it in your shell profile and restart Claude Code "
                               f"(docs/installation.md → Klucze API), or run /cutmate:setup to pick another backend.")
        up = encode_for_upload(wav, self.limit_bytes, self.name)
        data = {"model_id": self.model, "language_code": language, "timestamps_granularity": "word",
                "tag_audio_events": "false"}
        try:
            try:
                with open(up, "rb") as f:
                    r = requests.post(URL, headers={"xi-api-key": key}, data=data,
                                      files={"file": (up.name, f, "audio/mpeg")}, timeout=900)
            except requests.RequestException as e:
                raise BackendError(f"{self.name}: request failed ({e.__class__.__name__}). Check your connection.") from None
            if r.status_code == 401:
                raise BackendError(f"{self.name}: API key rejected (401). Check {KEY_ENV}.")
            if r.status_code == 429:
                raise BackendError(f"{self.name}: rate limit or quota hit (429). Wait a minute or switch backend.")
            if not r.ok:
                raise BackendError(f"{self.name}: HTTP {r.status_code}: {' '.join(r.text.split())[:300]} — or switch backend with /cutmate:setup.")
            try:
                body = r.json()
                if not isinstance(body.get("words"), list):
                    raise BackendError(f"{self.name}: response has no word timestamps. Switch backend with /cutmate:setup.")
                words = [Word(w["text"].strip(), float(w["start"]), float(w["end"]),
                              math.exp(w["logprob"]) if w.get("logprob") is not None else None)
                         for w in body["words"] if w.get("type") == "word" and w["text"].strip()]
            except (ValueError, KeyError, TypeError, AttributeError):
                raise BackendError(f"{self.name}: unexpected response format from the API") from None
            return Transcript(language, words, self.name)
        finally:
            up.unlink(missing_ok=True)
