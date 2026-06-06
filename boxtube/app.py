"""BoxTube — a TUI YouTube client built with Textual.

A YouTube-like layout: a persistent search bar on top, a Library nav on the left
(Home / History / Liked / Watch Later / Playlists), a results list in the middle,
and a preview pane on the right. Personalized feeds use a cookies file for
sign-in (see :mod:`boxtube.account`); search works signed out.
"""

from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static
from textual_image.widget import Image

from . import account, player, thumbnails, youtube
from .youtube import Playlist, SearchError, Video

# Left-nav items: (key, icon, label). All require sign-in.
NAV_ITEMS = [
    ("home", "🏠", "Home"),
    ("history", "🕘", "History"),
    ("liked", "👍", "Liked"),
    ("watch_later", "⏰", "Watch Later"),
    ("playlists", "🎵", "Playlists"),
]

SOURCE_TITLES = {
    "home": "Home — Subscriptions",
    "history": "History",
    "liked": "Liked videos",
    "watch_later": "Watch Later",
    "playlists": "Playlists",
}


class NavItem(ListItem):
    """A row in the left Library nav."""

    def __init__(self, key: str, icon: str, label: str) -> None:
        super().__init__()
        self.key = key
        self._icon = icon
        self._label = label

    def compose(self) -> ComposeResult:
        yield Label(f"{self._icon}  {self._label}")


class VideoItem(ListItem):
    """A video row in the results list."""

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


class PlaylistItem(ListItem):
    """A playlist row in the results list (drill-down)."""

    def __init__(self, playlist: Playlist) -> None:
        super().__init__()
        self.playlist = playlist

    def compose(self) -> ComposeResult:
        p = self.playlist
        yield Label(f"🎵  {p.title}", classes="title")
        yield Label(p.count_str, classes="meta")


