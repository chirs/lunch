// Two songs, both synthesized. Run simulation plays a New Order-style
// sequenced dance loop under a pulsar plot like Joy Division's Unknown Pleasures
// cover, and fades out on the pick (app.js fires 'lunch-decided'). Picking a place by
// hand plays a short Elvis number in a random style and key
// ('place-picked').

const ANNIE_BPM = 130;
const ANNIE_SHOUTS = ['BLUE MONDAY', 'BIZARRE LOVE TRIANGLE', 'WHERE WE EATIN\'', 'TRUE FAITH', 'CEREMONY', 'REGRET'];
const ELVIS_LINES = ['Well, alright now.', 'Thank you very much.', 'Takin\' care of business.', 'Let\'s go, baby.', 'Now that\'s lunch.'];

let annie = null;

function annieVoice() {
  const voices = speechSynthesis.getVoices().filter(v => v.lang.startsWith('en'));
  return voices.find(v => /aaron|alex|daniel|tom|reed|male/i.test(v.name)) ?? voices[0];
}

function annieSay(text, pitch, rate) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const words = new SpeechSynthesisUtterance(text);
  words.voice = annieVoice() ?? null;
  words.pitch = pitch;
  words.rate = rate;
  speechSynthesis.speak(words);
}

const pickOne = list => list[Math.floor(Math.random() * list.length)];

function annieKit(ctx) {
  const noise = ctx.createBuffer(1, ctx.sampleRate / 2, ctx.sampleRate);
  noise.getChannelData(0).forEach((_, n, data) => { data[n] = Math.random() * 2 - 1; });
  const envelope = (node, at, peak, length) => {
    node.gain.setValueAtTime(peak, at);
    node.gain.exponentialRampToValueAtTime(0.001, at + length);
  };
  const hiss = (dest, at, type, freq, peak, length) => {
    const src = ctx.createBufferSource(), gain = ctx.createGain(), filter = ctx.createBiquadFilter();
    src.buffer = noise;
    src.loop = true;
    filter.type = type;
    filter.frequency.value = freq;
    envelope(gain, at, peak, length);
    src.connect(filter).connect(gain).connect(dest);
    src.start(at);
    src.stop(at + length);
  };
  const kick = (dest, at) => {
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.frequency.setValueAtTime(130, at);
    osc.frequency.exponentialRampToValueAtTime(42, at + 0.12);
    envelope(gain, at, 0.9, 0.25);
    osc.connect(gain).connect(dest);
    osc.start(at);
    osc.stop(at + 0.25);
  };
  // A dry, clipped snare: a tight tone and a burst of noise, gated short.
  const snare = (dest, at, peak = 0.8) => {
    const osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.value = 190;
    envelope(gain, at, peak / 2, 0.08);
    osc.connect(gain).connect(dest);
    osc.start(at);
    osc.stop(at + 0.08);
    hiss(dest, at, 'bandpass', 2500, peak, 0.14);
  };
  // Oscillators (one per pitch and detune) through a lowpass that closes from
  // `open` to `shut`; covers the bass, brass, strings, guitar and organ.
  const tone = (dest, at, freqs, length, { type = 'sawtooth', peak = 0.1, open = 3000, shut = open, attack = 0.01, detunes = [0], q = 1 } = {}) => {
    const gain = ctx.createGain(), low = ctx.createBiquadFilter();
    low.Q.value = q;
    low.frequency.setValueAtTime(open, at);
    low.frequency.exponentialRampToValueAtTime(shut, at + length);
    gain.gain.setValueAtTime(0.001, at);
    gain.gain.exponentialRampToValueAtTime(peak, at + attack);
    gain.gain.exponentialRampToValueAtTime(0.001, at + length);
    low.connect(gain).connect(dest);
    for (const freq of freqs) {
      for (const detune of detunes) {
        const osc = ctx.createOscillator();
        osc.type = type;
        osc.frequency.value = freq;
        osc.detune.value = detune;
        osc.connect(low);
        osc.start(at);
        osc.stop(at + length);
      }
    }
  };
  // A drum-machine clap: three quick bursts of noise and a short tail.
  const clap = (dest, at, peak) => {
    for (const [lag, length] of [[0, 0.02], [0.012, 0.02], [0.024, 0.2]]) hiss(dest, at + lag, 'bandpass', 1400, peak, length);
  };
  return { hiss, kick, snare, clap, tone };
}

