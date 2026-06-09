"""BoxTube — a TUI YouTube client built with Textual.

A YouTube-styled layout: a header with a centered search bar, a row of filter
chips, a left sidebar (Home / History / Playlists / Watch Later / Liked, plus your
subscribed channels), a **thumbnail grid** of videos, and a preview pane with the
highlighted video's details. Personalized feeds use a cookies file for sign-in
(see :mod:`boxtube.account`); search works signed out.
"""

from __future__ import annotations

import os
import time

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, HorizontalScroll, Vertical, VerticalScroll
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

# Filter chips under the header. "All" returns to Home, "Shorts" loads the
# Shorts feed; the rest run a search.
CHIPS = ["All", "Shorts", "Music", "Gaming", "News", "Live", "Podcasts", "Learning", "Sports", "Comedy", "Mixes"]

# Sources that require a valid signed-in session.
FEED_KEYS = {"home", "history", "liked", "watch_later", "playlists"}

# Substrings in a yt-dlp error that indicate the cookies aren't authenticating.
_AUTH_HINTS = ("does not exist", "sign in", "log in", "login", "private", "cookie",
               "members-only", "unavailable", "not available on this app")

# Grid sizing: target card width (cols) used to compute the column count.
CARD_WIDTH = 24
GRID_GUTTER = 2


class CardSelected(Message):
    """Posted when a grid card gains focus (→ update the preview)."""

    def __init__(self, card: "Card") -> None:
        super().__init__()
        self.card = card


class CardActivated(Message):
    """Posted when a grid card is double-clicked (→ play / open)."""

    def __init__(self, card: "Card") -> None:
        super().__init__()
        self.card = card


class Card(Vertical):
    """A focusable grid cell. Subclasses hold a Video or Playlist as ``item``."""

    can_focus = True

    def __init__(self, item) -> None:
        super().__init__(classes="card")
        self.item = item

    def on_focus(self) -> None:
        self.add_class("-sel")
        self.post_message(CardSelected(self))

    def on_blur(self) -> None:
        self.remove_class("-sel")

    def on_click(self, event) -> None:
        if getattr(event, "chain", 1) >= 2:  # double-click activates
            self.post_message(CardActivated(self))


class VideoCard(Card):
    """A video tile: thumbnail + title + channel/meta."""

    def __init__(self, video: Video) -> None:
        super().__init__(video)
        self.video = video

    def compose(self) -> ComposeResult:
        v = self.video
        yield Image(thumbnails.placeholder(), classes="card-thumb")
        yield Label(v.title, classes="card-title")
        # Duration now rides as a badge on the thumbnail (YouTube-style), so the
        # meta line is just channel · views.
        yield Label(f"{v.channel} · {v.views_str} views", classes="card-meta")

    def set_thumb(self, image) -> None:
        self.query_one(".card-thumb", Image).image = image


