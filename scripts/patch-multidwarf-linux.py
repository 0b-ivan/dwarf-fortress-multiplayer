#!/usr/bin/env python3
# Minimal Linux enablement patch for SourceAirbender/multi-dwarf at the pinned
# commit used by this repository.

from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8-sig')

def write(rel, text):
    (ROOT / rel).write_text(text, encoding='utf-8')

def require_replace(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'{label}: expected source fragment not found')
    return text.replace(old, new, 1)

def unwrap_windows_command(text, name):
    pattern = re.compile(
        rf'(command_result\s+{re.escape(name)}\s*\([^{{]*\)\s*\{{)\n'
        r'#ifdef _WIN32\n'
        r'(.*?)\n'
        r'#else\n'
        r'.*?currently Windows-only.*?\n'
        r'\s*return CR_FAILURE;\n'
        r'#endif\n'
        r'\}',
        re.S,
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f'{name}: Windows guard not found')
    return text[:match.start()] + match.group(1) + '\n' + match.group(2) + '\n}' + text[match.end():]

# CMake ---------------------------------------------------------------------
cmake = read('CMakeLists.txt')
needle = 'dfhack_plugin(dfcapture_public\n'
insert = '''if(WIN32)
    set(DFCAPTURE_PLATFORM_LIBS bcrypt gdiplus ole32 ws2_32)
else()
    find_package(JPEG REQUIRED)
    find_package(PNG REQUIRED)
    set(DFCAPTURE_PLATFORM_LIBS JPEG::JPEG PNG::PNG dl)
endif()

'''
if insert not in cmake:
    cmake = require_replace(cmake, needle, insert + needle, 'CMake platform libs')
cmake = require_replace(
    cmake,
    '    LINK_LIBRARIES bcrypt gdiplus ole32 ws2_32 lua jsoncpp_static)',
    '    LINK_LIBRARIES ${DFCAPTURE_PLATFORM_LIBS} lua jsoncpp_static)',
    'CMake LINK_LIBRARIES',
)
# DFHack enables -Werror for the whole tree. On Linux, a few upstream helper
# functions and one Windows-only failure label become intentionally unused after
# the platform guards below are opened up. Keep DFHack strict, but do not turn
# these expected porting warnings into errors for this external plugin target.
linux_warning_block = '''if(NOT WIN32)
    target_compile_options(dfcapture_public PRIVATE
        -Wno-error=unused-function
        -Wno-error=unused-label)
endif()

'''
if linux_warning_block not in cmake:
    cmake += '\n' + linux_warning_block
write('CMakeLists.txt', cmake)

# Fix an upstream style pattern that GCC diagnoses as misleading indentation.
# The statements are semantically separate; make that explicit instead of
# suppressing the diagnostic.
for cpp in (ROOT / 'src').glob('*.cpp'):
    text = cpp.read_text(encoding='utf-8-sig')
    fixed = re.sub(
        r'(?m)^(?P<indent>[ \t]*)if \(!first\) body << ","; first = false;[ \t]*$',
        lambda m: (f'{m.group("indent")}if (!first)\n'
                   f'{m.group("indent")}    body << ",";\n'
                   f'{m.group("indent")}first = false;'),
        text,
    )
    if fixed != text:
        cpp.write_text(fixed, encoding='utf-8')

# GCC/Linux: df::coord stores x/y as signed 16-bit values while Maps::getTileSize
# returns unsigned 32-bit dimensions. Compare against signed 32-bit edge
# coordinates so -Werror=sign-compare stays useful instead of being suppressed.
trade = read('src/trade_depot.cpp')
trade_old = '''    auto& edge = df::global::plotinfo->map_edge;
    for (size_t i = 0; i < edge.surface_x.size(); ++i) {
        df::coord pos(edge.surface_x[i], edge.surface_y[i], edge.surface_z[i]);
        if ((pos.x == 0 || pos.y == 0 || pos.x == count_x - 1 || pos.y == count_y - 1) &&
            DFHack::Maps::getWalkableGroup(pos) == walk_group)
            entry_tiles.emplace(pos);
    }'''
