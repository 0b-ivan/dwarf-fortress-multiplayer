#!/usr/bin/env python3
"""Fix top-level stockpile category disabling in the pinned Lua companion."""
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8-sig")
old = "    local lib = STOCKPILE_PRESETS[preset] or preset\n"
new = """    -- import_settings(disable) changes item masks but leaves the category enabled.
    -- Native DF disables the category flag, preserving its per-item preferences.
    if mode == 'disable' then
        local flags = {food='food', stone='stone', wood='wood',
            furniture='furniture', finished='finished_goods', bars='bars_blocks',
            gems='gems', cloth='cloth', leather='leather', ammo='ammo',
            armor='armor', weapons='weapons', animals='animals',
            corpses='corpses', refuse='refuse', coins='coins', sheets='sheet'}
        local flag = flags[preset]
        if flag then
            b.settings.flags[flag] = false
            return true, ''
        end
    end
""" + old
if text.count(old) != 2:
    raise SystemExit("Unexpected stockpile/hauling preset source; review patch")
# The first occurrence is stockpile_set_preset; hauling has its own settings object.
path.write_text(text.replace(old, new, 1), encoding="utf-8")
