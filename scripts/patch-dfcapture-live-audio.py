#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-dfcapture-live-audio.py <index.html>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8-sig")

# Disable DFCapture's direct installed-track playback so the browser has exactly
# one audio source: the real game mix streamed from the container.
text, removed = re.subn(
    r'\n?<script src="/js/dfcapture-audio\.js\?[^\"]+"></script>',
    "",
    text,
    count=1,
)
if removed != 1:
    raise SystemExit("could not find DFCapture audio script in index.html")

css = '<link rel="stylesheet" href="/css/dfcapture-live-audio.css?v=1">'
if css not in text:
    text = text.replace("</head>", f"{css}\n</head>", 1)

bar = '''<div id="liveAudioBar" role="region" aria-label="Dwarf Fortress live audio">
  <span class="live-audio-label" aria-hidden="true">🔊</span>
  <audio id="liveDfAudio" controls preload="none">
    <source src="/audio" type="audio/ogg; codecs=opus">
  </audio>
  <button id="liveAudioEnable" type="button" hidden>▶ Enable audio</button>
  <span id="liveAudioStatus" class="live-audio-status" aria-live="polite">Connecting…</span>
</div>'''
if 'id="liveAudioBar"' not in text:
    marker = '<div id="selection" aria-live="polite"></div>'
    if marker not in text:
        raise SystemExit("could not find DFCapture footer marker in index.html")
    text = text.replace(marker, f"{bar}\n{marker}", 1)

script = '<script src="/js/dfcapture-live-audio.js?v=1"></script>'
if script not in text:
    marker = '<script src="/js/dfcapture-session.js'
    if marker not in text:
        raise SystemExit("could not find DFCapture script marker in index.html")
    text = text.replace(marker, f'{script}\n{marker}', 1)

path.write_text(text, encoding="utf-8")
