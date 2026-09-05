#!/usr/bin/env python3
"""Enable the typed viewport-buffer zoom guard for native Linux capture."""
from pathlib import Path
import sys

path = Path(sys.argv[1]) / 'src/sdl_capture.cpp'
text = path.read_text(encoding='utf-8-sig')


def replace(old, new):
    global text
    if text.count(old) != 1:
        raise SystemExit('Unexpected zoom source fragment: ' + old[:100])
    text = text.replace(old, new, 1)


replace('''void capture_zoom_reference_if_needed() {
#ifdef _WIN32
    if (g_ref_dim_x.load() > 0)
        return;
#endif''', '''void capture_zoom_reference_if_needed() {
    if (g_ref_dim_x.load() > 0)
        return;''')
replace('''bool per_player_zoom_active(const Camera& camera) {
#ifdef _WIN32
    (void)camera;
    return !g_zoom_unsafe.load() && g_ref_dim_x.load() > 0;
#else
    (void)camera;
    return false;
#endif
}''', '''bool per_player_zoom_active(const Camera& camera) {
    (void)camera;
    return !g_zoom_unsafe.load() && g_ref_dim_x.load() > 0;
}''')
replace('''#ifdef _WIN32
struct ViewportPointerField {''', '''#ifndef _WIN32
// Use DFHack's generated Linux virtual-method layout, never Windows offsets.
static bool call_set_viewport_zoom_factor_seh(df::renderer* renderer, int32_t factor) {
    if (!renderer) return false;
    renderer->set_viewport_zoom_factor(factor);
    return true;
}
#endif

struct ViewportPointerField {''')
replace('''    std::vector<SavedViewportState> saved_;
};
#endif''', '''    std::vector<SavedViewportState> saved_;
};''')
replace('''#ifdef _WIN32
    capture_zoom_reference_if_needed();
    ViewportZoomGuard zoom_guard;''', '''    capture_zoom_reference_if_needed();
    ViewportZoomGuard zoom_guard;''')
replace('''    }
#endif

    std::string map_err;''', '''    }

    std::string map_err;''')
replace('''    if (zoom_guard.active())
        zoom_guard.restore();
#endif''', '''#endif
    if (zoom_guard.active())
        zoom_guard.restore();''')
path.write_text(text, encoding='utf-8')

# Hot reload can initialize before DFHack has restored its world-loaded cache.
# Re-arm the barrier and release only after normal core updates confirm readiness.
root = Path(sys.argv[1])
p = root / 'src/save_barrier.h'
p.write_text(p.read_text() + '\nnamespace dfcapture { void save_barrier_initialize(); }\n')
p = root / 'src/save_barrier.cpp'
s = p.read_text().replace('#include "DataDefs.h"', '#include "DataDefs.h"\n#include "Core.h"')
s = s.replace('void save_barrier_update() {', '''void save_barrier_initialize() {
    g_shutting_down.store(false);
    g_world_loaded.store(false);
    g_active.store(true);
    g_save_cleanup.store(true);
    g_clear_frames = 0;
}

void save_barrier_update() {
    if (!g_shutting_down.load() && !g_world_loaded.load() &&
        DFHack::Core::getInstance().isWorldLoaded()) {
        g_world_loaded.store(true);
        g_save_cleanup.store(true);
        g_clear_frames = 0;
    }''')
p.write_text(s)
p = root / 'src/dfcapture.cpp'
s = p.read_text()
s = s.replace('dfcapture::save_barrier_set_world_loaded(Core::getInstance().isWorldLoaded());', 'dfcapture::save_barrier_initialize();')
p.write_text(s)
