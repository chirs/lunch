// Run simulation gets a Vegas-style stomp while it rolls, and a big finish
// when it lands on a place. app.js fires 'lunch-decided' at that moment.

const ANNIE_BPM = 132;
const ANNIE_SHOUTS = ['POKE SALAT ANNIE', 'UH!', 'WHERE WE EATIN\'', 'SOCK IT TO ME', 'HUH!', 'POLK SALAD ANNIE'];

let annie = null;

function annieVoice() {
  const voices = speechSynthesis.getVoices().filter(v => v.lang.startsWith('en'));
  return voices.find(v => /daniel|fred|alex|male/i.test(v.name)) ?? voices[0];
}

function annieSay(text, rate = 0.8) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const words = new SpeechSynthesisUtterance(text);
  words.voice = annieVoice() ?? null;
  words.pitch = 0.1;
  words.rate = rate;
  speechSynthesis.speak(words);
}

function annieSing() {
  if (annie) annieStop();
  const ctx = new AudioContext();
  const out = ctx.createGain();
  out.connect(ctx.destination);
  // The band runs through its own bus so the finish can cut it dead.
  const band = ctx.createGain();
  band.connect(out);
  const noise = ctx.createBuffer(1, ctx.sampleRate / 4, ctx.sampleRate);
  noise.getChannelData(0).forEach((_, n, data) => { data[n] = Math.random() * 2 - 1; });

  const envelope = (node, at, peak, length) => {
    node.gain.setValueAtTime(peak, at);
    node.gain.exponentialRampToValueAtTime(0.001, at + length);
  };
  const kick = (at, dest) => {
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.frequency.setValueAtTime(140, at);
    osc.frequency.exponentialRampToValueAtTime(40, at + 0.15);
    envelope(gain, at, 1, 0.3);
    osc.connect(gain).connect(dest);
    osc.start(at);
    osc.stop(at + 0.3);
  };
  const crash = (at, dest, peak, length) => {
    const src = ctx.createBufferSource(), gain = ctx.createGain(), high = ctx.createBiquadFilter();
    src.buffer = noise;
    src.loop = true;
    high.type = 'highpass';
    high.frequency.value = 1500;
    envelope(gain, at, peak, length);
    src.connect(high).connect(gain).connect(dest);
    src.start(at);
    src.stop(at + length);
  };
  // Brass: three detuned saws through a closing filter, punched in fast.
  const horn = (at, freqs, length, dest, peak) => {
    const gain = ctx.createGain(), low = ctx.createBiquadFilter();
    low.frequency.setValueAtTime(3000, at);
    low.frequency.exponentialRampToValueAtTime(700, at + length);
    gain.gain.setValueAtTime(0.001, at);
    gain.gain.exponentialRampToValueAtTime(peak, at + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, at + length);
    low.connect(gain).connect(dest);
    for (const freq of freqs) {
      for (const detune of [-12, 0, 12]) {
        const osc = ctx.createOscillator();
        osc.type = 'sawtooth';
        osc.frequency.value = freq;
        osc.detune.value = detune;
        osc.connect(low);
        osc.start(at);
        osc.stop(at + length);
      }
    }
  };
  const bass = (at, freq, length) => {
    const osc = ctx.createOscillator(), gain = ctx.createGain(), low = ctx.createBiquadFilter();
    osc.type = 'sawtooth';
    osc.frequency.value = freq;
    low.frequency.value = 500;
    envelope(gain, at, 0.6, length);
    osc.connect(low).connect(gain).connect(band);
    osc.start(at);
    osc.stop(at + length);
  };

  // Enough bars to outlast any roll; the finish cuts it short.
  const beat = 60 / ANNIE_BPM;
  const walk = [82.4, 82.4, 98, 110, 123.5, 110, 98, 73.4];
  const start = ctx.currentTime + 0.05;
  for (let bar = 0; bar < 16; bar++) {
    const t0 = start + bar * 4 * beat;
    for (let b = 0; b < 4; b++) {
      kick(t0 + b * beat, band);
      if (b % 2) crash(t0 + b * beat, band, 0.35, 0.12);
    }
    walk.forEach((freq, n) => bass(t0 + n * beat / 2, freq, beat / 2));
    horn(t0 + 1.5 * beat, [329.6, 415.3, 493.9], beat * 0.4, band, 0.12);
    horn(t0 + 3 * beat, [329.6, 392, 493.9], beat * 0.6, band, 0.12);
  }

  const overlay = document.createElement('div');
  overlay.id = 'annie';
  overlay.innerHTML = '<div class="annie-singer" aria-hidden="true">✻</div><p class="annie-line"></p><button type="button" class="annie-stop">Stop</button>';
  document.body.append(overlay);
  const line = overlay.querySelector('.annie-line');
  const singer = overlay.querySelector('.annie-singer');
  annie = { ctx, out, band, start, beat, horn, kick, crash, overlay, line, ending: false };
  overlay.querySelector('.annie-stop').addEventListener('click', annieStop);
  annieSay('Poke salat Annie. Uh.', 0.9);

  const tick = () => {
    if (!annie || annie.ctx !== ctx) return;
    const elapsed = ctx.currentTime - start;
    if (!annie.ending) line.textContent = ANNIE_SHOUTS[Math.max(0, Math.floor(elapsed / beat)) % ANNIE_SHOUTS.length];
    const pulse = annie.ending ? 0 : 1 - ((elapsed / beat) % 1);
    singer.style.transform = `scale(${1 + pulse * 0.35}) rotate(${Math.sin(elapsed * 4) * 18}deg)`;
    annie.frame = requestAnimationFrame(tick);
  };
  annie.frame = requestAnimationFrame(tick);
}

// Cut the band, hit one big E chord with a crash, and thank the room.
function annieFinish(name) {
  if (!annie || annie.ending) return;
  const { ctx, band, out, horn, kick, crash, line } = annie;
  annie.ending = true;
  const now = ctx.currentTime;
  band.gain.setValueAtTime(band.gain.value, now);
  band.gain.linearRampToValueAtTime(0, now + 0.03);
  kick(now + 0.03, out);
  crash(now + 0.03, out, 0.5, 2.5);
  horn(now + 0.03, [164.8, 329.6, 415.3, 493.9, 659.3], 2.6, out, 0.1);
  line.textContent = name ? `${name}. Thank you very much.` : 'Thank you very much.';
  annieSay('Thank you. Thank you very much.', 0.85);
  const ctxNow = ctx;
  setTimeout(() => { if (annie?.ctx === ctxNow) annieStop(); }, 3500);
}

function annieStop() {
  if (!annie) return;
  cancelAnimationFrame(annie.frame);
  annie.ctx.close();
  annie.overlay.remove();
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  annie = null;
}

// Capture, so the song is running before app.js decides, even when it decides at once.
document.addEventListener('click', event => {
  if (event.target.closest('#simulate') && !event.target.closest('#simulate').disabled) annieSing();
}, true);
document.addEventListener('lunch-decided', event => annieFinish(event.detail));
