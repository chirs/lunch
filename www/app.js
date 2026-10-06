// Lunch Simulator. The data is places.json, which update.py writes.

const TIER_RADIUS = [5, 6.5, 8];
const SHORTLIST_KEY = 'lunch-shortlist';
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const DALLAS_CLOCK = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago', weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});
// Score at or above each cut moves a place up a tier. Tiers and the quality
// slider compare the score as displayed, rounded to one decimal. The cuts
// come from places.json, where update.py sizes them to the data.
let tierCuts = [4.3, 4.5];
// The longest drive in the data, in minutes. Also from places.json.
let maxMinutes = 20;

const $ = id => document.getElementById(id);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const theme = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const tierColors = [0, 1, 2].map(n => theme(`--tier-${n}`));

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function button(label, className = 'button') {
  const node = el('button', className, label);
  node.type = 'button';
  return node;
}

function link(label, href, className = 'button') {
  const a = el('a', className, label);
  a.href = href;
  a.target = '_blank';
  a.rel = 'noopener';
  return a;
}

function shownScore(place) {
  return Number(place.score.toFixed(1));
}

function tier(place) {
  return tierCuts.filter(cut => shownScore(place) >= cut).length;
}

function minutesText(place) {
  if (!Number.isFinite(place.minutes)) return 'No route';
  return `${Math.max(1, Math.round(place.minutes))} min`;
}

function meta(place) {
  return [place.cuisine, place.price, minutesText(place)].filter(Boolean).join(' · ');
}

function visitedText(place) {
  if (place.visited === true) return '✓ Visited';
  const [year, month, day] = place.visited.split('-').map(Number);
  const date = new Date(year, month - 1, day);
  return `✓ Visited ${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`;
}

// "1430" -> "2:30 PM"
function clock(hhmm) {
  const hour = Number(hhmm.slice(0, 2)) % 24, minute = hhmm.slice(2);
  if (minute === '00' && hour === 0) return 'midnight';
  if (minute === '00' && hour === 12) return 'noon';
  return `${hour % 12 || 12}${minute === '00' ? '' : `:${minute}`} ${hour < 12 ? 'AM' : 'PM'}`;
}

// One day's "1100-1400,1700-0200" as minute ranges. A range that ends at or
// before its start runs past midnight, so its end lands beyond 1440.
function ranges(day) {
  if (!day) return [];
  return day.split(',').map(range => {
    const [from, to] = range.split('-');
    const start = Number(from.slice(0, 2)) * 60 + Number(from.slice(2));
    let end = Number(to.slice(0, 2)) * 60 + Number(to.slice(2));
    if (end <= start) end += 1440;
    return { start, end, from, to };
  });
}

function dayText(day) {
  if (day === '0000-2400') return 'Open 24 hours';
  return ranges(day).map(r => `${clock(r.from)} to ${clock(r.to)}`).join(', ') || 'Closed';
}

function dallasTime(now = new Date()) {
  const parts = Object.fromEntries(DALLAS_CLOCK.formatToParts(now).map(part => [part.type, part.value]));
  return { today: DAYS.indexOf(parts.weekday), minute: Number(parts.hour) * 60 + Number(parts.minute) };
}

function openStatus(hours, now = new Date()) {
  if (!hours) return null;
  if (hours.every(day => day === '0000-2400')) return { open: true, text: 'Open 24 hours' };
  const { today, minute } = dallasTime(now);
  // Yesterday's late range may still be running.
  for (const [back, shift] of [[0, 0], [1, 1440]]) {
    const running = ranges(hours[(today - back + 7) % 7])
      .find(r => r.start <= minute + shift && minute + shift < r.end);
    if (running) return { open: true, text: `Open until ${clock(running.to)}` };
  }
  for (let ahead = 0; ahead < 7; ahead++) {
    const day = (today + ahead) % 7;
    const next = ranges(hours[day]).find(r => ahead > 0 || r.start > minute);
    if (!next) continue;
    const when = ahead === 0 ? '' : ahead === 1 ? ' tomorrow' : ` ${DAYS[day]}`;
    return { open: false, text: `Closed, opens ${clock(next.from)}${when}` };
  }
  return { open: false, text: 'Closed' };
}