// Start a song: a fresh audio context, a band bus the finish can cut or fade,
// a room that feeds the band through a long reverb, and the corner banner with
// `art` beside the line.
function annieStart(kind, art) {
  annieStop();
  const ctx = new AudioContext();
  const out = ctx.createGain();
  out.connect(ctx.destination);
  const band = ctx.createGain();
  band.connect(out);
  const room = ctx.createGain(), reverb = ctx.createConvolver();
  const tail = ctx.createBuffer(2, ctx.sampleRate * 2, ctx.sampleRate);
  for (let c = 0; c < 2; c++) {
    tail.getChannelData(c).forEach((_, n, data) => { data[n] = (Math.random() * 2 - 1) * (1 - n / data.length) ** 3; });
  }
  reverb.buffer = tail;
  room.connect(band);
  room.connect(reverb).connect(band);
  const overlay = document.createElement('div');
  overlay.id = 'annie';
  overlay.innerHTML = `${art}<p class="annie-line"></p><button type="button" class="annie-stop">Stop</button>`;
  document.body.append(overlay);
  overlay.querySelector('.annie-stop').addEventListener('click', annieStop);
  annie = { kind, ctx, out, band, room, kit: annieKit(ctx), overlay, line: overlay.querySelector('.annie-line'), ending: false };
  return annie;
}

function annieSing() {
  const song = annieStart('simulation', '<canvas class="annie-pulsar" width="96" height="72" aria-hidden="true"></canvas>');
  const { ctx, band, room, line } = song;
  const { hiss, kick, clap, tone } = song.kit;

  // The roll lasts under three seconds, so everything comes in at once. A
  // drum machine with the stuttering sixteenth-note kick runs, a clap in a big
  // room on two and four, and open hats on the off-beats. Under it a
  // sequencer bass jumping octaves in sixteenths over Dm, C, F, Bb; the bass
  // guitar high up the neck, plucked and wet, carrying the tune; a choir-ish
  // string pad and a bright arpeggio. Enough bars to outlast any roll.
  const beat = 60 / ANNIE_BPM;
  const roots = [73.4, 65.4, 87.3, 58.3];
  const chords = [
    [293.7, 349.2, 440],
    [261.6, 329.6, 392],
    [349.2, 440, 523.3],
    [293.7, 349.2, 466.2],
  ];
  const hooks = [
    [440, 0, 440, 392, 349.2, 0, 293.7, 349.2],
    [392, 0, 392, 349.2, 329.6, 0, 261.6, 329.6],
    [349.2, 0, 440, 392, 349.2, 0, 261.6, 349.2],
    [349.2, 0, 293.7, 0, 233.1, 261.6, 293.7, 0],
  ];
  // Kick sixteenths per bar, alternating: four on the floor with a run into
  // the next bar, then a run across the whole back half.
  const kicks = [[0, 4, 8, 12, 13, 14, 15], [0, 4, 8, 9, 10, 11, 12, 13, 14, 15]];
  const start = ctx.currentTime + 0.05;
  for (let bar = 0; bar < 24; bar++) {
    const t0 = start + bar * 4 * beat;
    const root = roots[bar % 4], chord = chords[bar % 4];
    for (const n of kicks[bar % 2]) kick(band, t0 + n * beat / 4);
    for (let b = 0; b < 4; b++) {
      if (b % 2) clap(room, t0 + b * beat, 0.5);
      hiss(band, t0 + (b + 0.5) * beat, 'highpass', 7000, 0.1, 0.15);
    }
    for (let n = 0; n < 16; n++) tone(band, t0 + n * beat / 4, [n % 2 ? root * 2 : root], beat / 4, { type: 'square', peak: 0.16, open: 2400, shut: 300, attack: 0.003, q: 6 });
    hooks[bar % 4].forEach((freq, n) => {
      if (freq) tone(room, t0 + n * beat / 2, [freq], beat * 0.9, { peak: 0.13, open: 3200, shut: 600, attack: 0.004, detunes: [-12, 12] });
    });
    for (let n = 0; n < 16; n++) tone(room, t0 + n * beat / 4, [chord[(n * 2) % 3] * 2], beat / 5, { type: 'square', peak: 0.02, open: 4000, shut: 1200, attack: 0.003 });
    tone(room, t0, chord, 4 * beat, { type: 'triangle', peak: 0.06, attack: 0.25, detunes: [-14, 0, 14] });
  }
  annieSay('How does it feel?', 0.9, 0.85);

  const pulsar = song.overlay.querySelector('.annie-pulsar').getContext('2d');
  const tick = () => {
    if (annie !== song) return;
    const elapsed = ctx.currentTime - start;
    if (!song.ending) line.textContent = ANNIE_SHOUTS[Math.max(0, Math.floor(elapsed / beat / 4)) % ANNIE_SHOUTS.length];
    annieDraw(pulsar, elapsed, 1 - ((elapsed / beat) % 1));
    song.frame = requestAnimationFrame(tick);
  };
  song.frame = requestAnimationFrame(tick);
}

