"""Persisted user settings, stored as TOML.

Settings live in ``~/.config/boxtube/config.toml`` (override with
``BOXTUBE_CONFIG``). Each setting optionally maps to an existing ``BOXTUBE_*``
environment variable; :func:`apply_to_env` pushes the saved values into the
environment so the rest of the app — which already reads those env vars at use
time — picks them up without further wiring. An env var set in the shell still
wins over the config file (it's applied with ``setdefault``).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    kind: str  # "int" | "choice" | "bool"
    default: object
    env: str | None = None
    choices: tuple[str, ...] | None = None
    minimum: int | None = None
    maximum: int | None = None
    help: str = ""


# The settings shown in the Settings screen, in display order.
SCHEMA: tuple[Setting, ...] = (
    Setting("player_height", "Video resolution cap", "int", 360,
            env="BOXTUBE_PLAYER_HEIGHT", minimum=144, maximum=1080,
            help="Max source height mpv decodes. Higher = sharper but heavier."),
    Setting("player_maxwidth", "Frame width cap (px)", "int", 480,
            env="BOXTUBE_PLAYER_MAXWIDTH", minimum=240, maximum=3840,
            help="Upper bound on rendered frame width. Raise on a fast terminal."),
    Setting("player_fps", "Player frame rate", "int", 15,
            env="BOXTUBE_PLAYER_FPS", minimum=1, maximum=60,
            help="Render/capture frames per second."),
    Setting("image_backend", "Image backend", "choice", "auto",
            env="BOXTUBE_IMAGE_BACKEND",
            choices=("auto", "sixel", "kitty", "halfcell", "unicode"),
            help="Force the player's image protocol (auto = detect best)."),
    Setting("screenshot_format", "Frame capture format", "choice", "jpg",
            env="BOXTUBE_SCREENSHOT_FORMAT", choices=("jpg", "png"),
            help="png is lossless (sharper, heavier); jpg is faster."),
    Setting("audio_buffer", "Audio buffer (seconds)", "choice", "0.6",
            env="BOXTUBE_AUDIO_BUFFER", choices=("0.3", "0.6", "1.0", "2.0"),
            help="Larger absorbs CPU spikes (less crackle) at a little seek latency."),
    Setting("thumb_cache", "Thumbnail cache size", "int", 64,
            env="BOXTUBE_THUMB_CACHE_SIZE", minimum=0, maximum=512,
            help="Thumbnails kept in memory (0 disables caching)."),
    Setting("grid_density", "Grid density", "choice", "normal",
            choices=("compact", "normal", "comfortable"),
            help="Card size in the video grid (affects columns per row)."),
    Setting("playback_cookies", "Send cookies to playback", "bool", False,
            env="BOXTUBE_PLAYBACK_COOKIES",
            help="Needed for private/members-only videos; can break normal playback."),
)

_BY_KEY = {s.key: s for s in SCHEMA}

# Grid density → target card width in columns (consumed by app._card_width).
GRID_DENSITY_WIDTH = {"compact": 20, "normal": 24, "comfortable": 30}


def config_path() -> Path:
    override = os.environ.get("BOXTUBE_CONFIG")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    return Path(base) / "boxtube" / "config.toml"


def defaults() -> dict:
    return {s.key: s.default for s in SCHEMA}


def _coerce(setting: Setting, value) -> object:
    """Validate/normalise a raw value against the schema; fall back to default."""
    try:
        if setting.kind == "int":
            v = int(value)
            if setting.minimum is not None:
                v = max(setting.minimum, v)
            if setting.maximum is not None:
                v = min(setting.maximum, v)
            return v
        if setting.kind == "bool":
            return bool(value)
        if setting.kind == "choice":
            v = str(value).strip().lower()
            return v if (setting.choices and v in setting.choices) else setting.default
    except (TypeError, ValueError):
        return setting.default
    return setting.default


def load() -> dict:
    """Load settings merged over the defaults. Never raises."""
    values = defaults()
    path = config_path()
    try:
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return values
    for key, setting in _BY_KEY.items():
        if key in raw:
            values[key] = _coerce(setting, raw[key])
    return values


def _dump_toml(values: dict) -> str:
    lines = ["# BoxTube settings — edit in-app via the Settings screen (press ,)"]
    for s in SCHEMA:
        v = values.get(s.key, s.default)
        if s.kind == "bool":
            rendered = "true" if v else "false"
        elif s.kind == "int":
            rendered = str(int(v))
        else:
            escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
            rendered = f'"{escaped}"'
        lines.append(f"{s.key} = {rendered}")
    return "\n".join(lines) + "\n"


def save(values: dict) -> Path:
    """Write settings to the config file, creating parent dirs. Returns the path."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {s.key: _coerce(s, values.get(s.key, s.default)) for s in SCHEMA}
    path.write_text(_dump_toml(clean), encoding="utf-8")
    return path


def _env_value(setting: Setting, value) -> str:
    if setting.kind == "bool":
        return "1" if value else ""
    if setting.key == "image_backend" and value == "auto":
        return ""  # empty → textual-image auto-detection
    return str(value)


def apply_to_env(values: dict, *, overwrite: bool = False) -> None:
    """Push env-mapped settings into ``os.environ``.

    With ``overwrite=False`` (startup) a shell-set env var wins over the config.
    With ``overwrite=True`` (after an in-app save) the chosen values take effect
    immediately for the next playback / thumbnail fetch.
    """
    for s in SCHEMA:
        if not s.env:
            continue
        ev = _env_value(s, values.get(s.key, s.default))
        if overwrite:
            os.environ[s.env] = ev
        else:
            os.environ.setdefault(s.env, ev)