trade_new = '''    const int32_t edge_x = static_cast<int32_t>(count_x - 1);
    const int32_t edge_y = static_cast<int32_t>(count_y - 1);
    auto& edge = df::global::plotinfo->map_edge;
    for (size_t i = 0; i < edge.surface_x.size(); ++i) {
        df::coord pos(edge.surface_x[i], edge.surface_y[i], edge.surface_z[i]);
        if ((pos.x == 0 || pos.y == 0 || pos.x == edge_x || pos.y == edge_y) &&
            DFHack::Maps::getWalkableGroup(pos) == walk_group)
            entry_tiles.emplace(pos);
    }'''
trade = require_replace(trade, trade_old, trade_new, 'Linux trade depot signed edge comparison')
write('src/trade_depot.cpp', trade)

# Main plugin ---------------------------------------------------------------
main = read('src/dfcapture.cpp')
for fn in ('cmd_start', 'cmd_stop', 'cmd_status'):
    main = unwrap_windows_command(main, fn)

shutdown_old = '''DFhackCExport command_result plugin_shutdown(color_ostream&) {
#ifdef _WIN32
    is_enabled = false;
    dfcapture::save_barrier_shutdown();
    dfcapture::diagnostics_log("plugin shutdown");
    dfcapture::stop_server();
    dfcapture::restore_overlay_after_stream();
    dfcapture::shutdown_image_encoder();
    dfcapture::ownership_clear_world();
#endif
    return CR_OK;
}'''
shutdown_new = '''DFhackCExport command_result plugin_shutdown(color_ostream&) {
    is_enabled = false;
    dfcapture::save_barrier_shutdown();
    dfcapture::diagnostics_log("plugin shutdown");
    dfcapture::stop_server();
    dfcapture::restore_overlay_after_stream();
    dfcapture::shutdown_image_encoder();
    dfcapture::ownership_clear_world();
    return CR_OK;
}'''
main = require_replace(main, shutdown_old, shutdown_new, 'plugin_shutdown')
write('src/dfcapture.cpp', main)

# SDL capture ---------------------------------------------------------------
sdl = read('src/sdl_capture.cpp')
sdl = require_replace(
    sdl,
    '#include <algorithm>\n',
    '#ifndef _WIN32\n#include <dlfcn.h>\n#endif\n\n#include <algorithm>\n',
    'sdl dlfcn include',
)
sdl_old = '''#else
    if (err) *err = "SDL capture is currently Windows-only";
    return false;
#endif
}'''
sdl_new = '''#else
    dlerror();
    p_CreateTexture = reinterpret_cast<pfn_CreateTexture>(dlsym(RTLD_DEFAULT, "SDL_CreateTexture"));
    p_SetRenderTarget = reinterpret_cast<pfn_SetRenderTarget>(dlsym(RTLD_DEFAULT, "SDL_SetRenderTarget"));
    p_RenderReadPixels = reinterpret_cast<pfn_RenderReadPixels>(dlsym(RTLD_DEFAULT, "SDL_RenderReadPixels"));
    p_DestroyTexture = reinterpret_cast<pfn_DestroyTexture>(dlsym(RTLD_DEFAULT, "SDL_DestroyTexture"));
    p_GetRendererOutputSize = reinterpret_cast<pfn_GetRendererOutputSize>(dlsym(RTLD_DEFAULT, "SDL_GetRendererOutputSize"));
    p_SetRenderDrawColor = reinterpret_cast<pfn_SetRenderDrawColor>(dlsym(RTLD_DEFAULT, "SDL_SetRenderDrawColor"));
    p_RenderClear = reinterpret_cast<pfn_RenderClear>(dlsym(RTLD_DEFAULT, "SDL_RenderClear"));

    if (p_CreateTexture && p_SetRenderTarget && p_RenderReadPixels &&
        p_DestroyTexture && p_GetRendererOutputSize &&
        p_SetRenderDrawColor && p_RenderClear) {
        return true;
    }

    const char* why = dlerror();
    if (err) {
        *err = std::string("could not resolve required SDL2 functions on Linux");
        if (why) *err += std::string(": ") + why;
    }
    return false;
#endif
}'''
sdl = require_replace(sdl, sdl_old, sdl_new, 'sdl resolve_sdl')