// Stacked lines, each peaked in the middle; drawn top down, each one filled
// black underneath so it hides the lines behind it.
function annieDraw(g, t, pulse) {
  const { width, height } = g.canvas;
  g.fillStyle = '#000';
  g.fillRect(0, 0, width, height);
  g.strokeStyle = '#fff';
  g.lineWidth = 1;
  for (let i = 0; i < 14; i++) {
    const base = 14 + i * 4;
    g.beginPath();
    g.moveTo(0, base);
    for (let x = 0; x <= width; x += 2) {
      const middle = Math.exp(-(((x - width / 2) / (width / 7)) ** 2));
      const wiggle = Math.abs(Math.sin(x * 0.31 + i * 1.7 + t * 3) + Math.sin(x * 0.13 - i * 0.9 + t * 1.3));
      g.lineTo(x, base - middle * wiggle * (5 + pulse * 7));
    }
    g.lineTo(width, height);
    g.lineTo(0, height);
    g.closePath();
    g.fill();
    g.stroke();
  }
}

// Hit a clap and a held chord, let the band fade out under them, and name the pick.
function annieFinish(name) {
  const song = annie;
  if (!song || song.kind !== 'simulation' || song.ending) return;
  const { ctx, band, room, line } = song;
  const { kick, clap, tone } = song.kit;
  song.ending = true;
  const now = ctx.currentTime;
  band.gain.setValueAtTime(band.gain.value, now);
  band.gain.linearRampToValueAtTime(0.6, now + 0.1);
  band.gain.linearRampToValueAtTime(0, now + 6);
  kick(band, now + 0.03);
  clap(room, now + 0.03, 0.8);
  tone(room, now + 0.03, [73.4, 293.7, 349.2, 440], 5, { type: 'triangle', peak: 0.12, attack: 0.05, detunes: [-14, 0, 14] });
  line.textContent = name ? `${name}. True faith.` : 'True faith.';
  annieSay(line.textContent, 0.9, 0.85);
  setTimeout(() => { if (annie === song) annieStop(); }, 6200);
}

