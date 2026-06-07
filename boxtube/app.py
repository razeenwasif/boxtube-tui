"""BoxTube — a TUI YouTube client built with Textual.

A YouTube-styled layout: a header with a centered search bar, a row of filter
chips, a left sidebar (Home / History / Playlists / Watch Later / Liked, plus your
subscribed channels), a results list, and a preview pane. Personalized feeds use a
cookies file for sign-in (see :mod:`boxtube.account`); search works signed out.
"""

from __future__ import annotations

import os

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, HorizontalScroll, VerticalScroll
from textual.message import Message
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static
from textual_image.widget import Image

from . import account, opener, player, thumbnails, youtube
from .player_screen import PlayerScreen
from .youtube import Channel, Playlist, SearchError, Video

# Left-nav items: (key, icon, label). All require sign-in.
NAV_ITEMS = [
    ("home", "🏠", "Home"),
    ("history", "🕘", "History"),
    ("playlists", "🎵", "Playlists"),
    ("watch_later", "⏰", "Watch Later"),
    ("liked", "👍", "Liked"),
]

SOURCE_TITLES = {
    "home": "Home — Subscriptions",
    "history": "History",
    "liked": "Liked videos",
    "watch_later": "Watch Later",
    "playlists": "Playlists",
}

# Filter chips under the header. "All" returns to Home; the rest run a search.
CHIPS = ["All", "Music", "Gaming", "News", "Live", "Podcasts", "Learning", "Sports", "Comedy", "Mixes"]

# Sources that require a valid signed-in session.
FEED_KEYS = {"home", "history", "liked", "watch_later", "playlists"}

# Substrings in a yt-dlp error that indicate the cookies aren't authenticating.
_AUTH_HINTS = ("does not exist", "sign in", "log in", "login", "private", "cookie",
               "members-only", "unavailable", "not available on this app")


class Chip(Static):
    """A clickable filter pill in the chips row."""

    class Selected(Message):
        def __init__(self, label: str) -> None:
            super().__init__()
            self.label = label

    def __init__(self, label: str) -> None:
        super().__init__(label, classes="chip")
        self.label = label

    def on_click(self) -> None:
        self.post_message(self.Selected(self.label))


class NavItem(ListItem):
    """A row in the left sidebar nav."""

    def __init__(self, key: str, icon: str, label: str) -> None:
        super().__init__()
        self.key = key
        self._icon = icon
        self._label = label

    def compose(self) -> ComposeResult:
        yield Label(f"{self._icon}  {self._label}")


