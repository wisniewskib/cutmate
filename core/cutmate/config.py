import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .errors import ConfigError
from .formats import FORMATS

BACKENDS = ("local", "groq", "openai", "elevenlabs")
LANGUAGES = ("pl", "en")
CAPTION_MODES = ("burn", "srt", "both", "none")
DEFAULT_STEPS = {"factcheck": True, "qa": True, "thumbnail": True}
DEFAULT_MUSIC = {"source": "none", "folder": None}
DEFAULT_CAPTIONS = {"9:16": "burn", "16:9": "srt"}


def home() -> Path:
    return Path(os.environ.get("CUTMATE_HOME") or Path.home() / ".cutmate")


@dataclass
class Config:
    transcription: str = "local"
    language: str = "pl"
    theme: str = "clean"
    steps: dict = field(default_factory=lambda: dict(DEFAULT_STEPS))
    music: dict = field(default_factory=lambda: dict(DEFAULT_MUSIC))
    captions: dict = field(default_factory=lambda: dict(DEFAULT_CAPTIONS))

    def __post_init__(self):
        self.steps = {**DEFAULT_STEPS, **(self.steps or {})}
        self.music = {**DEFAULT_MUSIC, **(self.music or {})}
        self.captions = {**DEFAULT_CAPTIONS, **(self.captions or {})}


def load(path: Path | None = None) -> Config:
    path = Path(path) if path else home() / "config.json"
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(f"{path}: cannot read config file ({e.__class__.__name__}). Run /cutmate:setup to rewrite it.") from None
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: invalid JSON ({e.msg}). Run /cutmate:setup to rewrite it.") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: must be a JSON object. Run /cutmate:setup to rewrite it.") from None
    if "steps" in data and not isinstance(data["steps"], dict):
        raise ConfigError(f"{path}: steps must be a JSON object, got {type(data['steps']).__name__}")
    if "music" in data and not isinstance(data["music"], dict):
        raise ConfigError(f"{path}: music must be a JSON object, got {type(data['music']).__name__}")
    if "captions" in data and not isinstance(data["captions"], dict):
        raise ConfigError(f"{path}: captions must be a JSON object, got {type(data['captions']).__name__}")
    cfg = Config(**{k: v for k, v in data.items() if k in Config.__dataclass_fields__})
    if cfg.transcription not in BACKENDS:
        raise ConfigError(f"{path}: transcription must be one of {', '.join(BACKENDS)}, got {cfg.transcription!r}")
    if cfg.language not in LANGUAGES:
        raise ConfigError(f"{path}: language must be one of {', '.join(LANGUAGES)}, got {cfg.language!r}")
    for fmt, mode in cfg.captions.items():
        if fmt not in FORMATS:
            raise ConfigError(f"{path}: captions has unknown format {fmt!r} (use 9:16 or 16:9)")
        if mode not in CAPTION_MODES:
            raise ConfigError(f"{path}: captions[{fmt!r}] must be one of burn, srt, both, none, got {mode!r}")
    return cfg


def save(cfg: Config, path: Path | None = None) -> Path:
    path = Path(path) if path else home() / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