class BoxTube(App[None]):
    """The BoxTube application."""

    CSS_PATH = "boxtube.tcss"
    TITLE = "BoxTube"

    BINDINGS = [
        Binding("ctrl+c,ctrl+q", "quit", "Quit", priority=True),
        Binding("slash", "focus_search", "Search", show=True),
        Binding("enter", "play", "Play", show=True),
        Binding("p", "play", "Play", show=False),
        Binding("o", "open_browser", "Open", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("question_mark", "help", "Sign in", show=True),
        Binding("backspace", "back", "Back", show=False),
        Binding("escape", "focus_search", "Search", show=False),
        Binding("1", "select_nav(0)", "", show=False),
        Binding("2", "select_nav(1)", "", show=False),
        Binding("3", "select_nav(2)", "", show=False),
        Binding("4", "select_nav(3)", "", show=False),
        Binding("5", "select_nav(4)", "", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._current_video_id: str | None = None
        self._current_source: str | None = None
        self._drill_playlist: Playlist | None = None
        self._last_query: str | None = None

    # ----- layout --------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="appbar"):
            yield Static("[#ff6b6b]●[/]  [b]BoxTube[/b]", id="brand", markup=True)
            yield Static("", id="auth", markup=True)
        yield Input(placeholder="Search YouTube…", id="search")
        with Horizontal(id="body"):
            with ListView(id="nav"):
                for key, icon, label in NAV_ITEMS:
                    yield NavItem(key, icon, label)
            yield ListView(id="results")
            with VerticalScroll(id="detail-pane"):
                yield Image(thumbnails.placeholder(), id="thumb")
                yield Static("", id="meta", markup=True)
                yield Static("", id="desc", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search", Input).border_title = "Search"
        self.query_one("#nav", ListView).border_title = "Library"
        self.query_one("#results", ListView).border_title = "Home"
        self.query_one("#detail-pane").border_title = "Preview"
        self._update_auth()
        self.query_one("#nav", ListView).index = 0

        if account.is_signed_in():
            self._open_source("home")
        else:
            self._show_signin_help()
            self._set_results_title("Sign in required")
            self.query_one("#search", Input).focus()

    def _update_auth(self) -> None:
        auth = self.query_one("#auth", Static)
        if account.is_signed_in():
            auth.update("[#6ee7a0]●[/] [#a8a8b2]Signed in[/]")
        else:
            auth.update("[#8a8a94]○ Signed out — press [#ff6b6b]?[/] to sign in[/]")

    # ----- navigation ----------------------------------------------------

    def action_select_nav(self, index: int) -> None:
        if 0 <= index < len(NAV_ITEMS):
            self.query_one("#nav", ListView).index = index
            self._open_source(NAV_ITEMS[index][0])

    def _open_source(self, key: str) -> None:
        self._current_source = key
        self._drill_playlist = None
        self._last_query = None
        for i, (k, _, _) in enumerate(NAV_ITEMS):
            if k == key:
                self.query_one("#nav", ListView).index = i
                break
        self.load_source(key)

    def _open_playlist(self, playlist: Playlist) -> None:
        self._drill_playlist = playlist
        self.load_playlist(playlist)

    def action_back(self) -> None:
        if self._drill_playlist is not None:
            self._open_source("playlists")

    # ----- loading (workers) ---------------------------------------------

    @work(thread=True, exclusive=True, group="source")
    def load_source(self, key: str) -> None:
        cookies = account.cookies_arg()
        if cookies is None:
            self.call_from_thread(self._require_sign_in)
            return
        self.call_from_thread(self._set_results_title, "Loading…")
        try:
            if key == "playlists":
                playlists = youtube.user_playlists(cookies=cookies)
                self.call_from_thread(self._populate_playlists, playlists, "Playlists")
                return
            videos = youtube.videos_for_feed(key, limit=40, cookies=cookies)
        except SearchError as exc:
            self.call_from_thread(self._on_load_error, str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            self.call_from_thread(self._on_load_error, str(exc))
            return
        self.call_from_thread(self._populate_videos, videos, SOURCE_TITLES.get(key, key))

    @work(thread=True, exclusive=True, group="source")
    def load_playlist(self, playlist: Playlist) -> None:
        cookies = account.cookies_arg()
        self.call_from_thread(self._set_results_title, f"Loading {playlist.title}…")
        try:
            videos = youtube.playlist_videos(playlist.id, cookies=cookies)
        except SearchError as exc:
            self.call_from_thread(self._on_load_error, str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            self.call_from_thread(self._on_load_error, str(exc))
            return
        self.call_from_thread(self._populate_videos, videos, playlist.title)

    @work(thread=True, exclusive=True, group="source")
    def run_search(self, query: str) -> None:
        cookies = account.cookies_arg()
        self.call_from_thread(self._set_results_title, "Searching…")
        try:
            videos = youtube.search(query, limit=25, cookies=cookies)
        except SearchError as exc:
            self.call_from_thread(self._on_load_error, str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            self.call_from_thread(self._on_load_error, str(exc))
            return
        self.call_from_thread(self._populate_videos, videos, f"Search: {query}")

    # ----- search --------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            query = event.value.strip()
            if query:
                self._current_source = None
                self._drill_playlist = None
                self._last_query = query
                self.run_search(query)

    # ----- populate ------------------------------------------------------

    def _populate_videos(self, videos: list[Video], title: str) -> None:
        results = self.query_one("#results", ListView)
        results.clear()
        for video in videos:
            results.append(VideoItem(video))
        if videos:
            self._set_results_title(f"{title} ({len(videos)})")
            results.index = 0
            results.focus()
            self._show_details(videos[0])
        else:
            self._set_results_title(title)
            self._show_message("Nothing to show", "This list is empty.")

    def _populate_playlists(self, playlists: list[Playlist], title: str) -> None:
        results = self.query_one("#results", ListView)
        results.clear()
        for playlist in playlists:
            results.append(PlaylistItem(playlist))
        if playlists:
            self._set_results_title(f"{title} ({len(playlists)})")
            results.index = 0
            results.focus()
            self._show_playlist_detail(playlists[0])
        else:
            self._set_results_title(title)
            self._show_message("No playlists", "You don't have any playlists yet.")

    def _set_results_title(self, title: str) -> None:
        self.query_one("#results", ListView).border_title = title

    def _on_load_error(self, message: str) -> None:
        self.query_one("#results", ListView).clear()
        self._update_auth()
        if not account.is_signed_in():
            self._set_results_title("Sign in required")
            self._show_signin_help()
        else:
            self._set_results_title("Couldn't load")
            self._show_message("Couldn't load", message)
        self.notify(message, severity="error", timeout=8)

    # ----- selection / details ------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "nav":
            self.action_select_nav(event.list_view.index or 0)
        elif isinstance(event.item, VideoItem):
            self._watch(event.item.video)
        elif isinstance(event.item, PlaylistItem):
            self._open_playlist(event.item.playlist)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "results":
            return
        if isinstance(event.item, VideoItem):
            self._show_details(event.item.video)
        elif isinstance(event.item, PlaylistItem):
            self._show_playlist_detail(event.item.playlist)

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

        self.query_one("#thumb", Image).image = thumbnails.placeholder()
        self.load_thumbnail(video)

    def _show_playlist_detail(self, playlist: Playlist) -> None:
        self._current_video_id = None
        self.query_one("#thumb", Image).image = thumbnails.placeholder()
        self.query_one("#meta", Static).update(
            f"[b #ff8a8a]{_escape(playlist.title)}[/]\n\n"
            f"[#8a8a94]Playlist[/]   {playlist.count_str}"
        )
        self.query_one("#desc", Static).update(
            "[#a8a8b2]Press [b]Enter[/b] to open · [b]Backspace[/b] to go back[/]"
        )

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

    def action_refresh(self) -> None:
        self._update_auth()
        if self._drill_playlist is not None:
            self.load_playlist(self._drill_playlist)
        elif self._current_source is not None:
            self._open_source(self._current_source)
        elif self._last_query:
            self.run_search(self._last_query)
        else:
            self.on_mount()

    def action_help(self) -> None:
        self._show_signin_help()

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
        cookies = account.cookies_arg()
        self.notify(f"Loading “{video.title}” (vo={vo})…  press q in mpv to return.")
        with self.suspend():
            print(f"\n▶  BoxTube — playing: {video.title}")
            print(f"   {video.watch_url}   [video output: {vo}]")
            print("   Controls:  q quit · space pause · ←/→ seek · 9/0 volume\n")
            try:
                player.play(video.watch_url, vo=vo, cookies=cookies)
            except Exception as exc:  # pragma: no cover - defensive
                print(f"\nPlayback error: {exc}")
                input("Press Enter to return to BoxTube… ")
        self.query_one("#results", ListView).focus()

    # ----- messages / help ----------------------------------------------

    def _require_sign_in(self) -> None:
        self.query_one("#results", ListView).clear()
        self._set_results_title("Sign in required")
        self._show_signin_help()
        self.notify("Sign in to view this. Press ? for steps.", severity="warning")

    def _show_message(self, title: str, body: str) -> None:
        self._current_video_id = None
        self.query_one("#thumb", Image).image = thumbnails.placeholder()
        self.query_one("#meta", Static).update(f"[b #ff8a8a]{_escape(title)}[/]")
        self.query_one("#desc", Static).update(f"[#a8a8b2]{_escape(body)}[/]")

    def _show_signin_help(self) -> None:
        path = account.cookies_path()
        self._current_video_id = None
        self.query_one("#thumb", Image).image = thumbnails.placeholder()
        self.query_one("#meta", Static).update(
            "[b #ff8a8a]Sign in to BoxTube[/]\n\n"
            "[#a8a8b2]BoxTube reads your YouTube cookies to show your feed,\n"
            "history, liked videos, watch later, and playlists.[/]"
        )
        self.query_one("#desc", Static).update(
            "[#a8a8b2][b]Steps[/b]\n"
            "1. In a browser logged into YouTube, install the\n"
            "   [b]Get cookies.txt LOCALLY[/b] extension.\n"
            "2. Open youtube.com and export your cookies.\n"
            "3. Save the file to:\n"
            f"   [#ff6b6b]{_escape(str(path))}[/]\n"
            "4. Press [b]r[/b] to refresh.[/]\n\n"
            "[#6f6f78]Tip: set BOXTUBE_COOKIES to use a different path.\n"
            "Search works without signing in.[/]"
        )


def _escape(text: str) -> str:
    """Escape Textual console-markup brackets in arbitrary text."""
    return text.replace("[", r"\[")


def main() -> None:
    BoxTube().run()


if __name__ == "__main__":
    main()
