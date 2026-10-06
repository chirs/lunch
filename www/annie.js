// Plays whenever Run simulation is pressed.

const ANNIE_BPM = 104;
const ANNIE_LYRICS = [
  'Down off Northwest Highway',
  'where the drive times run free',
  'there\'s a place Google never found',
  'not in grid cell one-oh-three',
  'POKE SALAT ANNIE',
  'Bachman Tacos called her cousin',
  'but she never made the list',
  'twenty reviews was all she needed',
  'and the Nearby Search just missed',
  'POKE SALAT ANNIE (uh!)',
  'the gators got your score',
  'POLK SALAD ANNIE',
  'twenty-three minutes and no more',
  'her hours read eleven to two',
  'she\'s closed on Sunday, mind',
  'she\'d beat a four-point-eight from thirty',
  'if update.py could find',
  'run it cached... run it cached...',
  'don\'t you spend no thousand calls',
  './update.py --near',
  'one-point-five miles round her shack',
  './visit.py "annie" --rating 5',
  'and she ain\'t ever coming back',
  'SOCK IT TO ME',
];

let annie = null;

function annieSing() {
  if (annie) return;
  const ctx = new AudioContext();
  const out = ctx.createGain();
  out.gain.value = 1;
  out.connect(ctx.destination);
  const fuzz = ctx.createWaveShaper();
  fuzz.curve = Float32Array.from({ length: 1024 }, (_, n) => Math.tanh(((n / 512) - 1) * 6));
  fuzz.connect(out);
  const noise = ctx.createBuffer(1, ctx.sampleRate / 4, ctx.sampleRate);
  noise.getChannelData(0).forEach((_, n, data) => { data[n] = Math.random() * 2 - 1; });

  const envelope = (node, at, peak, length) => {
    node.gain.setValueAtTime(peak, at);
    node.gain.exponentialRampToValueAtTime(0.001, at + length);
  };
  const kick = at => {
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.frequency.setValueAtTime(140, at);
    osc.frequency.exponentialRampToValueAtTime(40, at + 0.15);
    envelope(gain, at, 1, 0.3);
    osc.connect(gain).connect(out);
    osc.start(at);
    osc.stop(at + 0.3);
  };
  const snare = at => {
    const src = ctx.createBufferSource(), gain = ctx.createGain(), band = ctx.createBiquadFilter();
    src.buffer = noise;
    band.type = 'highpass';
    band.frequency.value = 1200;
    envelope(gain, at, 0.6, 0.18);
    src.connect(band).connect(gain).connect(out);
    src.start(at);
  };
  const note = (at, freq, length, type, dest, peak) => {
    const osc = ctx.createOscillator(), gain = ctx.createGain(), low = ctx.createBiquadFilter();
    osc.type = type;
    osc.frequency.value = freq;
    low.frequency.value = 900;
    envelope(gain, at, peak, length);
    osc.connect(low).connect(gain).connect(dest);
    osc.start(at);
    osc.stop(at + length);
  };

  // A swung E-minor pentatonic stomp: two bars per lyric line.
  const beat = 60 / ANNIE_BPM;
  const swing = n => n * beat / 2 + (n % 2 ? beat / 6 : 0);
  const riff = [82.4, 0, 82.4, 98, 82.4, 110, 98, 0, 82.4, 0, 82.4, 98, 123.5, 110, 98, 73.4];
  const start = ctx.currentTime + 0.1;
  const bars = ANNIE_LYRICS.length * 2;
  for (let bar = 0; bar < bars; bar++) {
    const t0 = start + bar * 4 * beat;
    for (let b = 0; b < 4; b++) {
      if (b % 2 === 0) kick(t0 + b * beat);
      else snare(t0 + b * beat);
    }
    riff.slice((bar % 2) * 8, (bar % 2) * 8 + 8).forEach((freq, n) => {
      if (!freq) return;
      note(t0 + swing(n), freq, beat / 2, 'sawtooth', out, 0.5);
      if (bar % 4 === 3 && n % 2 === 0) note(t0 + swing(n), freq * 4, beat / 2, 'square', fuzz, 0.12);
    });
  }

  const overlay = document.createElement('div');
  overlay.id = 'annie';
  overlay.innerHTML = '<div class="annie-singer" aria-hidden="true">✻</div><p class="annie-line"></p><p class="annie-hint">Esc to make it stop</p>';
  document.body.append(overlay);
  const line = overlay.querySelector('.annie-line');
  const singer = overlay.querySelector('.annie-singer');
  let shown = -1;
  const tick = () => {
    const elapsed = ctx.currentTime - start;
    const index = Math.floor(elapsed / (8 * beat));
    if (index >= ANNIE_LYRICS.length) return annieStop();
    if (index >= 0 && index !== shown) {
      shown = index;
      line.textContent = ANNIE_LYRICS[index];
      line.classList.toggle('annie-shout', ANNIE_LYRICS[index] === ANNIE_LYRICS[index].toUpperCase());
    }
    const pulse = 1 - ((elapsed / beat) % 1);
    singer.style.transform = `scale(${1 + pulse * 0.35}) rotate(${Math.sin(elapsed * 3) * 15}deg)`;
    document.body.style.transform = pulse > 0.85 ? `translate(${Math.random() * 8 - 4}px, ${Math.random() * 8 - 4}px)` : '';
    annie.frame = requestAnimationFrame(tick);
  };
  annie = { ctx, overlay, frame: requestAnimationFrame(tick) };
  overlay.addEventListener('click', annieStop);
}

function annieStop() {
  if (!annie) return;
  cancelAnimationFrame(annie.frame);
  annie.ctx.close();
  annie.overlay.remove();
  document.body.style.transform = '';
  annie = null;
}

document.getElementById('simulate').addEventListener('click', annieSing);
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') annieStop();
}, true);
