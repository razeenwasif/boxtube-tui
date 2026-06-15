"""Modal Comments screen — a video's top comments, loaded via yt-dlp.

Comment extraction is slow (yt-dlp loads the full watch page), so the screen
opens immediately with a loading line and a background worker fills it in. It's a
flat list of top-level comments (no reply threads), ordered like YouTube's "Top
comments".
"""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from . import youtube
from .youtube import Comment, SearchError, Video


class CommentRow(Vertical):
    """One comment: a meta line (author · time · likes) above the body text."""

    def __init__(self, comment: Comment) -> None:
        super().__init__(classes="comment-row")
        self.comment = comment

    def compose(self) -> ComposeResult:
        c = self.comment
        author = f"[b #e8e8ea]{_esc(c.author)}[/]"
        if c.is_uploader:
            author += " [#ff6b6b]· creator[/]"
        bits = [author]
        if c.time_text:
            bits.append(f"[#6f6f78]{_esc(c.time_text)}[/]")
        if c.likes_str:
            heart = " ♥" if c.is_favorited else ""
            bits.append(f"[#8a8a94]👍 {c.likes_str}{heart}[/]")
        yield Static("  ·  ".join(bits), classes="comment-meta", markup=True)
        yield Static(f"[#cccccc]{_esc(c.text)}[/]", classes="comment-text", markup=True)


class CommentsScreen(ModalScreen):
    """A centered dialog listing a video's top comments."""

    BINDINGS = [Binding("escape,q,c", "close", "Close", show=True)]

    def __init__(self, video: Video) -> None:
        super().__init__()
        self.video = video

    def compose(self) -> ComposeResult:
        with Vertical(id="comments-dialog"):
            yield Static(f"💬  Comments — [b]{_esc(self.video.title)}[/]",
                         id="comments-title", markup=True)
            with VerticalScroll(id="comments-body"):
                yield Static("[#8a8a94]Loading comments…[/]", id="comments-status",
                             markup=True)
            yield Static("[#6f6f78]Esc / q / c to close[/]", id="comments-foot",
                         markup=True)

    def on_mount(self) -> None:
        self._load()

    @work(thread=True, exclusive=True, group="comments")
    def _load(self) -> None:
        try:
            comments = youtube.fetch_comments(self.video.id)
        except SearchError as exc:
            self.app.call_from_thread(self._show_error, str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            self.app.call_from_thread(self._show_error, str(exc))
            return
        self.app.call_from_thread(self._show_comments, comments)

    def _show_comments(self, comments: list[Comment]) -> None:
        body = self.query_one("#comments-body", VerticalScroll)
        body.remove_children()
        if not comments:
            body.mount(Static("[#8a8a94]No comments to show — they may be turned "
                              "off for this video.[/]", classes="comment-empty",
                              markup=True))
            return
        self.query_one("#comments-title", Static).update(
            f"💬  Comments ({len(comments)}) — [b]{_esc(self.video.title)}[/]"
        )
        body.mount(*[CommentRow(c) for c in comments])

    def _show_error(self, message: str) -> None:
        body = self.query_one("#comments-body", VerticalScroll)
        body.remove_children()
        body.mount(Static(
            f"[#ff8a8a]Couldn't load comments.[/]\n[#8a8a94]{_esc(message)}[/]",
            classes="comment-empty", markup=True,
        ))

    def action_close(self) -> None:
        self.dismiss(None)


def _esc(text: str) -> str:
    return text.replace("[", r"\[")