geom_old = '''#ifdef _WIN32
    if (gps && gps->main_viewport)
        read_capture_geometry_seh(renderer, gps->main_viewport, next.geometry);
#endif
    next.bgra.resize'''
geom_new = '''#ifdef _WIN32
    if (gps && gps->main_viewport)
        read_capture_geometry_seh(renderer, gps->main_viewport, next.geometry);
#else
    if (gps && gps->main_viewport) {
        auto renderer_2d = DFHack::virtual_cast<df::renderer_2d>(renderer);
        auto vp = gps->main_viewport;
        if (renderer_2d && renderer_2d->viewport_zoom_factor > 0 &&
                vp->dim_x > 0 && vp->dim_y > 0) {
            next.geometry.origin_x = renderer_2d->origin_x;
            next.geometry.origin_y = renderer_2d->origin_y;
            next.geometry.zoom_factor = renderer_2d->viewport_zoom_factor;
            next.geometry.viewport_width = vp->dim_x;
            next.geometry.viewport_height = vp->dim_y;
            next.geometry.valid = true;
        }
    }
#endif
    next.bgra.resize'''
sdl = require_replace(sdl, geom_old, geom_new, 'Linux capture geometry')

linux_failure_old = '''#else
    if (!render_current_viewscreen(&map_err)) {
        if (err) *err = map_err;
        return false;
    }
    needs_full_host_restore = true;
#endif'''
linux_failure_new = '''#else
    if (!render_current_viewscreen(&map_err)) {
        *df::global::window_x = saved.x;
        *df::global::window_y = saved.y;
        *df::global::window_z = saved.z;
        if (gps)
            gps->force_full_display_count = 1;
        if (err) *err = map_err;
        return false;
    }
#endif'''
sdl = require_replace(sdl, linux_failure_old, linux_failure_new, 'Linux camera restore on error')

# This state is consumed only by the Windows native-render restore path.
# Do not create or assign it on Linux, where GCC correctly diagnoses it as
# set-but-never-used under DFHack's global -Werror policy.
sdl = require_replace(
    sdl,
    '    bool needs_full_host_restore = false;\n\n#ifdef _WIN32\n',
    '#ifdef _WIN32\n    bool needs_full_host_restore = false;\n\n',
    'Windows-only host restore state',
)
write('src/sdl_capture.cpp', sdl)

# Image encoder -------------------------------------------------------------
enc = read('src/image_encoder.cpp')
enc = require_replace(
    enc,
    '#include <algorithm>\n#include <fstream>\n#include <mutex>\n',
    '''#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <mutex>

#ifndef _WIN32
#include <cstdio>
#include <setjmp.h>
extern "C" {
#include <jpeglib.h>
}
#include <png.h>
#endif
''',
    'image encoder Linux includes',
)

