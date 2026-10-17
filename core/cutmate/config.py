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
MUSIC_SOURCES = ("heygen", "folder", "none")
DEFAULT_MUSIC = {"source": "none", "folder": None, "volume": 0.45}
SETTABLE = ("transcription", "language", "theme", "steps.factcheck", "steps.qa", "steps.thumbnail",
            "music.source", "music.folder", "music.volume", "captions.9:16", "captions.16:9")
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
    return validate(Config(**{k: v for k, v in data.items() if k in Config.__dataclass_fields__}), str(path))


def validate(cfg: Config, where: str) -> Config:
    if cfg.transcription not in BACKENDS:
        raise ConfigError(f"{where}: transcription must be one of {', '.join(BACKENDS)}, got {cfg.transcription!r}")
    if cfg.language not in LANGUAGES:
        raise ConfigError(f"{where}: language must be one of {', '.join(LANGUAGES)}, got {cfg.language!r}")
    for fmt, mode in cfg.captions.items():
        if fmt not in FORMATS:
            raise ConfigError(f"{where}: captions has unknown format {fmt!r} (use 9:16 or 16:9)")
        if mode not in CAPTION_MODES:
            raise ConfigError(f"{where}: captions[{fmt!r}] must be one of burn, srt, both, none, got {mode!r}")
    if cfg.music["source"] not in MUSIC_SOURCES:
        raise ConfigError(f"{where}: music.source must be one of {', '.join(MUSIC_SOURCES)}, got {cfg.music['source']!r}")
    v = cfg.music["volume"]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 2:
        raise ConfigError(f"{where}: music.volume must be a number from 0 to 2, got {v!r}")
    return cfg


def save(cfg: Config, path: Path | None = None) -> Path:
    path = Path(path) if path else home() / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _parse(key: str, value: str):
    if key.startswith("steps."):
        if value not in ("true", "false"):
            raise ConfigError(f"{key} must be true or false")
        return value == "true"
    if key == "music.volume":
        try:
            return float(value)
        except ValueError:
            raise ConfigError("music.volume must be a number from 0 to 2") from None
    if key == "music.folder":
        return None if value in ("", "null") else str(Path(value).expanduser().resolve())
    return value


def set_values(pairs: list[str], path: Path | None = None) -> Config:
    from . import paths
    from .music import AUDIO_EXTS
    path = Path(path) if path else home() / "config.json"
    try:
        cfg = load(path)
    except ConfigError:
        print(f"WARN config: {path} was unreadable — starting from defaults")
        cfg = Config()
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or key not in SETTABLE:
            raise ConfigError(f"unknown config key {key!r} (settable: {', '.join(SETTABLE)}). API keys belong in environment "
                              "variables (GROQ_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY), never in the config")
        parsed = _parse(key, value)
        head, _, tail = key.partition(".")
        if tail:
            getattr(cfg, head)[tail] = parsed
        else:
            if key == "theme":
                paths.theme_dir(value)
            setattr(cfg, key, parsed)
    validate(cfg, str(path))
    if cfg.music["source"] == "folder":
        folder = Path(cfg.music["folder"] or "")
        if not cfg.music["folder"] or not folder.is_dir() or not any(
                f.is_file() and f.suffix.lower() in AUDIO_EXTS for f in folder.iterdir()):
            raise ConfigError(f"music.source=folder needs a music.folder with at least one audio file "
                              f"({' '.join(sorted(AUDIO_EXTS))}), got {cfg.music['folder'] or folder}")
    save(cfg, path)
    return cfg
