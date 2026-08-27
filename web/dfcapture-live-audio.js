// Live Dwarf Fortress audio streamed from PulseAudio -> ffmpeg -> Icecast.
(function () {
  "use strict";

  const STORAGE_VOLUME = "dfcapture.liveAudio.volume";
  const STORAGE_MUTED = "dfcapture.liveAudio.muted";

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

    function remember() {
      try {
        localStorage.setItem(STORAGE_VOLUME, String(audio.volume));
        localStorage.setItem(STORAGE_MUTED, String(audio.muted));
      } catch (_) {}
    }

    async function start() {
      setStatus("Connecting…");
      try {
        await audio.play();
        enable.hidden = true;
      } catch (_) {
        setStatus("Click to enable audio");
        enable.hidden = false;
      }
    }

    enable.addEventListener("click", start);
    audio.addEventListener("volumechange", remember);
    audio.addEventListener("playing", () => {
      enable.hidden = true;
      setStatus("Live DF audio");
    });
    audio.addEventListener("waiting", () => setStatus("Buffering…"));
    audio.addEventListener("stalled", () => setStatus("Reconnecting…"));
    audio.addEventListener("error", () => {
      enable.hidden = false;
      setStatus("Audio unavailable");
    });

    start();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
