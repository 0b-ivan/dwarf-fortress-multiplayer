// Live Dwarf Fortress audio streamed from PulseAudio -> ffmpeg -> Icecast.
(function () {
  "use strict";

  const STORAGE_VOLUME = "dfcapture.liveAudio.volume";
  const STORAGE_MUTED = "dfcapture.liveAudio.muted";
  const STREAM_URL = "/audio";

  function boot() {
    const audio = document.getElementById("liveDfAudio");
    const enable = document.getElementById("liveAudioEnable");
    const status = document.getElementById("liveAudioStatus");
    if (!audio || !enable || !status) return;

    try {
      const volume = Number(localStorage.getItem(STORAGE_VOLUME));
      if (Number.isFinite(volume)) audio.volume = Math.max(0, Math.min(1, volume));
      audio.muted = localStorage.getItem(STORAGE_MUTED) === "true";
    } catch (_) {}

    function setStatus(value) {
      status.textContent = value;
    }

    let requestedPlayback = false;

    function remember() {
      try {
        localStorage.setItem(STORAGE_VOLUME, String(audio.volume));
        localStorage.setItem(STORAGE_MUTED, String(audio.muted));
      } catch (_) {}
    }

    async function start() {
      requestedPlayback = true;
      setStatus("Connecting…");
      try {
        await audio.play();
        enable.hidden = true;
      } catch (_) {
        setStatus("Click to enable audio");
        enable.hidden = false;
      }
    }

    let reconnectTimer = null;
    function reconnect() {
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(() => {
        audio.src = `${STREAM_URL}?t=${Date.now()}`;
        audio.load();
        if (requestedPlayback) start();
      }, 1200);
    }

    enable.addEventListener("click", start);
    audio.addEventListener("volumechange", remember);
    audio.addEventListener("playing", () => {
      enable.hidden = true;
      setStatus("Live DF audio");
    });
    audio.addEventListener("pause", () => {
      if (!audio.error) requestedPlayback = false;
    });
    audio.addEventListener("waiting", () => setStatus("Buffering…"));
    audio.addEventListener("stalled", () => {
      setStatus("Reconnecting…");
      reconnect();
    });
    audio.addEventListener("abort", reconnect);
    audio.addEventListener("error", () => {
      setStatus("Reconnecting…");
      reconnect();
    });

    start();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