helper_anchor = 'bool validate_frame(const CapturedFrame& frame, std::string* err) {'
helpers = r'''#ifndef _WIN32
struct JpegErrorState {
    jpeg_error_mgr base;
    jmp_buf jump;
    char message[JMSG_LENGTH_MAX] = {};
};

void jpeg_error_exit_bridge(j_common_ptr cinfo) {
    auto* state = reinterpret_cast<JpegErrorState*>(cinfo->err);
    (*cinfo->err->format_message)(cinfo, state->message);
    longjmp(state->jump, 1);
}

bool encode_jpeg_libjpeg(const CapturedFrame& frame, std::vector<uint8_t>& out,
                         int quality, std::string* err) {
    jpeg_compress_struct cinfo = {};
    JpegErrorState state = {};
    cinfo.err = jpeg_std_error(&state.base);
    state.base.error_exit = jpeg_error_exit_bridge;

    unsigned char* memory = nullptr;
    unsigned long memory_size = 0;

    if (setjmp(state.jump)) {
        jpeg_destroy_compress(&cinfo);
        std::free(memory);
        if (err) *err = state.message[0] ? state.message : "libjpeg failed";
        return false;
    }

    jpeg_create_compress(&cinfo);
    jpeg_mem_dest(&cinfo, &memory, &memory_size);
    cinfo.image_width = frame.width;
    cinfo.image_height = frame.height;
    cinfo.input_components = 3;
    cinfo.in_color_space = JCS_RGB;
    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, std::max(1, std::min(100, quality)), TRUE);
    jpeg_start_compress(&cinfo, TRUE);

    std::vector<uint8_t> rgb(static_cast<size_t>(frame.width) * 3);
    while (cinfo.next_scanline < cinfo.image_height) {
        const uint8_t* src = frame.bgra.data() +
            static_cast<size_t>(cinfo.next_scanline) * frame.width * 4;
        for (int x = 0; x < frame.width; ++x) {
            rgb[static_cast<size_t>(x) * 3 + 0] = src[static_cast<size_t>(x) * 4 + 2];
            rgb[static_cast<size_t>(x) * 3 + 1] = src[static_cast<size_t>(x) * 4 + 1];
            rgb[static_cast<size_t>(x) * 3 + 2] = src[static_cast<size_t>(x) * 4 + 0];
        }
        JSAMPROW row = rgb.data();
        jpeg_write_scanlines(&cinfo, &row, 1);
    }

    jpeg_finish_compress(&cinfo);
    out.assign(memory, memory + memory_size);
    jpeg_destroy_compress(&cinfo);
    std::free(memory);
    return true;
}

bool encode_png_libpng(const CapturedFrame& frame, std::vector<uint8_t>& out,
                       std::string* err) {
    png_image image = {};
    image.version = PNG_IMAGE_VERSION;
    image.width = static_cast<png_uint_32>(frame.width);
    image.height = static_cast<png_uint_32>(frame.height);
    image.format = PNG_FORMAT_BGRA;

    png_alloc_size_t size = 0;
    if (!png_image_write_to_memory(&image, nullptr, &size, 0,
                                   frame.bgra.data(), 0, nullptr)) {
        if (err) *err = image.message[0] ? image.message : "libpng size calculation failed";
        png_image_free(&image);
        return false;
    }

    out.resize(static_cast<size_t>(size));
    if (!png_image_write_to_memory(&image, out.data(), &size, 0,
                                   frame.bgra.data(), 0, nullptr)) {
        if (err) *err = image.message[0] ? image.message : "libpng encoding failed";
        png_image_free(&image);
        out.clear();
        return false;
    }
    out.resize(static_cast<size_t>(size));
    png_image_free(&image);
    return true;
}
#endif

'''
if helpers not in enc:
    enc = require_replace(enc, helper_anchor, helpers + helper_anchor, 'image encoder helpers')

enc = require_replace(
    enc,
    '''#else
    if (err) *err = "JPEG encoding is currently Windows-only";
    return false;
#endif''',
    '''#else
    return encode_jpeg_libjpeg(frame, jpeg, quality, err);
#endif''',
    'JPEG Linux backend',
)
enc = require_replace(
    enc,
    '''#else
    if (err) *err = "PNG encoding is currently Windows-only";
    return false;
#endif''',
    '''#else
    return encode_png_libpng(frame, png, err);
#endif''',
    'PNG Linux backend',
)
write('src/image_encoder.cpp', enc)