function fitsLunch(place, mealMinutes, now = new Date(), clockTimes = new Map()) {
  if (!place.hours || !Number.isFinite(place.minutes)) return false;
  const schedule = place.hours.map(ranges);
  const arrival = now.getTime() + place.minutes * 60000;
  const finish = arrival + mealMinutes * 60000;
  // Hours change on minute boundaries. Check every occupied minute, using
  // elapsed time so a meal can cross midnight or a daylight-saving change.
  for (let time = Math.floor(arrival / 60000) * 60000; time < finish; time += 60000) {
    if (!clockTimes.has(time)) clockTimes.set(time, dallasTime(new Date(time)));
    const { today, minute } = clockTimes.get(time);
    const contains = (periods, at) => periods.some(r => r.start <= at && at < r.end);
    if (!contains(schedule[today], minute) && !contains(schedule[(today + 6) % 7], minute + 1440)) return false;
  }
  return true;
}

function lunchPool(places, shown, shortlist, mealMinutes, now = new Date()) {
  const starred = places.filter(p => shortlist.has(p.id));
  const candidates = starred.length >= 2 ? starred : shown;
  const clockTimes = new Map();
  return {
    places: candidates.filter(p => fitsLunch(p, mealMinutes, now, clockTimes)),
    source: starred.length >= 2 ? 'shortlisted' : 'filtered',
    total: candidates.length,
    unknown: candidates.filter(p => !p.hours).length,
  };
}

function stat(label, fraction, value, className = '') {
  const term = el('dt', '', label), detail = el('dd');
  const bar = el('span', `bar ${className}`), fill = el('i');
  fill.style.width = `${Math.round(Math.max(0, Math.min(1, fraction)) * 100)}%`;
  bar.append(fill);
  detail.append(bar, el('span', 'value', value));
  return [term, detail];
}

function stats(place) {
  const list = el('dl', 'stats');
  list.append(
    ...stat('Quality', (place.score - 3.5) / 1.5, place.score.toFixed(1), `tier-${tier(place)}`),
    ...stat('Drive', (maxMinutes - place.minutes) / maxMinutes, minutesText(place)),
    // Review counts run from 20 to tens of thousands, so the bar is logarithmic.
    ...stat('Reviews', Math.max(0.05, (Math.log10(place.reviews) - 1.3) / 2.7), place.reviews.toLocaleString()),
    ...stat('Price', place.price ? place.price.length / 4 : 0, place.price || 'Not listed'),
  );
  return list;
}

function breakdown(place, average) {
  const google = `Google ${place.rating.toFixed(1)} from ${place.reviews.toLocaleString()} reviews`;
  if (place.my_rating) return `Your rating is ${place.my_rating.toFixed(1)}. ${google}.`;
  return `${google}, pulled toward the area average of ${average.toFixed(1)}.`;
}

function weekTable(hours, today) {
  const details = el('details', 'week');
  const table = el('table');
  hours.forEach((day, n) => {
    const row = el('tr', n === today ? 'today' : '');
    row.append(el('td', '', DAYS[n]), el('td', '', dayText(day)));
    table.append(row);
  });
  details.append(el('summary', '', 'Hours this week'), table);
  return details;
}

function directionsUrl(place, base) {
  return 'https://www.google.com/maps/dir/?api=1' +
    `&origin=${base.lat},${base.lon}` +
    `&destination=${encodeURIComponent(place.name + ', ' + place.address)}` +
    (place.id ? `&destination_place_id=${place.id}` : '');
}

// Points every place's minutes at one base, and marks the branch of each name
// nearest to it; farther branches of the same name stay out of the list unless
// hand-annotated, as update.py does for a single base.
function useBase(places, base) {
  const nearest = new Map();
  for (const p of places) {
    p.minutes = p.drive[base] ?? Infinity;
    const best = nearest.get(p.name);
    if (!best || p.minutes < best.minutes) nearest.set(p.name, p);
  }
  for (const p of places) {
    p.branch = nearest.get(p.name) === p || Boolean(p.notes || p.my_rating || p.my_cuisine || p.visited);
  }
}

