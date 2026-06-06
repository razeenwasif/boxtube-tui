# Installation

This guide covers installing BoxTube, putting it on your `PATH`, verifying the
install, and platform-specific notes.

## Prerequisites

BoxTube needs two system tools and a few Python packages.

| Tool | Required | How to get it |
|------|----------|---------------|
| **Python 3.10+** | Yes | System package or [python.org](https://www.python.org/) |
| **mpv** | Yes (for playback) | `apt install mpv` / `brew install mpv` / [mpv.io](https://mpv.io/) |
| **yt-dlp** | Yes | Installed automatically into the venv by pip |

> BoxTube installs and uses its **own** `yt-dlp` inside the virtualenv rather than
> relying on a system package. YouTube changes its stream cipher often, and an
> outdated `yt-dlp` is the most common cause of broken playback. See
> [Configuration → yt-dlp resolution](configuration.md#yt-dlp-resolution).

Verify the system prerequisites:

```bash
python3 --version    # >= 3.10
mpv --version        # any recent build with kitty/sixel/tct video outputs
```

## Install

```bash
cd BoxTube

# 1. Create an isolated environment
python3 -m venv .venv

# 2. Install BoxTube + dependencies and the `boxtube` console command
.venv/bin/pip install -e .

# 3. Expose the command on your PATH
ln -sf "$PWD/.venv/bin/boxtube" ~/.local/bin/boxtube
```

`pip install -e .` performs an *editable* install: the `boxtube` command always
runs the live source in this folder (including `boxtube.tcss`), so edits take
effect without reinstalling.

Using the [`Makefile`](../Makefile) instead:

```bash
make install   # create venv + editable install
make link      # symlink into ~/.local/bin
```

## Putting `boxtube` on your PATH

The symlink target, `~/.local/bin`, is on the `PATH` of most modern Linux/macOS
shells. Confirm:

```bash
command -v boxtube        # -> ~/.local/bin/boxtube
echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin" && echo "on PATH" || echo "NOT on PATH"
```

If `~/.local/bin` is **not** on your `PATH`, add it to your shell profile:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc   # or ~/.zshrc
exec "$SHELL"
```

## Verify

```bash
boxtube      # launches the TUI; type a query and press Enter
```

You can also run it without the global command:

```bash
./boxtube.sh                  # launcher script
.venv/bin/python -m boxtube   # module form
```

## Updating

```bash
cd BoxTube
git pull                      # if tracked in git
.venv/bin/pip install -e .    # pick up dependency changes
.venv/bin/pip install -U yt-dlp   # keep playback working
```

## Uninstall

```bash
rm ~/.local/bin/boxtube       # remove the global command
rm -rf .venv                  # remove the environment
# delete the BoxTube folder to remove the rest
```

## Platform notes

### WSL (Windows Subsystem for Linux)

- Works well. Thumbnails and video render in whichever terminal you run from
  (Windows Terminal, Ghostty for WSL, etc.).
- Audio may be silent depending on your PulseAudio/WSLg setup; video still plays.

### Ghostty / kitty / WezTerm

- These support the kitty graphics protocol; BoxTube auto-selects `--vo=kitty`
  for **sharp** thumbnails and video. No configuration needed.

### Sixel terminals (foot, mlterm, xterm `-ti vt340`)

- Auto-detected as `--vo=sixel`. If detection misses your terminal, force it:
  `BOXTUBE_VO=sixel boxtube`.

### Plain terminals (xterm-256color, most defaults)

- Fall back to `--vo=tct` (truecolor text blocks). Playback works everywhere with
  24-bit color; it's blocky but functional. For crisp video, use a
  graphics-capable terminal above.

The symlink points into the venv, which uses absolute paths. If you **move or
rename** the `BoxTube` folder, recreate the venv and re-link (`make install link`).
