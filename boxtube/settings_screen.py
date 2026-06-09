"""Modal Settings screen — edit and persist user preferences.

Reads/writes via :mod:`boxtube.config`. On save it writes the TOML config and
pushes the values into the environment (``apply_to_env(overwrite=True)``) so the
next playback / thumbnail fetch uses them without a restart, then dismisses with
the saved values so the app can apply anything that's live (e.g. grid density).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch

from . import config


class SettingsScreen(ModalScreen):
    """A centered dialog for editing settings."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=True)]

    def __init__(self, values: dict) -> None:
        super().__init__()
        self.values = values

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Static("⚙  Settings", id="settings-title")
            with VerticalScroll(id="settings-body"):
                for setting in config.SCHEMA:
                    with Horizontal(classes="setting-row"):
                        yield Label(setting.label, classes="setting-label")
                        yield self._control(setting)
                    yield Static(setting.help, classes="setting-help")
            with Horizontal(id="settings-buttons"):
                yield Button("Save", variant="primary", id="settings-save")
                yield Button("Cancel", id="settings-cancel")

    def _control(self, setting: config.Setting):
        current = self.values.get(setting.key, setting.default)
        cid = f"set-{setting.key}"
        if setting.kind == "bool":
            return Switch(value=bool(current), id=cid, classes="setting-control")
        if setting.kind == "choice":
            options = [(choice, choice) for choice in (setting.choices or ())]
            return Select(options, value=current, allow_blank=False, id=cid,
                          classes="setting-control")
        return Input(value=str(current), type="integer", id=cid, classes="setting-control")

    def _collect(self) -> dict:
        new: dict = {}
        for setting in config.SCHEMA:
            new[setting.key] = self.query_one(f"#set-{setting.key}").value
        return new

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-cancel":
            self.dismiss(None)
        elif event.button.id == "settings-save":
            config.save(self._collect())          # writes TOML (coerces/validates)
            values = config.load()                 # canonical, coerced values
            config.apply_to_env(values, overwrite=True)
            self.dismiss(values)

    def action_cancel(self) -> None:
        self.dismiss(None)
