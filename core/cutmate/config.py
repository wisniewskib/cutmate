import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .errors import ConfigError

BACKENDS = ("local", "groq", "openai", "elevenlabs")
LANGUAGES = ("pl", "en")
DEFAULT_STEPS = {"factcheck": True, "qa": True, "thumbnail": True}
DEFAULT_MUSIC = {"source": "none", "folder": None}


def home() -> Path:
    return Path(os.environ.get("CUTMATE_HOME") or Path.home() / ".cutmate")


@dataclass
class Config:
    transcription: str = "local"
    language: str = "pl"
    theme: str = "neutral"
    steps: dict = field(default_factory=lambda: dict(DEFAULT_STEPS))
    music: dict = field(default_factory=lambda: dict(DEFAULT_MUSIC))

    def __post_init__(self):
        self.steps = {**DEFAULT_STEPS, **(self.steps or {})}
        self.music = {**DEFAULT_MUSIC, **(self.music or {})}


def load(path: Path | None = None) -> Config:
    path = Path(path) if path else home() / "config.json"
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: invalid JSON ({e.msg}). Run /cutmate:setup to rewrite it.") from None
    cfg = Config(**{k: v for k, v in data.items() if k in Config.__dataclass_fields__})
    if cfg.transcription not in BACKENDS:
        raise ConfigError(f"{path}: transcription must be one of {', '.join(BACKENDS)}, got {cfg.transcription!r}")
    if cfg.language not in LANGUAGES:
        raise ConfigError(f"{path}: language must be one of {', '.join(LANGUAGES)}, got {cfg.language!r}")
    return cfg


def save(cfg: Config, path: Path | None = None) -> Path:
    path = Path(path) if path else home() / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