class PlaylistCard(Card):
    """A playlist tile (drill-down)."""

    def __init__(self, playlist: Playlist) -> None:
        super().__init__(playlist)
        self.playlist = playlist

    def compose(self) -> ComposeResult:
        p = self.playlist
        yield Static("🎵", classes="card-thumb card-thumb-icon")
        yield Label(p.title, classes="card-title")
        yield Label(p.count_str, classes="card-meta")


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
        Binding("up", "grid_move('up')", "", show=False),
        Binding("down", "grid_move('down')", "", show=False),
        Binding("left", "grid_move('left')", "", show=False),
        Binding("right", "grid_move('right')", "", show=False),
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
        self._shorts_active: bool = False
        self._cards: list[Card] = []
        self._cols: int = 1
        self._focused_item = None
        self._thumbs_loaded: set[str] = set()
        self._thumb_timer = None

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
            with VerticalScroll(id="grid"):
                yield Grid(id="grid-inner")
            with VerticalScroll(id="detail-pane"):
                yield Image(thumbnails.placeholder(), id="thumb")
                yield Static("", id="meta", markup=True)
                yield Static("", id="desc", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#grid").border_title = "Home"
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

    def on_resize(self, event) -> None:
        if self._cards:
            cols = self._compute_cols()
            if cols != self._cols:
                self._cols = cols
                self.query_one("#grid-inner", Grid).styles.grid_size_columns = cols
            self._request_thumb_scan()  # reflow reveals different cards

    # ----- chips ---------------------------------------------------------

    def on_chip_selected(self, event: Chip.Selected) -> None:
        self._set_active_chip(event.label)
        if event.label == "All":
            self._open_source("home")
        elif event.label == "Shorts":
            self._current_source = None
            self._drill_playlist = None
            self._drill_channel = None
            self._last_query = None
            self._shorts_active = True
            self.run_shorts()
        else:
            self._current_source = None
            self._drill_playlist = None
            self._drill_channel = None
            self._last_query = event.label
            self._shorts_active = False
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
        self._shorts_active = False
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

    # ----- grid navigation ----------------------------------------------

    def action_grid_move(self, direction: str) -> None:
        cards = self._cards
        if not cards:
            return
        current = self.focused
        if current not in cards:
            cards[0].focus()
            return
        idx = cards.index(current)
        cols = max(1, self._cols)
        target = {
            "left": idx - 1,
            "right": idx + 1,
            "up": idx - cols,
            "down": idx + cols,
        }[direction]
        if 0 <= target < len(cards):
            cards[target].focus()
            cards[target].scroll_visible()
            self._request_thumb_scan()  # newly-revealed cards

    def _request_thumb_scan(self) -> None:
        """Debounce: scan for visible thumbnails shortly after scrolling stops,
        so rapid wheel/arrow scrolling doesn't restart the loader repeatedly."""
        if self._thumb_timer is not None:
            self._thumb_timer.stop()
        self._thumb_timer = self.set_timer(0.12, self._load_visible_thumbnails)

    def on_mouse_scroll_down(self, event) -> None:
        self._request_thumb_scan()

    def on_mouse_scroll_up(self, event) -> None:
        self._request_thumb_scan()

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
    def run_shorts(self) -> None:
        cookies = account.cookies_arg()
        self.call_from_thread(self._set_results_title, "Loading Shorts…")
        try:
            videos = youtube.shorts_feed(limit=40, cookies=cookies)
        except SearchError as exc:
            self.call_from_thread(self._on_load_error, str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            self.call_from_thread(self._on_load_error, str(exc))
            return
        self.call_from_thread(self._populate_videos, videos, "Shorts")

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

    def _visible_unloaded_cards(self) -> list[VideoCard]:
        """Video cards whose thumbnail isn't loaded yet and that are on (or near)
        screen — within one viewport above/below for light pre-loading."""
        try:
            viewport = self.query_one("#grid").region
        except Exception:
            return []
        if not viewport.height:
            return []
        # Strictly visible plus a small buffer below the fold (preload the next
        # few rows). Document order means visible cards load first.
        top = viewport.y - 2
        bottom = viewport.bottom + 8
        cards: list[VideoCard] = []
        for card in self._cards:
            if not isinstance(card, VideoCard) or card.item.id in self._thumbs_loaded:
                continue
            r = card.region
            if r.height and r.bottom > top and r.y < bottom:
                cards.append(card)
        return cards

    def _grid_layout_ready(self) -> bool:
        return bool(self._cards) and self._cards[0].region.height > 0

    @work(thread=True, exclusive=True, group="grid-thumbs")
    def _load_visible_thumbnails(self) -> None:
        # Only fetch/render thumbnails for cards in view (re-scanning so scrolling
        # mid-load picks up newly-revealed cards). Avoids loading dozens of
        # off-screen images up front. Wait for layout so card regions are known.
        waits = 0
        while not self.call_from_thread(self._grid_layout_ready):
            if waits >= 20:
                return
            waits += 1
            time.sleep(0.05)
        while True:
            cards = self.call_from_thread(self._visible_unloaded_cards)
            if not cards:
                return
            for card in cards:
                video = card.item
                try:
                    image = thumbnails.fetch(video.id, video.thumbnail_url)
                except Exception:
                    self._thumbs_loaded.add(video.id)  # don't retry a hard failure
                    continue
                self._thumbs_loaded.add(video.id)
                # Pre-resize + bake the duration badge off the UI thread so each
                # card re-render is cheaper.
                thumb = thumbnails.with_duration_badge(
                    thumbnails.for_card(image), video.duration_str
                )
                self.call_from_thread(self._apply_card_thumb, card, thumb)

    def _apply_card_thumb(self, card: VideoCard, image) -> None:
        try:
            card.set_thumb(image)
        except Exception:
            pass  # card may have been replaced by a newer load

    # ----- search --------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            query = event.value.strip()
            if query:
                self._current_source = None
                self._drill_playlist = None
                self._drill_channel = None
                self._last_query = query
                self._shorts_active = False
                self._set_active_chip("")
                self.run_search(query)

    # ----- populate ------------------------------------------------------

    def _compute_cols(self) -> int:
        width = self.query_one("#grid").content_size.width or 70
        return max(1, (width + GRID_GUTTER) // (CARD_WIDTH + GRID_GUTTER))

    def _populate_videos(self, videos: list[Video], title: str) -> None:
        self._show_grid([VideoCard(v) for v in videos], title, video_feed=True)

    def _populate_playlists(self, playlists: list[Playlist], title: str) -> None:
        self._show_grid([PlaylistCard(p) for p in playlists], title, video_feed=False)

    def _populate_channels(self, channels: list[Channel]) -> None:
        subs = self.query_one("#subs", ListView)
        subs.clear()
        for channel in channels:
            subs.append(ChannelItem(channel))

    def _show_grid(self, cards: list[Card], title: str, video_feed: bool) -> None:
        grid = self.query_one("#grid-inner", Grid)
        grid.remove_children()
        self._cards = cards
        self._focused_item = None
        self._thumbs_loaded = set()
        if cards:
            grid.mount(*cards)
            self._set_results_title(f"{title} ({len(cards)})")
            self.call_after_refresh(self._finalize_grid)
        else:
            self._set_results_title(title)
            if account.is_signed_in() and video_feed and self._current_source in FEED_KEYS:
                self._show_cookie_trouble("This feed came back empty.")
            else:
                self._show_message("Nothing to show", "This list is empty.")

    def _finalize_grid(self) -> None:
        if not self._cards:
            return
        self._cols = self._compute_cols()
        self.query_one("#grid-inner", Grid).styles.grid_size_columns = self._cols
        self._cards[0].focus()
        self._load_visible_thumbnails()

    def _set_results_title(self, title: str) -> None:
        self.query_one("#grid").border_title = title

    def _on_load_error(self, message: str) -> None:
        self.query_one("#grid-inner", Grid).remove_children()
        self._cards = []
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

    # ----- card selection / details -------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = event.list_view.id
        if lv == "nav":
            self.action_select_nav(event.list_view.index or 0)
        elif lv == "subs" and isinstance(event.item, ChannelItem):
            self._open_channel(event.item.channel)

    def on_card_selected(self, event: CardSelected) -> None:
        self._focused_item = event.card.item
        if isinstance(event.card, VideoCard):
            self._show_details(event.card.item)
        elif isinstance(event.card, PlaylistCard):
            self._show_playlist_detail(event.card.item)

    def on_card_activated(self, event: CardActivated) -> None:
        self._activate(event.card.item)

    def _activate(self, item) -> None:
        if isinstance(item, Video):
            self._watch(item)
        elif isinstance(item, Playlist):
            self._open_playlist(item)

    def _show_details(self, video: Video) -> None:
        self._current_video_id = video.id
        meta = (
            f"[b #f1f1f1]{_escape(video.title)}[/]\n\n"
            f"[#aaaaaa]{_escape(video.channel)}[/]\n"
            f"[#aaaaaa]{video.views_str} views · {video.duration_str}[/]\n\n"
            f"[link='{video.watch_url}'][#3ea6ff]{_escape(video.watch_url)}[/][/]\n"
            f"[#6f6f78]Enter to play · o to open in browser[/]"
        )
        self.query_one("#meta", Static).update(meta)

        desc = video.description.strip()
        if len(desc) > 1500:
            desc = desc[:1500].rstrip() + "…"
        desc_markup = _escape(desc) if desc else "No description available."
        self.query_one("#desc", Static).update(f"[#cccccc]{desc_markup}[/]")

        self.query_one("#thumb", Image).image = thumbnails.placeholder()
        self.load_thumbnail(video)

    def _show_playlist_detail(self, playlist: Playlist) -> None:
        self._current_video_id = None
        self.query_one("#thumb", Image).image = thumbnails.placeholder()
        self.query_one("#meta", Static).update(
            f"[b #f1f1f1]{_escape(playlist.title)}[/]\n\n"
            f"[#aaaaaa]Playlist · {playlist.count_str}[/]"
        )
        self.query_one("#desc", Static).update(
            "[#cccccc]Press [b]Enter[/b] to open · [b]Backspace[/b] to go back[/]"
        )

    @work(thread=True, exclusive=True, group="thumb")
    def load_thumbnail(self, video: Video) -> None:
        try:
            image = thumbnails.fetch(video.id, video.thumbnail_url)
        except Exception:
            return  # leave the placeholder in place
        image = thumbnails.with_duration_badge(image, video.duration_str)
        self.call_from_thread(self._apply_thumbnail, video.id, image)

    def _apply_thumbnail(self, video_id: str, image) -> None:
        if video_id != self._current_video_id:
            return  # selection moved on before the download finished
        self.query_one("#thumb", Image).image = image

    # ----- actions -------------------------------------------------------

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_play(self) -> None:
        if self._focused_item is None:
            self.notify("Highlight a video first.", severity="warning")
            return
        self._activate(self._focused_item)

    def action_open_browser(self) -> None:
        item = self._focused_item
        if not isinstance(item, Video):
            self.notify("Highlight a video first.", severity="warning")
            return
        if opener.open_url(item.watch_url):
            self.notify(f"Opened {item.watch_url}")
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
        elif self._shorts_active:
            self.run_shorts()
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
        # Hand the player the whole feed so it can move to the next clip (n / b);
        # Shorts roll into the next one automatically when one ends.
        playlist = [c.item for c in self._cards if isinstance(c, VideoCard)]
        index = next((i for i, v in enumerate(playlist) if v is video), 0)
        if not playlist:
            playlist, index = [video], 0
        self.push_screen(PlayerScreen(
            video, cookies=cookies, playlist=playlist, index=index, autoplay=self._shorts_active,
        ))

    # ----- messages / help ----------------------------------------------

    def _require_sign_in(self) -> None:
        self.query_one("#grid-inner", Grid).remove_children()
        self._cards = []
        self._set_results_title("Sign in required")
        self._show_signin_help()
        self.notify("Sign in to view this. Press ? for steps.", severity="warning")

    def _show_message(self, title: str, body: str) -> None:
        self._current_video_id = None
        self.query_one("#thumb", Image).image = thumbnails.placeholder()
        self.query_one("#meta", Static).update(f"[b #f1f1f1]{_escape(title)}[/]")
        self.query_one("#desc", Static).update(f"[#aaaaaa]{_escape(body)}[/]")

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
