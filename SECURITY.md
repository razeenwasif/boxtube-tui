# Security Policy

## Supported versions

BoxTube is pre-1.0 software. Security fixes are applied to the latest released
version only.

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ |
| < 0.1   | ❌ |

## Reporting a vulnerability

Please report security vulnerabilities **privately** by emailing
**razeen.wasif66@gmail.com** with the subject line `BoxTube security`.

Include, where possible:

- A description of the vulnerability and its impact
- Steps to reproduce or a proof of concept
- Affected version(s) and environment (OS, terminal, mpv/yt-dlp versions)

Please do **not** open a public issue for security problems. We aim to
acknowledge reports within a few days and to provide a remediation timeline after
triage.

## Security model & considerations

BoxTube is a local, single-user desktop application. It has no server component
and collects no telemetry. Nonetheless, contributors and operators should be
aware of the following trust boundaries:

- **External binaries.** BoxTube executes `yt-dlp` and `mpv` as subprocesses.
  Command arguments are constructed in `boxtube/player.py` and
  `boxtube/youtube.py`. Arguments are passed as argv list elements (never via a
  shell), which avoids shell-injection; review changes to these modules
  carefully.
- **Untrusted remote content.** Search results, stream URLs, and thumbnail images
  originate from YouTube and are processed by `yt-dlp`, `mpv`, and Pillow. Keep
  these dependencies up to date — most real-world risk lives in the media stack,
  not in BoxTube itself.
- **Network access.** BoxTube makes outbound HTTPS requests to YouTube (search,
  streams) and `i.ytimg.com` (thumbnails). It opens no inbound ports.
- **Browser handoff.** The "open in browser" action passes a
  `https://www.youtube.com/watch?v=<id>` URL to the system browser via Python's
  `webbrowser` module.

## Keeping dependencies current

YouTube changes its stream cipher frequently; an outdated `yt-dlp` is the most
common cause of broken playback and the place security fixes land most often:

```bash
.venv/bin/pip install -U yt-dlp
```
