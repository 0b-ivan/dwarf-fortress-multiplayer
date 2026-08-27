#!/usr/bin/env python3
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch-dfcapture-live-audio.py <index.html>")

path = Path(sys.argv[1])
web_root = path.parent
controls_path = web_root / "js/dfcapture-controls-placement.js"
style_path = web_root / "css/dfcapture.css"
text = path.read_text(encoding="utf-8-sig")


def replace_once(source, old, new, label):
    if old not in source:
        raise SystemExit(f"could not find {label}")
    return source.replace(old, new, 1)


# DFCapture exposes one generic stair button even though the backend supports
# DownStair, UpDownStair and UpStair separately. Expose all three so browser
# players can designate complete stairwells on the correct tile types.
stair_button = '<button class="tool-button" data-dig-tool="stairs" title="Dig stairwell"></button>'
stair_buttons = '''<button class="tool-button stair-tool stair-tool-down" data-dig-tool="downstair" title="Dig downward stair"></button>
    <button class="tool-button stair-tool stair-tool-updown" data-dig-tool="stairs" title="Dig up/down stair"></button>
    <button class="tool-button stair-tool stair-tool-up" data-dig-tool="upstair" title="Dig upward stair"></button>'''
text = replace_once(text, stair_button, stair_buttons, "generic stair button in index.html")

# Bust caches for the upstream web assets modified below.
text, controls_version = re.subn(
    r'(<script src="/js/dfcapture-controls-placement\.js\?v=)([^"]+)("></script>)',
    lambda match: match.group(1) + match.group(2) + "-stairs2" + match.group(3),
    text,
    count=1,
)
if controls_version != 1:
    raise SystemExit("could not bump DFCapture controls script version")

text, css_version = re.subn(
    r'(<link rel="stylesheet" href="/css/dfcapture\.css\?v=)([^"]+)(">)',
    lambda match: match.group(1) + match.group(2) + "-stairs2" + match.group(3),
    text,
    count=1,
)
if css_version != 1:
    raise SystemExit("could not bump DFCapture stylesheet version")

controls = controls_path.read_text(encoding="utf-8-sig")
controls = replace_once(
    controls,
    '    stairs:{normal:[8,22], active:[12,22]},',
    '''    downstair:{normal:[8,22], active:[12,22]},
    stairs:{normal:[8,22], active:[12,22]},
    upstair:{normal:[8,22], active:[12,22]},''',
    "stairs sprite mapping",
)
controls = replace_once(
    controls,
    '  const digTools = new Set(["dig", "stairs", "ramp", "channel", "remove"]);',
    '  const digTools = new Set(["dig", "downstair", "stairs", "upstair", "ramp", "channel", "remove"]);',
    "dig tool set",
)
controls = replace_once(
    controls,
    '    return ({ dig:"dig", stairs:"stairs", ramp:"ramp", channel:"channel", remove:"clear",',
    '''    return ({ dig:"dig", downstair:"downstair", stairs:"stairs", upstair:"upstair",
              ramp:"ramp", channel:"channel", remove:"clear",''',
    "backend stair tool mapping",
)
controls_path.write_text(controls, encoding="utf-8")

styles = style_path.read_text(encoding="utf-8-sig")
stair_styles = '''
/* Distinguish the three stair designation modes while reusing DF's stair sprite. */
#digSubmenu .stair-tool { position: relative; }
#digSubmenu .stair-tool::after {
  position: absolute;
  right: 1px;
  bottom: 1px;
  min-width: 9px;
  padding: 1px 2px;
  border: 1px solid #8a6a28;
  background: rgba(0, 0, 0, 0.86);
  color: #fff3b0;
  font: 700 8px/1 ui-monospace, monospace;
  text-align: center;
  pointer-events: none;
}
#digSubmenu .stair-tool-down::after { content: "D"; }
#digSubmenu .stair-tool-updown::after { content: "UD"; }
#digSubmenu .stair-tool-up::after { content: "U"; }
'''
if "#digSubmenu .stair-tool-down::after" not in styles:
    styles += stair_styles
style_path.write_text(styles, encoding="utf-8")

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

# v=2 also invalidates the old CSS that moved only #bottomBar and accidentally
# left its submenus behind the toolbar.
css = '<link rel="stylesheet" href="/css/dfcapture-live-audio.css?v=2">'
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

for expected in (
    'data-dig-tool="downstair"',
    'data-dig-tool="stairs"',
    'data-dig-tool="upstair"',
    'downstair:"downstair"',
    'stairs:"stairs"',
    'upstair:"upstair"',
):
    haystack = text if expected.startswith("data-") else controls
    if expected not in haystack:
        raise SystemExit(f"stair patch verification failed: {expected}")

path.write_text(text, encoding="utf-8")