class ChannelItem(ListItem):
    """A subscribed channel row (drill-down to its videos)."""

    def __init__(self, channel: Channel) -> None:
        super().__init__()
        self.channel = channel

    def compose(self) -> ComposeResult:
        yield Label(f"[#ff6b6b]◍[/]  {_escape(self.channel.name)}", markup=True, classes="channel")


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
        self._drill_channel: Channel | None = None
        self._last_query: str | None = None

    # ----- layout --------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="appbar"):
            yield Static("[#ff3b3b]▶[/]  [b]BoxTube[/b]", id="brand", markup=True)
            with Horizontal(id="search-wrap"):
                yield Input(placeholder="Search", id="search")
            yield Static("", id="auth", markup=True)
        with HorizontalScroll(id="chips"):
            for label in CHIPS:
                yield Chip(label)
        with Horizontal(id="body"):
            with VerticalScroll(id="sidebar"):
                yield Static("You", classes="nav-section")
                with ListView(id="nav"):
                    for key, icon, label in NAV_ITEMS:
                        yield NavItem(key, icon, label)
                yield Static("Subscriptions", classes="nav-section")
                yield ListView(id="subs")
            yield ListView(id="results")
            with VerticalScroll(id="detail-pane"):
                yield Image(thumbnails.placeholder(), id="thumb")
                yield Static("", id="meta", markup=True)
                yield Static("", id="desc", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#results", ListView).border_title = "Home"
        self.query_one("#detail-pane").border_title = "Preview"
        self._update_auth()
        self.query_one("#nav", ListView).index = 0
        self._set_active_chip("All")

        if account.is_signed_in():
            self.load_channels()
            self._open_source("home")
        else:
            self._show_signin_help()
            self._set_results_title("Sign in required")
            self.query_one("#search", Input).focus()

    def _update_auth(self) -> None:
        auth = self.query_one("#auth", Static)
        if account.is_signed_in():
            auth.update("[#6ee7a0]◉[/] [#e8e8ea]You[/]")
        else:
            auth.update("[#8a8a94]○ Sign in[/] [#ff6b6b](?)[/]")

    # ----- chips ---------------------------------------------------------

    def on_chip_selected(self, event: Chip.Selected) -> None:
        self._set_active_chip(event.label)
        if event.label == "All":
            self._open_source("home")
        else:
            self._current_source = None
            self._drill_playlist = None
            self._drill_channel = None
            self._last_query = event.label
            self.run_search(event.label)

    def _set_active_chip(self, label: str) -> None:
        for chip in self.query(Chip):
            chip.set_class(chip.label == label, "-active")

    # ----- navigation ----------------------------------------------------

    def action_select_nav(self, index: int) -> None:
        if 0 <= index < len(NAV_ITEMS):
            self.query_one("#nav", ListView).index = index
            self._open_source(NAV_ITEMS[index][0])

    def _open_source(self, key: str) -> None:
        self._current_source = key
        self._drill_playlist = None
        self._drill_channel = None
        self._last_query = None
        self._set_active_chip("All" if key == "home" else "")
        for i, (k, _, _) in enumerate(NAV_ITEMS):
            if k == key:
                self.query_one("#nav", ListView).index = i
                break
        self.load_source(key)

    def _open_playlist(self, playlist: Playlist) -> None:
        self._drill_playlist = playlist
        self._drill_channel = None
        self.load_playlist(playlist)

    def _open_channel(self, channel: Channel) -> None:
        self._drill_channel = channel
        self._drill_playlist = None
        self.load_channel(channel)

    def action_back(self) -> None:
        if self._drill_playlist is not None:
            self._open_source("playlists")
        elif self._drill_channel is not None:
            self._open_source(self._current_source or "home")

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
    def load_channel(self, channel: Channel) -> None:
        cookies = account.cookies_arg()
        self.call_from_thread(self._set_results_title, f"Loading {channel.name}…")
        try:
            videos = youtube.channel_videos(channel.id, cookies=cookies)
        except SearchError as exc:
            self.call_from_thread(self._on_load_error, str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            self.call_from_thread(self._on_load_error, str(exc))
            return
        self.call_from_thread(self._populate_videos, videos, channel.name)

    @work(thread=True, exclusive=True, group="channels")
    def load_channels(self) -> None:
        cookies = account.cookies_arg()
        if cookies is None:
            return
        try:
            channels = youtube.subscribed_channels(cookies=cookies)
        except Exception:
            return
        self.call_from_thread(self._populate_channels, channels)

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
                self._drill_channel = None
                self._last_query = query
                self._set_active_chip("")
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
            if account.is_signed_in() and self._current_source in FEED_KEYS:
                # Signed in but a feed came back empty — almost always bad cookies.
                self._show_cookie_trouble("This feed came back empty.")
            else:
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

    def _populate_channels(self, channels: list[Channel]) -> None:
        subs = self.query_one("#subs", ListView)
        subs.clear()
        for channel in channels:
            subs.append(ChannelItem(channel))

    def _set_results_title(self, title: str) -> None:
        self.query_one("#results", ListView).border_title = title

    def _on_load_error(self, message: str) -> None:
        self.query_one("#results", ListView).clear()
        self._update_auth()
        if not account.is_signed_in():
            self._set_results_title("Sign in required")
            self._show_signin_help()
        elif any(hint in message.lower() for hint in _AUTH_HINTS):
            # Signed in, but YouTube rejected the request — stale/incomplete cookies.
            self._set_results_title("Sign-in problem")
            self._show_cookie_trouble(message)
        else:
            self._set_results_title("Couldn't load")
            self._show_message("Couldn't load", message)
        self.notify(message, severity="error", timeout=8)

    # ----- selection / details ------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = event.list_view.id
        if lv == "nav":
            self.action_select_nav(event.list_view.index or 0)
        elif lv == "subs" and isinstance(event.item, ChannelItem):
            self._open_channel(event.item.channel)
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
        if opener.open_url(item.video.watch_url):
            self.notify(f"Opened {item.video.watch_url}")
        else:
            self.notify("Couldn't find a browser to open the link.", severity="error")

    def action_refresh(self) -> None:
        self._update_auth()
        if account.is_signed_in():
            self.load_channels()
        if self._drill_playlist is not None:
            self.load_playlist(self._drill_playlist)
        elif self._drill_channel is not None:
            self.load_channel(self._drill_channel)
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
        # Cookies break extraction (they disable the JS-free clients), so don't
        # send them by default. Age-restricted videos already play cookie-free.
        # Opt in with BOXTUBE_PLAYBACK_COOKIES=1 for private/members-only videos.
        cookies = account.cookies_arg() if os.environ.get("BOXTUBE_PLAYBACK_COOKIES") else None
        self.push_screen(PlayerScreen(video, cookies=cookies))

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

    def _show_cookie_trouble(self, detail: str = "") -> None:
        path = account.cookies_path()
        self._current_video_id = None
        self.query_one("#thumb", Image).image = thumbnails.placeholder()
        self.query_one("#meta", Static).update(
            "[b #ff8a8a]Your sign-in isn't working[/]\n\n"
            + (f"[#8a8a94]{_escape(detail)}[/]\n\n" if detail else "")
            + "[#a8a8b2]YouTube didn't accept your cookies, so your feeds look\n"
            "empty. This usually means they're expired or incomplete.[/]"
        )
        self.query_one("#desc", Static).update(
            "[#a8a8b2][b]Fix: re-export your cookies[/b]\n"
            "1. Open a [b]private / incognito[/b] window and log into YouTube.\n"
            "2. In a new tab on youtube.com, export with\n"
            "   [b]Get cookies.txt LOCALLY[/b].\n"
            "3. [b]Close the private window[/b] right after exporting.\n"
            f"4. Replace [#ff6b6b]{_escape(str(path))}[/]\n"
            "5. Press [b]r[/b] to refresh.[/]\n\n"
            "[#6f6f78]The incognito-then-close step matters: cookies from a\n"
            "browser you keep using are often rotated and invalidated.[/]"
        )

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
