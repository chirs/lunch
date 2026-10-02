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
