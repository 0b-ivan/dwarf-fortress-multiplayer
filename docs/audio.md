# Live Dwarf Fortress audio

The browser player uses the real audio mix produced by the single shared Dwarf Fortress process.

```text
Dwarf Fortress / SDL / FMOD
          |
          v
PulseAudio virtual_out
          |
          v
virtual_out.monitor
          |
          v
ffmpeg -> Ogg/Opus -> Icecast 127.0.0.1:8000/df.ogg
          |
          v
nginx :8765/audio
          |
          v
browser soundbar
```

DFCapture listens only on `127.0.0.1:8766`. nginx is the public player gateway on `:8765` and proxies normal DFCapture requests to that backend while `/audio` is proxied to Icecast without buffering.

The upstream DFCapture direct installed-track audio client is disabled in the packaged web UI to prevent music from playing twice. Volume and mute state for the live stream are stored in browser local storage.

## Diagnostics

Inside the running container:

```bash
pactl info
pactl list short sinks
pactl list short sources
curl -I http://127.0.0.1:8765/audio
```

Relevant logs:

```text
/var/log/df/pulse.log
/var/log/df/audio.log
/var/log/df/icecast.log
/var/log/df/icecast-error.log
/var/log/df/nginx-error.log
```

A browser may block autoplay with sound. In that case the soundbar displays an `Enable audio` button.
