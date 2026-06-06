"""BoxTube — a TUI YouTube client built with Textual.

Search YouTube, browse results, and watch videos rendered directly inside the
terminal via mpv.
"""

from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static
from textual_image.widget import Image

from . import player, thumbnails
from .youtube import SearchError, Video, search


class VideoItem(ListItem):
    """A single result row in the results list."""

    def __init__(self, video: Video) -> None:
        super().__init__()
        self.video = video

    def compose(self) -> ComposeResult:
        v = self.video
        yield Label(v.title, classes="title")
        yield Label(
            f"[b]{v.channel}[/b]   {v.duration_str}   {v.views_str} views",
            classes="meta",
            markup=True,
        )


class BoxTube(App[None]):
    """The BoxTube application."""

    CSS_PATH = "boxtube.tcss"
    TITLE = "BoxTube"

    BINDINGS = [
        Binding("ctrl+c,ctrl+q", "quit", "Quit", priority=True),
        Binding("slash", "focus_search", "Search", show=True),
        Binding("enter", "play", "Play", show=True),
        Binding("p", "play", "Play", show=False),
        Binding("o", "open_browser", "Open in browser", show=True),
        Binding("escape", "focus_search", "Search", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._current_video_id: str | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="appbar"):
            yield Static("[#ff6b6b]●[/]  [b]BoxTube[/b]", id="brand", markup=True)
            yield Static("press [#ff6b6b]/[/] to search", id="brand-hint", markup=True)
        yield Input(placeholder="Search YouTube…", id="search")
        with Horizontal(id="body"):
            yield ListView(id="results")
            with VerticalScroll(id="detail-pane"):
                yield Image(thumbnails.placeholder(), id="thumb")
                yield Static(self._welcome_text(), id="meta", markup=True)
                yield Static("", id="desc", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search", Input).border_title = "Search"
        self.query_one("#results", ListView).border_title = "Results"
        self.query_one("#detail-pane").border_title = "Preview"
        self.query_one("#search", Input).focus()

    # ----- actions -------------------------------------------------------

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_play(self) -> None:
        item = self._current_item()
        if item is None:
            self.notify("Highlight a video first.", severity="warning")
            return
        self._watch(item.video)

    def action_open_browser(self) -> None:
        item = self._current_item()
        if item is None:
            self.notify("Highlight a video first.", severity="warning")
            return
        import webbrowser

        webbrowser.open(item.video.watch_url)
        self.notify(f"Opened {item.video.watch_url}")

    # ----- search --------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            query = event.value.strip()
            if query:
                self.run_search(query)

    @work(thread=True, exclusive=True, group="search")
    def run_search(self, query: str) -> None:
        self.call_from_thread(self._set_results_title, "Searching…")
        try:
            videos = search(query, limit=25)
        except SearchError as exc:
            self.call_from_thread(self.notify, str(exc), severity="error")
            self.call_from_thread(self._set_results_title, "Results")
            return
        except Exception as exc:  # pragma: no cover - defensive
            self.call_from_thread(self.notify, f"Search failed: {exc}", severity="error")
            self.call_from_thread(self._set_results_title, "Results")
            return
        self.call_from_thread(self._populate, videos)

    def _populate(self, videos: list[Video]) -> None:
        results = self.query_one("#results", ListView)
        results.clear()
        for video in videos:
            results.append(VideoItem(video))
        count = len(videos)
        self._set_results_title(f"Results ({count})")
        if count:
            results.index = 0
            results.focus()
            self._show_details(videos[0])
        else:
            self.notify("No results found.", severity="warning")

    def _set_results_title(self, title: str) -> None:
        self.query_one("#results", ListView).border_title = title

    # ----- selection / details ------------------------------------------

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, VideoItem):
            self._show_details(event.item.video)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, VideoItem):
            self._watch(event.item.video)

    def _current_item(self) -> VideoItem | None:
        item = self.query_one("#results", ListView).highlighted_child
        return item if isinstance(item, VideoItem) else None

    def _show_details(self, video: Video) -> None:
        self._current_video_id = video.id

        meta = (
            f"[b #ff8a8a]{_escape(video.title)}[/]\n\n"
            f"[#8a8a94]Channel[/]   {_escape(video.channel)}\n"
            f"[#8a8a94]Length[/]    {video.duration_str}\n"
            f"[#8a8a94]Views[/]     {video.views_str} views\n"
            f"[#8a8a94]Link[/]      [link='{video.watch_url}']{_escape(video.id)}[/link]"
        )
        self.query_one("#meta", Static).update(meta)

        desc = video.description.strip()
        if len(desc) > 1500:
            desc = desc[:1500].rstrip() + "…"
        desc_markup = _escape(desc) if desc else "No description available."
        self.query_one("#desc", Static).update(f"[#6f6f78]{desc_markup}[/]")

        # Reset to a neutral frame, then load the real thumbnail in the
        # background so fast navigation never blocks the UI.
        self.query_one("#thumb", Image).image = thumbnails.placeholder()
        self.load_thumbnail(video)

    @work(thread=True, exclusive=True, group="thumb")
    def load_thumbnail(self, video: Video) -> None:
        try:
            image = thumbnails.fetch(video.id, video.thumbnail_url)
        except Exception:
            return  # leave the placeholder in place
        self.call_from_thread(self._apply_thumbnail, video.id, image)

    def _apply_thumbnail(self, video_id: str, image) -> None:
        if video_id != self._current_video_id:
            return  # selection moved on before the download finished
        self.query_one("#thumb", Image).image = image

    # ----- playback ------------------------------------------------------

    def _watch(self, video: Video) -> None:
        if player.mpv_path() is None:
            self.notify(
                "mpv is not installed. Install mpv to watch in the terminal.",
                severity="error",
                timeout=8,
            )
            return
        vo = player.detect_vo()
        self.notify(f"Loading “{video.title}” (vo={vo})…  press q in mpv to return.")
        with self.suspend():
            print(f"\n▶  BoxTube — playing: {video.title}")
            print(f"   {video.watch_url}   [video output: {vo}]")
            print("   Controls:  q quit · space pause · ←/→ seek · 9/0 volume\n")
            try:
                player.play(video.watch_url, vo=vo)
            except Exception as exc:  # pragma: no cover - defensive
                print(f"\nPlayback error: {exc}")
                input("Press Enter to return to BoxTube… ")
        self.query_one("#results", ListView).focus()

    # ----- misc ----------------------------------------------------------

    def _welcome_text(self) -> str:
        return (
            "[b #ff8a8a]Welcome to BoxTube[/]\n\n"
            "[#a8a8b2]Search above and press [b]Enter[/b].\n"
            "Use [#ff6b6b]↑ ↓[/] to browse, [#ff6b6b]Enter[/] to watch\n"
            "in the terminal, [#ff6b6b]o[/] to open in a browser.[/]\n\n"
            "[#6f6f78]Thumbnails render via your terminal's graphics\n"
            "protocol, with a unicode fallback everywhere else.[/]"
        )


def _escape(text: str) -> str:
    """Escape Textual console-markup brackets in arbitrary text."""
    return text.replace("[", r"\[")


def main() -> None:
    BoxTube().run()


if __name__ == "__main__":
    main()