# Unit portraits ------------------------------------------------------------
portrait = read('src/unit_portrait.cpp')
portrait = require_replace(
    portrait,
    '#include <algorithm>\n',
    '#ifndef _WIN32\n#include <dlfcn.h>\n#endif\n\n#include <algorithm>\n',
    'portrait dlfcn include',
)
portrait_old = '''#else
    if (err) *err = "native portrait rendering is Windows-only";
    return false;
#endif
}'''
portrait_new = '''#else
    dlerror();
    p_CreateTexture = reinterpret_cast<pfn_CreateTexture>(dlsym(RTLD_DEFAULT, "SDL_CreateTexture"));
    p_SetRenderTarget = reinterpret_cast<pfn_SetRenderTarget>(dlsym(RTLD_DEFAULT, "SDL_SetRenderTarget"));
    p_RenderReadPixels = reinterpret_cast<pfn_RenderReadPixels>(dlsym(RTLD_DEFAULT, "SDL_RenderReadPixels"));
    p_DestroyTexture = reinterpret_cast<pfn_DestroyTexture>(dlsym(RTLD_DEFAULT, "SDL_DestroyTexture"));
    p_GetRendererOutputSize = reinterpret_cast<pfn_GetRendererOutputSize>(dlsym(RTLD_DEFAULT, "SDL_GetRendererOutputSize"));
    p_SetRenderDrawColor = reinterpret_cast<pfn_SetRenderDrawColor>(dlsym(RTLD_DEFAULT, "SDL_SetRenderDrawColor"));
    p_RenderClear = reinterpret_cast<pfn_RenderClear>(dlsym(RTLD_DEFAULT, "SDL_RenderClear"));
    p_ConvertSurfaceFormat = reinterpret_cast<pfn_ConvertSurfaceFormat>(dlsym(RTLD_DEFAULT, "SDL_ConvertSurfaceFormat"));
    p_LockSurface = reinterpret_cast<pfn_LockSurface>(dlsym(RTLD_DEFAULT, "SDL_LockSurface"));
    p_UnlockSurface = reinterpret_cast<pfn_UnlockSurface>(dlsym(RTLD_DEFAULT, "SDL_UnlockSurface"));
    p_FreeSurface = reinterpret_cast<pfn_FreeSurface>(dlsym(RTLD_DEFAULT, "SDL_FreeSurface"));

    if (p_CreateTexture && p_SetRenderTarget && p_RenderReadPixels &&
        p_DestroyTexture && p_GetRendererOutputSize && p_SetRenderDrawColor &&
        p_RenderClear && p_ConvertSurfaceFormat && p_LockSurface &&
        p_UnlockSurface && p_FreeSurface) {
        return true;
    }

    const char* why = dlerror();
    if (err) {
        *err = "could not resolve SDL2 portrait functions on Linux";
        if (why) *err += std::string(": ") + why;
    }
    return false;
#endif
}'''
portrait = require_replace(portrait, portrait_old, portrait_new, 'portrait resolve_sdl')
write('src/unit_portrait.cpp', portrait)

# Native barter -------------------------------------------------------------
trade = read('src/native_trade.cpp')
marker = 'namespace dfcapture {\nnamespace {\n\n'
trade_insert = '''#ifndef _WIN32
#ifndef __fastcall
#define __fastcall
#endif
#endif

'''
if trade_insert not in trade:
    trade = require_replace(trade, marker, marker + trade_insert, 'native trade calling convention')

assert_block = '''static_assert(offsetof(df::trade_interfacest, bld) == 0xb0);
static_assert(offsetof(df::trade_interfacest, mer) == 0xb8);
static_assert(offsetof(df::trade_interfacest, civ) == 0xc0);
static_assert(offsetof(df::trade_interfacest, merchant_trader) == 0xd0);
static_assert(offsetof(df::trade_interfacest, fortress_trader) == 0xd8);
static_assert(offsetof(df::trade_interfacest, good) == 0xe0);
static_assert(offsetof(df::trade_interfacest, goodflag) == 0x110);
static_assert(offsetof(df::trade_interfacest, good_amount) == 0x140);
static_assert(offsetof(df::trade_interfacest, talkline) == 0x37a);
static_assert(offsetof(df::trade_interfacest, buildlists) == 0x37c);
static_assert(offsetof(df::trade_interfacest, counter_offer) == 0x37e);
static_assert(offsetof(df::trade_interfacest, counter_offer_item) == 0x380);'''
if '#ifdef _WIN32\n' + assert_block not in trade:
    trade = require_replace(
        trade,
        assert_block,
        '#ifdef _WIN32\n' + assert_block + '\n#endif',
        'native trade ABI asserts',
    )
write('src/native_trade.cpp', trade)

print('Linux patch applied successfully')
