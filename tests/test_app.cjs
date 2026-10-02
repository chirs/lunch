const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const app = vm.createContext({
  document: { documentElement: {} },
  getComputedStyle: () => ({ getPropertyValue: () => '' }),
  fetch: () => new Promise(() => {}),
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../www/app.js'), 'utf8'), app);

function status(hours, instant) {
  app.hours = hours;
  app.instant = instant;
  return app.openStatus(hours, vm.runInContext('new Date(instant)', app));
}

for (const zone of ['America/Chicago', 'America/Los_Angeles', 'Asia/Tokyo']) {
  test(`Dallas hours and weekday from ${zone}`, () => {
    const previous = process.env.TZ;
    process.env.TZ = zone;
    try {
      const lunch = Array(7).fill('1100-1400');
      for (const instant of ['2026-10-01T17:00:00Z', '2026-01-15T18:00:00Z']) {
        assert.equal(status(lunch, instant).text, 'Open until 2 PM');
      }
      assert.equal(status(lunch, '2026-10-01T15:59:00Z').open, false);
      assert.equal(status(lunch, '2026-10-01T16:00:00Z').open, true);
      assert.equal(status(lunch, '2026-10-01T19:00:00Z').open, false);

      const weekend = ['', '', '', '', '', '', '1700-0200'];
      assert.equal(status(weekend, '2026-10-04T04:30:00Z').open, true);
      assert.equal(status(weekend, '2026-10-04T06:30:00Z').open, true);
      assert.equal(status(weekend, '2026-10-04T07:00:00Z').open, false);
      app.instant = '2026-10-04T04:30:00Z';
      assert.equal(vm.runInContext('dallasTime(new Date(instant)).today', app), 6);
      app.instant = '2026-10-04T05:00:00Z';
      assert.equal(vm.runInContext('dallasTime(new Date(instant)).minute', app), 0);
      assert.equal(vm.runInContext('dallasTime(new Date(instant)).today', app), 0);

      const sunday = ['0100-0300', '', '', '', '', '', ''];
      assert.equal(status(sunday, '2026-03-08T07:59:00Z').open, true);
      assert.equal(status(sunday, '2026-03-08T08:00:00Z').open, false);
      assert.equal(status(sunday, '2026-11-01T06:30:00Z').open, true);
      assert.equal(status(sunday, '2026-11-01T07:30:00Z').open, true);
    } finally {
      if (previous === undefined) delete process.env.TZ;
      else process.env.TZ = previous;
    }
  });
}

test('unlisted and always-open hours', () => {
  assert.equal(status(undefined, '2026-10-01T17:00:00Z'), null);
  assert.equal(status(Array(7).fill('0000-2400'), '2026-10-01T17:00:00Z').text, 'Open 24 hours');
});

function fits(hours, departure, minutes = 10, meal = 45) {
  return app.fitsLunch({ hours, minutes }, meal, new Date(departure));
}

test('lunch starts on arrival and must finish by closing', () => {
  const hours = Array(7).fill('1100-1400');
  assert.equal(fits(hours, '2026-10-01T10:50:00-05:00'), true);
  assert.equal(fits(hours, '2026-10-01T10:49:00-05:00'), false);
  assert.equal(fits(hours, '2026-10-01T13:05:00-05:00'), true);
  assert.equal(fits(hours, '2026-10-01T13:05:01-05:00'), false);
  assert.equal(fits(hours, '2026-10-01T13:05:00-05:00', 10.1), false);
  assert.equal(fits(hours, '2026-10-01T13:04:54-05:00', 10.1), true);
  assert.equal(fits(hours, '2026-10-01T13:15:00-05:00', 10, 30), true);
  assert.equal(fits(hours, '2026-10-01T13:15:00-05:00', 10, 45), false);
  assert.equal(fits(hours, '2026-10-01T13:50:00-05:00'), false);
});

test('lunch cannot bridge a break in service', () => {
  const hours = Array(7).fill('1100-1200,1230-1500');
  assert.equal(fits(hours, '2026-10-01T11:35:00-05:00'), false);
  assert.equal(fits(hours, '2026-10-01T12:20:00-05:00'), true);
  assert.equal(fits(Array(7).fill('1100-1200,1200-1500'), '2026-10-01T11:35:00-05:00'), true);
});

test('lunch spans midnight, the week boundary and consecutive full days', () => {
  const overnight = ['', '', '', '', '', '', '1700-0200'];
  assert.equal(fits(overnight, '2026-10-03T23:30:00-05:00'), true);
  assert.equal(fits(overnight, '2026-10-04T01:10:00-05:00'), false);
  const fullDays = ['0000-2400', '', '', '', '', '0000-2400', '0000-2400'];
  assert.equal(fits(fullDays, '2026-10-03T23:30:00-05:00'), true);
  assert.equal(fits(fullDays, '2026-10-04T23:30:00-05:00'), false);
});

test('lunch excludes unknown hours and allows always-open places', () => {
  assert.equal(fits(undefined, '2026-10-01T12:00:00-05:00'), false);
  assert.equal(fits(Array(7).fill(''), '2026-10-01T12:00:00-05:00'), false);
  assert.equal(fits(Array(7).fill('0000-2400'), '2026-10-01T23:30:00-05:00', 23, 60), true);
});

test('meal duration measures elapsed time across daylight-saving changes', () => {
  assert.equal(fits(['0100-0300', '', '', '', '', '', ''], '2026-03-08T01:30:00-06:00'), false);
  assert.equal(fits(['0100-0200', '', '', '', '', '', ''], '2026-11-01T01:30:00-05:00'), true);
  assert.equal(fits(['0130-0200', '', '', '', '', '', ''], '2026-11-01T01:30:00-05:00'), false);
});

test('shortlist eligibility never falls back to unshortlisted places', () => {
  const open = { id: 'open', minutes: 10, hours: Array(7).fill('1100-1400') };
  const closed = { id: 'closed', minutes: 10, hours: Array(7).fill('1700-2200') };
  const unknown = { id: 'unknown', minutes: 10 };
  const all = [open, closed, unknown];
  const now = new Date('2026-10-01T12:00:00-05:00');
  const none = app.lunchPool(all, all, new Set(['closed', 'unknown']), 45, now);
  assert.equal(none.places.length, 0);
  assert.equal(none.source, 'shortlisted');
  assert.equal(none.total, 2);
  assert.equal(none.unknown, 1);
  const one = app.lunchPool(all, [], new Set(['open', 'closed']), 45, now);
  assert.equal(one.places.length, 1);
  assert.equal(one.places[0], open);
  const filtered = app.lunchPool(all, [closed], new Set(['open']), 45, now);
  assert.equal(filtered.places.length, 0);
  assert.equal(filtered.source, 'filtered');
  const visible = app.lunchPool(all, [open], new Set(), 45, now);
  assert.equal(visible.places[0], open);
  assert.equal(app.lunchPool(all, [open], new Set(), 45, new Date('2026-10-01T14:00:00-05:00')).places.length, 0);
});

test('search ranks name starts, then word starts, then the rest', () => {
  const places = [
    { name: 'The Hong Kong Café', score: 4.6 },
    { name: 'Hong Dumpling', score: 4.2 },
    { name: 'Thong Bistro', score: 4.9 },
    { name: 'Hong Kong Express', score: 4.4 },
  ];
  const names = query => Array.from(app.searchPlaces(places, query), p => p.name);
  assert.deepEqual(names('hong'), ['Hong Kong Express', 'Hong Dumpling', 'The Hong Kong Café', 'Thong Bistro']);
  assert.deepEqual(names('  HONG kong '), ['Hong Kong Express', 'The Hong Kong Café']);
  assert.deepEqual(names(''), []);
  assert.deepEqual(names('pizza'), []);
});

test('search ignores accents and apostrophes', () => {
  const places = [{ name: 'Taquería El Juárez', score: 4.5 }, { name: "Joe's Crab-Shack", score: 4.1 }];
  const names = query => Array.from(app.searchPlaces(places, query), p => p.name);
  assert.deepEqual(names('juarez'), ['Taquería El Juárez']);
  assert.deepEqual(names('joes crab shack'), ["Joe's Crab-Shack"]);
});
