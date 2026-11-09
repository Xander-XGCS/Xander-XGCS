import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import parse_observed, select_window, make_svg, make_data, update_readme, build

TODAY = date(2026, 11, 9)


def fixture(n=370, last=date(2026, 11, 8), gaps=(), bad=False):
    lines = ["DATATYPE CssiSpaceWeather", "BEGIN OBSERVED"]
    for i in range(n):
        day = last - timedelta(days=n - i - 1)
        if day in gaps: continue
        value = 4 + (i % 30)
        if bad and i == n - 1: value = 999
        ap = ' '.join([str(value)] * 8)
        lines.append(f'{day.year:04d} {day.month:02d} {day.day:02d} 1 1 ' + ' '.join(['10']*8) + ' 80 ' + ap + f' {value} 0.0 0 0 0')
    lines.append('END OBSERVED')
    lines += ['BEGIN DAILY_PREDICTED', '2026 11 09 forecast only', 'END DAILY_PREDICTED']
    return '\n'.join(lines)


README = '''<img src="assets/profile-geomagnetic-90d.svg" alt="Old data" width="100%">

## Mission

## Current Operations

<details>
<summary><sub>Earth-state visualization data and methodology</sub></summary>

<sub>Old attribution</sub>

</details>
'''

class BuildTests(unittest.TestCase):
    def test_observed_not_predicted(self):
        rows = parse_observed(fixture())
        self.assertEqual(len(rows), 370)
        self.assertEqual(rows[-1][0], date(2026, 11, 8))

    def test_window_exact_365(self):
        out = select_window(parse_observed(fixture()), TODAY)
        self.assertEqual(len(out), 365)
        self.assertEqual(out[-1][0], TODAY - timedelta(days=1))
        self.assertEqual((out[-1][0]-out[0][0]).days, 364)

    def test_fails_closed_on_stale_and_gap(self):
        with self.assertRaisesRegex(ValueError, 'Stale'):
            select_window(parse_observed(fixture(last=date(2026, 11, 1))), TODAY)
        with self.assertRaisesRegex(ValueError, 'Gap'):
            select_window(parse_observed(fixture(gaps={date(2026, 11, 4)})), TODAY)

    def test_rejects_outlier_or_prediction_only(self):
        with self.assertRaises(ValueError):
            parse_observed(fixture(bad=True))
        with self.assertRaisesRegex(ValueError, 'boundary'):
            parse_observed('BEGIN DAILY_PREDICTED\n2026 11 09 42\nEND DAILY_PREDICTED')

    def test_svg_365_values_and_minute(self):
        obs = select_window(parse_observed(fixture()), TODAY)
        svg = make_svg(obs)
        self.assertTrue('animation:intensity 60s' in svg)
        self.assertEqual(svg.count('%{opacity:'), 366)
        self.assertLess(len(svg.encode('utf-8')), 125000)
        self.assertIn('prefers-reduced-motion', svg)
        data = make_data(obs)
        self.assertIn('"observation_count": 365', data)

    def test_readme_preserves_sections_and_is_idempotent(self):
        obs = select_window(parse_observed(fixture()), TODAY)
        r1 = update_readme(README, obs)
        r2 = update_readme(r1, obs)
        self.assertEqual(r1, r2)
        self.assertIn('## Current Operations', r1)
        self.assertIn('365 **observed daily planetary Ap**', r1)
        self.assertTrue(r1.startswith('<img src="assets/profile-geomagnetic-365d.svg"'))

    def test_build_leaves_repository_contents_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'README.md').write_text(README, encoding='utf-8')
            svg, data, readme = build(root, fixture(), TODAY)
            self.assertIn('365-day geomagnetic history', svg)
            self.assertIn('2026-11-08', data)
            self.assertIn('geomagnetic-365d.svg', readme)
            self.assertEqual((root/'README.md').read_text(encoding='utf-8'),README)

if __name__ == '__main__': unittest.main()