// Four bars of I, IV, I, V in a random key and one of three styles, then a
// last chord. Never cuts into the simulation's song.
function elvisSing(name) {
  if (annie?.kind === 'simulation') return;
  const song = annieStart('elvis', '<div class="annie-singer" aria-hidden="true">✻</div>');
  const { ctx, band, out, line } = song;
  const { hiss, kick, snare, tone } = song.kit;
  const key = 82.4 * 2 ** (Math.floor(Math.random() * 7 - 3) / 12);
  const note = semis => key * 2 ** (semis / 12);
  const triad = root => [24, 28, 31].map(s => note(root + s));
  const roots = [0, 5, 0, 7];
  const style = pickOne(['rockabilly', 'vegas', 'ballad']);
  const bpm = { rockabilly: 168, vegas: 132, ballad: 76 }[style];
  const beat = 60 / bpm;
  const bars = style === 'ballad' ? 2 : 4;
  const start = ctx.currentTime + 0.05;

  for (let bar = 0; bar < bars; bar++) {
    const t0 = start + bar * 4 * beat;
    const root = style === 'ballad' ? [0, 5][bar] : roots[bar];
    const chord = triad(root);
    if (style === 'rockabilly') {
      // Walking bass, slap-back guitar chops on two and four, a light snare.
      [0, 4, 7, 9].forEach((s, b) => tone(band, t0 + b * beat, [note(root + s)], beat, { peak: 0.4, open: 600 }));
      for (const b of [1, 3]) {
        tone(band, t0 + b * beat, chord, 0.15, { type: 'square', peak: 0.04, open: 2500, shut: 400, attack: 0.003 });
        tone(band, t0 + b * beat + 0.11, chord, 0.15, { type: 'square', peak: 0.015, open: 2000, shut: 400, attack: 0.003 });
        snare(band, t0 + b * beat, 0.3);
      }
      kick(band, t0);
      kick(band, t0 + 2 * beat);
    } else if (style === 'vegas') {
      // Kick on every beat, a crash on two and four, an eighth-note bass walk
      // and brass stabs.
      for (let b = 0; b < 4; b++) {
        kick(band, t0 + b * beat);
        if (b % 2) hiss(band, t0 + b * beat, 'highpass', 1500, 0.35, 0.12);
      }
      [0, 0, 3, 5, 7, 5, 3, -5].forEach((s, n) => tone(band, t0 + n * beat / 2, [note(root + s)], beat / 2, { peak: 0.5, open: 500 }));
      tone(band, t0 + 1.5 * beat, chord, beat * 0.4, { peak: 0.1, shut: 700, attack: 0.02, detunes: [-12, 0, 12] });
      tone(band, t0 + 3 * beat, chord, beat * 0.6, { peak: 0.1, shut: 700, attack: 0.02, detunes: [-12, 0, 12] });
    } else {
      // A slow organ chord over a soft bass, in a lilting three.
      tone(band, t0, chord, 4 * beat, { type: 'sine', peak: 0.08, attack: 0.3 });
      tone(band, t0, [note(root + 12)], 4 * beat, { type: 'triangle', peak: 0.2, open: 400, attack: 0.05 });
      for (const b of [0, 4 / 3, 8 / 3]) tone(band, t0 + b * beat, [note(root + 31)], beat, { type: 'triangle', peak: 0.04, open: 2000 });
    }
  }

  const end = start + bars * 4 * beat;
  if (style === 'ballad') tone(out, end, triad(0), 2.5, { type: 'sine', peak: 0.1, attack: 0.1 });
  else {
    kick(out, end);
    hiss(out, end, 'highpass', 1500, 0.5, 2);
    tone(out, end, [note(12), ...triad(0), note(36)], 2, { peak: 0.08, shut: 700, attack: 0.02, detunes: [-12, 0, 12] });
  }

  const said = pickOne(ELVIS_LINES);
  line.textContent = name ? `${name}. ${said}` : said;
  annieSay(name ? `${name}. ${said}` : said, 0.7, 0.85);
  const singer = song.overlay.querySelector('.annie-singer');
  const tick = () => {
    if (annie !== song) return;
    const elapsed = ctx.currentTime - start;
    const pulse = elapsed < end - start ? 1 - ((elapsed / beat) % 1) : 0;
    singer.style.transform = `scale(${1 + pulse * 0.3}) rotate(${Math.sin(elapsed * 3) * 12}deg)`;
    song.frame = requestAnimationFrame(tick);
  };
  song.frame = requestAnimationFrame(tick);
  setTimeout(() => { if (annie === song) annieStop(); }, (end - ctx.currentTime + 2.2) * 1000);
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
document.addEventListener('place-picked', event => elvisSing(event.detail));