// visit.py ignores punctuation when matching, so drop what a shell would trip on.
function visitCommand(place) {
  return `./visit.py "${place.name.replace(/["$\`\\!]/g, '')}" --date today`;
}

// Lowercase, accents and apostrophes dropped, other punctuation as spaces, so
// "taqueria" finds "Taquería" and "joes" finds "Joe's".
function fold(text) {
  return text.normalize('NFD').replace(/[\u0300-\u036f'’]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ').trim();
}

// Places whose name holds the query: names starting with it first, then names
// with a word starting with it, then the rest; best score first within each.
function searchPlaces(places, query) {
  const q = fold(query);
  if (!q) return [];
  const rank = name => name.startsWith(q) ? 0 : ` ${name}`.includes(` ${q}`) ? 1 : name.includes(q) ? 2 : -1;
  return places.map(p => ({ p, r: rank(fold(p.name)) }))
    .filter(({ r }) => r >= 0)
    .sort((a, b) => a.r - b.r || b.p.score - a.p.score)
    .map(({ p }) => p);
}

function weightedPick(pool) {
  // Squaring the margin over 3.0 makes a 4.8 about twice as likely as a 4.3.
  const weights = pool.map(p => Math.max(0.1, p.score - 3) ** 2);
  let roll = Math.random() * weights.reduce((a, b) => a + b, 0);
  return pool.find((p, n) => (roll -= weights[n]) < 0) ?? pool.at(-1);
}

function loadShortlist() {
  try {
    return new Set(JSON.parse(localStorage.getItem(SHORTLIST_KEY)) ?? []);
  } catch {
    return new Set();
  }
}

function saveShortlist(shortlist) {
  try {
    localStorage.setItem(SHORTLIST_KEY, JSON.stringify([...shortlist]));
  } catch {
    // Private windows can refuse storage; the shortlist then lasts until reload.
  }
}

function start({ office, home, places, updated, tier_cuts, max_minutes, cuisine_groups = {} }) {
  if (tier_cuts) tierCuts = tier_cuts;
  if (max_minutes) maxMinutes = max_minutes;
  $('time').max = $('time-min').max = maxMinutes;
  places = places.filter(p => !p.hidden);
  for (const p of places) p.drive = { office: p.minutes, home: p.home_minutes };
  const bases = { office, home };
  for (const p of places) p.group = cuisine_groups[p.cuisine] ?? 'Other';
  const average = places.reduce((sum, p) => sum + p.rating, 0) / places.length;
  const shortlist = loadShortlist();
  // Which cuisines belong to each group, for the checklist.
  const members = {};
  for (const p of places) (members[p.group] ??= new Set()).add(p.cuisine);
  for (const group in members) members[group] = [...members[group]];
  const state = {
    cuisines: new Set(), prices: new Set(), expanded: new Set(),
    base: 'office', show: '', sort: 'score', query: '', inView: false, open: null, shown: [], simulating: false,
  };

  const map = L.map('map', { preferCanvas: true, zoomControl: false });
  L.control.zoom({ position: 'topright' }).addTo(map);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  const pins = L.layerGroup().addTo(map);
  // One pin for the base the drive times are from.
  const basePins = {};
  for (const name in bases) {
    const base = bases[name];
    basePins[name] = L.marker([base.lat, base.lon], {
      icon: L.divIcon({ className: '', html: '<div class="office-pin"></div>', iconSize: [18, 18] }),
      zIndexOffset: 1000,
    }).bindTooltip(`${base.name}: ${base.address}`);
  }
  basePins.office.addTo(map);
  // Marks the open restaurant, and jumps around during a simulation.
  const cursor = L.marker([office.lat, office.lon], {
    icon: L.divIcon({ className: '', html: '<div class="cursor"></div>', iconSize: [34, 34] }),
    interactive: false,
    zIndexOffset: 900,
  });

  function rowFor(place) {
    const row = el('li');
    row.tabIndex = 0;
    // Left: what it is. Right: the numbers, with price and drive under the score.
    const main = el('div', 'row-main'), side = el('div', 'row-side');
    main.append(el('div', 'name', place.name), el('div', 'meta', place.cuisine));
    if (place.visited) main.append(el('div', 'visited-line', visitedText(place)));
    if (place.notes) main.append(el('div', 'notes', place.notes));
    const score = el('div', 'score', place.score.toFixed(1));
    score.prepend(el('span', `dot tier-${tier(place)}`));
    side.append(score, el('div', 'meta', [place.price, minutesText(place)].filter(Boolean).join(' · ')));
    const columns = el('div', 'row');
    columns.append(main, side);
    row.append(columns);
    return row;
  }

  // Rows show the drive from the current base, so they are rebuilt on a switch.
  function buildRow(p) {
    p.row = rowFor(p);
    markStar(p);
    p.row.addEventListener('click', () => openCard(p));
    p.row.addEventListener('keydown', event => {
      if (event.key === 'Enter') openCard(p);
    });
  }

  function markStar(place) {
    place.row.querySelector('.name').textContent = (shortlist.has(place.id) ? '★ ' : '') + place.name;
  }

  for (const p of places) {
    p.marker = L.circleMarker([p.lat, p.lon], {
      radius: TIER_RADIUS[tier(p)], color: theme(p.visited ? '--pin-visited' : '--pin-ring'), weight: 2,
      fillColor: tierColors[tier(p)], fillOpacity: 1,
    });
    p.marker.bindTooltip(() => {
      const tip = el('div');
      tip.append(el('div', 'name', p.name), el('div', 'meta', `${meta(p)} · ${p.score.toFixed(1)}`));
      return tip;
    }, { direction: 'top', offset: [0, -TIER_RADIUS[tier(p)] - 2], className: 'pin-tip' });
    p.marker.on('click', () => openCard(p));
  }
  useBase(places, state.base);
  for (const p of places) buildRow(p);

  function showCard(...content) {
    const top = el('div', 'card-top');
    const back = button('← Back to list', 'ghost');
    back.addEventListener('click', closeCard);
    top.append(back);
    $('card').replaceChildren(top, ...content);
    $('card').scrollTop = 0;
    $('card').hidden = false;
    $('list').hidden = true;
    $('panel').classList.add('card-open');
  }

  function closeCard() {
    if (state.simulating) return;
    const last = state.open;
    state.open = null;
    $('card').hidden = true;
    $('list').hidden = false;
    $('panel').classList.remove('card-open');
    cursor.remove();
    document.querySelectorAll('#list li.selected').forEach(li => li.classList.remove('selected'));
    if (last?.row.isConnected) {
      last.row.classList.add('selected');
      last.row.scrollIntoView({ block: 'nearest' });
    }
  }

  function openCard(place, banner) {
    state.open = place;
    const now = new Date();

    const headline = el('div', 'headline');
    if (banner) headline.append(el('p', 'banner', banner));
    headline.append(el('h2', '', place.name), el('p', 'meta', meta(place)));
    const status = openStatus(place.hours, now);
    const chip = el('span', `chip ${status?.open ? 'open' : ''}`, status?.text ?? 'Hours not listed');
    chip.prepend(el('i'));
    headline.append(chip);
    const mealNote = el('p', 'meta');
    mealNote.id = 'meal-note';
    headline.append(mealNote);

    const actions = el('div', 'actions');
    actions.append(link('Directions', directionsUrl(place, bases[state.base]), 'button primary'));
    if (place.maps) actions.append(link('Google Maps', place.maps));
    if (place.url) actions.append(link('Website', place.url));

    const star = button('');
    const labelStar = () => {
      star.textContent = shortlist.has(place.id) ? '★ Shortlisted' : '☆ Shortlist';
      star.setAttribute('aria-pressed', shortlist.has(place.id));
    };
    star.addEventListener('click', () => {
      if (!shortlist.delete(place.id)) shortlist.add(place.id);
      saveShortlist(shortlist);
      labelStar();
      markStar(place);
      render();
    });
    labelStar();

    const command = el('div', 'command box');
    command.hidden = true;
    const log = button('Log a visit');
    log.addEventListener('click', () => {
      // Show the command straight away; the clipboard can refuse or stall.
      const text = visitCommand(place);
      const lead = el('span', '', 'Run this in the lunch repo:');
      command.replaceChildren(lead, el('code', '', text));
      command.hidden = false;
      navigator.clipboard?.writeText(text).then(
        () => { lead.textContent = 'Copied. Paste it in a terminal in the lunch repo:'; },
        () => {});
    });
    actions.append(star, log);

    const rest = [];
    if (place.visited) rest.push(el('p', 'visited-line', visitedText(place)));
    if (place.notes) rest.push(el('p', 'box', place.notes));
    if (place.hours) rest.push(weekTable(place.hours, dallasTime(now).today));

    showCard(headline, stats(place), el('p', 'breakdown', breakdown(place, average)), actions, command, ...rest);
    const spot = [place.lat, place.lon];
    cursor.setLatLng(spot).addTo(map);
    map.panInside(spot, { padding: [48, 48] });
    updateLunch();
  }

  function updateLunch() {
    const now = new Date(), meal = Number($('meal-duration').value);
    const choice = lunchPool(places, state.shown, shortlist, meal, now);
    $('counts').textContent = `${choice.places.length} of ${choice.total} ${choice.source} fit lunch` +
      (choice.unknown ? ` · ${choice.unknown} without hours` : '');
    $('simulate').disabled = state.simulating || choice.places.length === 0;
    $('meal-duration').disabled = state.simulating;
    if (state.open && $('meal-note')) {
      $('meal-note').textContent = !state.open.hours ? 'Hours not listed; excluded from lunch picks.'
        : fitsLunch(state.open, meal, now) ? `Time for a ${meal} min meal after your ${minutesText(state.open)} drive.`
        : `Not enough open time for a ${meal} min meal after your drive.`;
    }
    return choice;
  }

  async function simulate() {
    if (state.simulating) return;
    const { places: candidates, source } = updateLunch();
    if (!candidates.length) return;
    let winner = weightedPick(candidates);
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (candidates.length > 1 && !still) {
      state.simulating = true;
      updateLunch();
      const body = el('div', 'simulating');
      const name = el('div', 'name'), detail = el('div', 'meta');
      body.append(el('p', 'banner', `Choosing from ${candidates.length} ${source}`), name, detail);
      state.open = null;
      showCard(body);
      // Leave the map alone if every candidate is already on it. Otherwise
      // frame just the candidates, which is as far out as it needs to go.
      const candidateBox = L.latLngBounds(candidates.map(p => [p.lat, p.lon]));
      if (!map.getBounds().contains(candidateBox)) {
        map.fitBounds(candidateBox, { padding: [24, 24], maxZoom: 15, animate: false });
      }
      const steps = 16;
      for (let step = 0; step < steps; step++) {
        const p = step === steps - 1 ? winner : candidates[Math.floor(Math.random() * candidates.length)];
        cursor.setLatLng([p.lat, p.lon]).addTo(map);
        name.textContent = p.name;
        detail.textContent = meta(p);
        await sleep(60 + step * step * 1.1);
      }
      await sleep(350);
      state.simulating = false;
    }
    const now = new Date(), meal = Number($('meal-duration').value), clockTimes = new Map();
    const eligible = candidates.filter(p => fitsLunch(p, meal, now, clockTimes));
    if (!eligible.includes(winner)) winner = weightedPick(eligible);
    document.dispatchEvent(new CustomEvent('lunch-decided', { detail: winner?.name }));
    if (winner) openCard(winner, 'Simulation complete. Lunch is at');
    else {
      state.open = null;
      cursor.remove();
      showCard(el('p', 'box', 'No places still fit lunch. Try a shorter meal or different places.'));
    }
    updateLunch();
  }

  // Colors the stretch of a slider's track that is selected, as fractions of
  // its length. A thumb's center stops half a thumb short of each end of the
  // track, so the fill follows that, except where it runs out to the very end.
  function fillTrack(input, from, to) {
    const fill = input.parentElement.querySelector('.fill');
    const inset = fraction => `calc(var(--thumb) / 2 + ${fraction} * (100% - var(--thumb)))`;
    fill.style.left = from === 0 ? '0' : inset(from);
    fill.style.right = to === 1 ? '0' : inset(1 - to);
  }

  function visible() {
    const shortest = Number($('time-min').value), longest = Number($('time').value);
    const quality = $('quality');
    const minScore = quality.value === quality.min ? null : Number(quality.value);
    $('time-value').textContent = shortest ? `${shortest} to ${longest} min` : `Up to ${longest} min`;
    $('quality-value').textContent = minScore === null ? 'Any' : `${minScore.toFixed(1)}+`;
    fillTrack($('time'), shortest / maxMinutes, longest / maxMinutes);
    fillTrack(quality, (quality.value - quality.min) / (quality.max - quality.min), 1);
    const show = {
      '': () => true,
      new: p => !p.visited,
      visited: p => Boolean(p.visited),
      shortlist: p => shortlist.has(p.id),
    }[state.show];
    return places.filter(p => p.branch &&
      p.minutes >= shortest && p.minutes <= longest &&
      (minScore === null || shownScore(p) >= minScore) && show(p) &&
      (!state.prices.size || state.prices.has(p.price)));
  }

  function check(name, count, checked, toggle, className = '') {
    const row = el('div', `check-row ${className}`), label = el('label', 'check'), input = el('input');
    input.type = 'checkbox';
    input.checked = checked;
    input.dataset.key = name + className;
    input.addEventListener('change', () => {
      toggle();
      render();
    });
    label.append(input, el('span', 'check-name', name), el('span', 'count', String(count)));
    row.append(label);
    return row;
  }

  // Names of what is ticked: a whole group by its name, otherwise the cuisines.
  function tickedNames() {
    const names = [];
    for (const [group, cuisines] of Object.entries(members)) {
      const ticked = cuisines.filter(c => state.cuisines.has(c));
      if (ticked.length === cuisines.length) names.push(group);
      else names.push(...ticked);
    }
    return names;
  }

  // The cuisine checklist: one box per group, which opens to tick single
  // cuisines. Counts follow the other filters. Nothing ticked means everything.
  function renderCuisines(inRange) {
    const counts = {}, groupCounts = {};
    for (const p of inRange) {
      counts[p.cuisine] = (counts[p.cuisine] || 0) + 1;
      groupCounts[p.group] = (groupCounts[p.group] || 0) + 1;
    }
    const commonFirst = tally => (a, b) =>
      (a === 'Other') - (b === 'Other') || (tally[b] || 0) - (tally[a] || 0) || a.localeCompare(b);

    const list = $('cuisine-list'), scroll = list.scrollTop, focused = document.activeElement?.dataset?.key;
    list.replaceChildren(...Object.keys(members).sort(commonFirst(groupCounts)).map(group => {
      const cuisines = members[group].toSorted(commonFirst(counts));
      const ticked = cuisines.filter(c => state.cuisines.has(c));
      const all = check(group, groupCounts[group] || 0, ticked.length === cuisines.length, () => {
        const add = ticked.length < cuisines.length;
        for (const c of cuisines) add ? state.cuisines.add(c) : state.cuisines.delete(c);
      });
      all.querySelector('input').indeterminate = ticked.length > 0 && ticked.length < cuisines.length;
      const block = el('div', 'check-group');
      block.append(all);
      if (cuisines.length > 1 && group !== 'Other') {
        const open = state.expanded.has(group);
        const more = button(open ? '−' : '+', 'expander');
        more.setAttribute('aria-label', `${open ? 'Hide' : 'Show'} ${group} cuisines`);
        more.setAttribute('aria-expanded', open);
        more.dataset.key = `${group} expander`;
        more.addEventListener('click', () => {
          if (!state.expanded.delete(group)) state.expanded.add(group);
          render();
        });
        all.append(more);
        if (open) {
          block.append(...cuisines.map(c => check(c, counts[c] || 0, state.cuisines.has(c), () => {
            if (!state.cuisines.delete(c)) state.cuisines.add(c);
          }, 'sub')));
        }
      }
      return block;
    }));
    list.scrollTop = scroll;
    if (focused) list.querySelector(`[data-key="${CSS.escape(focused)}"]`)?.focus();
    // The button has a fixed width, so a long selection is cut short there and
    // spelled out in full on hover.
    const names = tickedNames();
    $('cuisine-summary').textContent = !names.length ? 'All cuisines'
      : names.length > 2 ? `${names.slice(0, 2).join(', ')} +${names.length - 2}` : names.join(', ');
    $('cuisine-summary').title = names.join(', ');
    $('cuisine-clear').hidden = state.cuisines.size === 0;
  }

  const nothing = el('li', 'empty', 'Nothing matches. Loosen a filter or move the map.');
  const noName = el('li', 'empty', 'No place by that name.');

  function render() {
    // "Only what's in the map view" narrows the list, the counts and the
    // simulation, but not the pins: those stay, so panning still finds them.
    const matching = visible();
    const bounds = state.inView ? map.getBounds() : null;
    const inRange = bounds ? matching.filter(p => bounds.contains([p.lat, p.lon])) : matching;
    renderCuisines(inRange);
    const picked = p => !state.cuisines.size || state.cuisines.has(p.cuisine);
    const shown = inRange.filter(picked);
    const byTime = (a, b) => a.minutes - b.minutes;
    const byScore = (a, b) => b.score - a.score || byTime(a, b);
    shown.sort(state.sort === 'score' ? byScore : byTime);
    // A search lists matches from every place and leaves the filters, pins,
    // counts and simulation as they were.
    const found = state.query ? searchPlaces(places, state.query) : null;
    const listed = found ?? shown;
    $('list').replaceChildren(...(listed.length ? listed.map(p => p.row) : [found ? noName : nothing]));

    // Best last, so the strongest pins draw on top.
    pins.clearLayers();
    for (const p of matching.filter(picked).sort((a, b) => byScore(b, a))) pins.addLayer(p.marker);

    for (const sortButton of document.querySelectorAll('#sort button')) {
      sortButton.setAttribute('aria-pressed', sortButton.dataset.sort === state.sort);
    }
    for (const baseButton of document.querySelectorAll('#base button')) {
      baseButton.setAttribute('aria-pressed', baseButton.dataset.base === state.base);
    }
    for (const priceButton of $('prices').children) {
      priceButton.setAttribute('aria-pressed', state.prices.has(priceButton.dataset.price));
    }
    state.shown = shown;
    // What the folded-up filter bar says on a small screen.
    $('filters-summary').textContent = [
      $('time-value').textContent,
      $('quality').value === $('quality').min ? '' : $('quality-value').textContent,
      state.cuisines.size ? $('cuisine-summary').textContent : '',
      [...state.prices].sort((a, b) => a.length - b.length).join(' '),
      { new: 'not visited', visited: 'visited', shortlist: 'shortlist' }[state.show],
      state.inView ? 'map view' : '',
      state.base === 'home' ? 'from home' : '',
    ].filter(Boolean).join(' · ');
    $('summary').textContent = found
      ? `${found.length.toLocaleString()} ${found.length === 1 ? 'match' : 'matches'} · filters paused`
      : `${shown.length.toLocaleString()} of ${places.length.toLocaleString()} places`;
    updateLunch();
    return shown;
  }

  function fit(shown) {
    const base = bases[state.base];
    map.fitBounds(
      L.latLngBounds([[base.lat, base.lon], ...shown.map(p => [p.lat, p.lon])]),
      { padding: [24, 24], maxZoom: 15 },
    );
  }

  // The two drive-time thumbs stay at least a minute apart; the one being
  // dragged stops when it reaches the other.
  $('time-min').addEventListener('input', () => {
    $('time-min').value = Math.min($('time-min').value, $('time').value - 1);
    render();
  });
  $('time').addEventListener('input', () => {
    $('time').value = Math.max($('time').value, Number($('time-min').value) + 1);
    render();
  });
  // Releasing a drive-time thumb reframes the map around the result, unless
  // the list is following the map, where moving it would change the answer.
  const reframe = () => {
    const shown = render();
    if (!state.inView) fit(shown);
  };
  $('time-min').addEventListener('change', reframe);
  $('time').addEventListener('change', reframe);
  $('in-view').addEventListener('change', event => {
    state.inView = event.target.checked;
    render();
  });
  map.on('moveend', () => {
    if (state.inView) render();
  });
  $('quality').addEventListener('input', render);
  $('search').addEventListener('input', event => {
    state.query = event.target.value;
    if (!$('card').hidden) closeCard();
    render();
    $('list').scrollTop = 0;
  });
  $('search').addEventListener('keydown', event => {
    if (event.key === 'Enter' && state.query) {
      const [first] = searchPlaces(places, state.query);
      if (first) openCard(first);
    } else if (event.key === 'Escape' && state.query) {
      // Handled here so the page-wide Escape does not also close a card.
      event.stopPropagation();
      event.target.value = state.query = '';
      render();
    }
  });
  $('filters-toggle').addEventListener('click', () => {
    const open = $('panel').classList.toggle('filters-open');
    $('filters-toggle').setAttribute('aria-expanded', open);
  });
  $('cuisine-clear').addEventListener('click', () => {
    state.cuisines.clear();
    render();
  });
  for (const priceButton of $('prices').children) {
    priceButton.addEventListener('click', () => {
      const price = priceButton.dataset.price;
      if (!state.prices.delete(price)) state.prices.add(price);
      render();
    });
  }
  // A click anywhere else closes the checklist. composedPath is fixed when the
  // click starts, so it still holds after a re-render has replaced the rows.
  document.addEventListener('click', event => {
    if ($('cuisine-menu').open && !event.composedPath().includes($('cuisine-menu'))) $('cuisine-menu').open = false;
  });
  $('show').addEventListener('change', event => {
    state.show = event.target.value;
    render();
  });
  for (const sortButton of document.querySelectorAll('#sort button')) {
    sortButton.addEventListener('click', () => {
      state.sort = sortButton.dataset.sort;
      render();
      $('list').scrollTop = 0;
    });
  }
  // Switching base swaps every drive time, so rows, pins and the open card are
  // redone and the map reframes around the new answer.
  for (const baseButton of document.querySelectorAll('#base button')) {
    baseButton.addEventListener('click', () => {
      if (state.simulating || baseButton.dataset.base === state.base) return;
      basePins[state.base].remove();
      state.base = baseButton.dataset.base;
      basePins[state.base].addTo(map);
      useBase(places, state.base);
      for (const p of places) buildRow(p);
      if (state.open) openCard(state.open);
      reframe();
    });
  }
  $('simulate').addEventListener('click', simulate);
  $('meal-duration').addEventListener('change', updateLunch);
  setInterval(() => {
    if (!state.simulating) updateLunch();
  }, 60000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !state.simulating) updateLunch();
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if ($('cuisine-menu').open) $('cuisine-menu').open = false;
    else if (!$('card').hidden) closeCard();
  });

  const labels = [`under ${tierCuts[0]}`, `${tierCuts[0]} to ${tierCuts[1]}`, `${tierCuts[1]} and up`];
  $('legend').append(...labels.map((label, n) => {
    const item = el('span', '', label);
    item.prepend(el('span', `dot tier-${n}`));
    return item;
  }));
  const visited = el('span', '', 'visited');
  visited.prepend(el('span', 'dot ring'));
  $('legend').append(visited);
  $('credit').textContent =
    `Ratings: Google Maps${updated ? `, ${updated}` : ''} · Drive times: OSRM, no traffic`;

  fit(render());
}

fetch('places.json', { cache: 'no-cache' }).then(response => response.json()).then(start).catch(error => {
  console.error(error);
  $('summary').textContent = 'Could not load the places. Reload to try again.';
});
