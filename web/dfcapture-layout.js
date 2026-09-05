/* Scale the browser chrome together and keep map input aligned with its image. */
(() => {
  const hud = document.getElementById('hud');
  // Each settings row already contains its help text; native tooltips obscure it.
  document.querySelectorAll('#settingsMenu .set-row[title]').forEach(row => row.removeAttribute('title'));
  const actions = document.createElement('div');
  actions.id = 'headerActions';
  hud.append(actions);
  actions.append(document.getElementById('pauseRow'), document.getElementById('extraTools'));
  document.getElementById('leftTools').append(document.getElementById('chatToggle'));

  let scheduled = false;
  const measure = () => {
    scheduled = false;
    hud.style.gridTemplateRows = hud.clientWidth <= 1000
      ? 'auto auto minmax(0, 1fr) auto' : 'auto minmax(0, 1fr) auto';
    const scale = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--ui-scale')) || 1;
    const top = Math.max(...['topbar', 'headerActions'].map(id => document.getElementById(id).getBoundingClientRect().bottom));
    const audio = document.getElementById('liveAudioBar');
    const audioHeight = audio ? audio.getBoundingClientRect().height : 0;
    document.documentElement.style.setProperty('--dfc-audio-gutter', `${audioHeight / scale}px`);
    const toolbarHeight = document.getElementById('bottomBar').getBoundingClientRect().height;
    document.documentElement.style.setProperty('--dfc-toolbar-height', `${toolbarHeight / scale}px`);
    const bottom = toolbarHeight + audioHeight;
    document.documentElement.style.setProperty('--dfc-top', `${Math.ceil(top / scale)}px`);
    document.documentElement.style.setProperty('--dfc-bottom', `${Math.ceil(bottom / scale)}px`);
  };
  const schedule = () => { if (!scheduled) { scheduled = true; requestAnimationFrame(measure); } };
  const observer = new ResizeObserver(schedule);
  ['hud', 'topbar', 'headerActions', 'bottomBar'].forEach(id => observer.observe(document.getElementById(id)));
  const audioObserver = new MutationObserver(() => {
    const audio = document.getElementById('liveAudioBar');
    if (audio) { observer.observe(audio); audioObserver.disconnect(); schedule(); }
  });
  const audio = document.getElementById('liveAudioBar');
  if (audio) observer.observe(audio);
  else audioObserver.observe(document.body, { childList: true, subtree: true });
  addEventListener('resize', schedule);
  schedule();

  // Native isolated per-player capture zoom; never scale the browser image.
  const controls = document.createElement('div');
  controls.id = 'mapZoomControls';
  controls.innerHTML = '<span>Map</span><button class="square-button" type="button" aria-label="Zoom map out">−</button><button class="top-button" type="button" aria-label="Reset map zoom">100%</button><button class="square-button" type="button" aria-label="Zoom map in">+</button>';
  actions.append(controls);
  const buttons = controls.querySelectorAll('button');
  ['out', 'reset', 'in'].forEach((direction, index) => buttons[index].addEventListener('click', event => {
    event.stopPropagation(); sendZoom(direction);
  }));
  const syncChrome = window.dfcSyncClientChrome;
  window.dfcSyncClientChrome = data => {
    if (syncChrome) syncChrome(data);
    const percent = Number(data?.camera?.zoom) || 100;
    buttons[1].textContent = `${Math.round(10000 / percent)}%`;
  };
  // Preserve the preference while keeping controls reachable in small windows.
  const originalApplyUiScale = applyUiScale;
  applyUiScale = () => {
    originalApplyUiScale();
    const fitted = Math.min(uiScale, Math.max(0.7, innerWidth / 800), Math.max(0.7, innerHeight / 600));
    document.documentElement.style.setProperty('--ui-scale', String(fitted));
    if (uiScaleReadout) {
      uiScaleReadout.textContent = `${Math.round(fitted * 100)}%` + (fitted < uiScale ? ' (auto)' : '');
      uiScaleReadout.title = `Preferred scale: ${Math.round(uiScale * 100)}%`;
    }
    schedule();
  };
  addEventListener('resize', applyUiScale);
  applyUiScale();
})();
