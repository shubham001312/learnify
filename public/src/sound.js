// Soft UI sounds generated with the Web Audio API (no external audio files).
let _ctx = null;
let _enabled = true;
try { _enabled = localStorage.getItem('learnify_sound') !== 'off'; } catch (_) {}

function _ctxReady() {
  if (!_ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    _ctx = new AC();
  }
  if (_ctx.state === 'suspended') _ctx.resume();
  return _ctx;
}

export function soundEnabled() { return _enabled; }

export function setSoundEnabled(v) {
  _enabled = !!v;
  try { localStorage.setItem('learnify_sound', _enabled ? 'on' : 'off'); } catch (_) {}
}

// Generic soft tone with an optional pitch slide.
function _tone({ freq = 440, dur = 0.12, type = 'sine', gain = 0.07, slideTo = null, delay = 0 }) {
  if (!_enabled) return;
  const ctx = _ctxReady();
  if (!ctx) return;
  const t0 = ctx.currentTime + delay;
  const osc = ctx.createOscillator();
  const g = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t0);
  if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, t0 + dur);
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.exponentialRampToValueAtTime(gain, t0 + 0.012);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(g); g.connect(ctx.destination);
  osc.start(t0);
  osc.stop(t0 + dur + 0.03);
}

// Gentle two-note chime played when Veda finishes a reply.
export function playChatDing() {
  _tone({ freq: 660, dur: 0.14, type: 'sine', gain: 0.06 });
  _tone({ freq: 990, dur: 0.18, type: 'sine', gain: 0.05, delay: 0.10 });
}

// Soft tick for calculator keys and small button presses.
export function playClick() {
  _tone({ freq: 320, dur: 0.045, type: 'triangle', gain: 0.035, slideTo: 220 });
}
