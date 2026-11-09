#!/usr/bin/env python3
"""Refresh Xander-XGCS's compact geomagnetic-history header from observed Ap.

No image dependencies or persistent services. Consumes *only* CelesTrak's
BEGIN OBSERVED block; never plots forecast/predicted values.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE = "https://celestrak.org/SpaceData/SW-Last5Years.txt"
IMAGE_PATH = "assets/profile-geomagnetic-365d.svg"
DATA_PATH = "assets/geomagnetic-ap-daily-rolling-365.json"
SOURCE_CREDIT = 'GFZ / Matzka et al. (2021), via CelesTrak observed daily planetary Ap'
DAYS = 365
DURATION_S = 60
MAX_BYTES = 2_000_000

# The coastline is a cartographic outline in the same compact north-polar
# illustration used in the prior header, not an observed auroral footprint.
COAST = (
    "M884 98L881 94L884 96L886 94L884 92L892 91L898 85L891 93L907 95"
    "L906 92L908 90L919 92L921 89L924 98L923 94L925 96L927 92L937 104"
    "L938 100L940 110L940 105L941 108L937 118L940 131L922 152L925 152"
    "L930 146L923 160L911 161L911 156L904 160L913 152L908 152L909 149"
    "L904 154L905 157L901 160L902 162L893 158L898 161L897 163L890 160"
    "L882 165L877 165L877 161L883 161L881 157L890 153L889 150L890 153"
    "L896 150L899 144L894 146L894 141L892 151L886 146L893 136L899 136"
    "L896 138L900 139L898 134L904 127L900 124L906 126L906 123L901 123"
    "L904 121L900 122L896 116L897 113L901 114L898 106L891 99L884 98"
    " M910 161L920 162L929 155L924 161"
    " M893 176L876 176L867 172L879 166L900 166L909 161"
    " M827 128L830 106L839 98L834 101L835 99L846 94L852 98L863 98"
    "L870 93L870 95L874 87L872 92L877 92L876 95L879 96L876 97L879 99"
    "L862 112L864 113L862 117L866 118L861 120L864 122L854 116L848 125"
    "L858 125L855 139L848 132L848 139L840 129L832 128L833 112L829 113"
    "L827 128 M827 129L840 156"
    " M864 140L872 123L881 125L879 134L876 134L877 137L875 136L877 137"
    "L864 140 M939 100L935 92 M859 130L860 124L863 126L865 119L867 120"
    "L864 130L863 128L859 130"
)


def fetch_source() -> str:
    request = Request(SOURCE, headers={"User-Agent": "XGCS-Geomagnetic-Profile/1.0 (weekly historical-data reader)", "Accept": "text/plain"})
    with urlopen(request, timeout=20) as response:
        if response.status != 200 or response.geturl() != SOURCE:
            raise ValueError("Source URL redirected or HTTP status unexpected")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Source file exceeds maximum byte limit")
    return raw.decode("ascii", errors="strict")


def parse_observed(text: str) -> list[tuple[date, int]]:
    if text.count("BEGIN OBSERVED") != 1 or text.count("END OBSERVED") != 1:
        raise ValueError("Missing or duplicate observed-data boundary")
    observed = text.split("BEGIN OBSERVED", 1)[1].split("END OBSERVED", 1)[0]
    records = []
    seen = set()
    for line in observed.splitlines():
        p = line.split()
        if not p or not re.fullmatch(r"\d{4}", p[0]):
            continue
        if len(p) < 23:
            raise ValueError("Observed record has insufficient fields")
        d = date(int(p[0]), int(p[1]), int(p[2]))
        if d in seen:
            raise ValueError("Duplicate observed date")
        seen.add(d)
        # CelesTrak CSSI columns: yyyy mm dd BSRN ND [8 Kp] KpSum
        # [8 three-hour ap] daily mean Ap (zero-based token #22).
        value = int(p[22])
        ap_slots = [int(x) for x in p[14:22]]
        if not (0 <= value <= 400 and all(0 <= x <= 400 for x in ap_slots)):
            raise ValueError("Missing/sentinel/out-of-range Ap")
        if abs(sum(ap_slots) / 8 - value) > 1.01:
            raise ValueError("Daily Ap inconsistent with eight three-hour ap readings")
        records.append((d, value))
    return sorted(records)


def select_window(records: list[tuple[date, int]], today: date, days: int = DAYS) -> list[tuple[date, int]]:
    if len(records) < days:
        raise ValueError("Insufficient observed history")
    latest = records[-1][0]
    if not (0 <= (today - latest).days <= 3):
        raise ValueError("Stale or future-dated source; no profile update")
    cutoff = latest - timedelta(days=days - 1)
    window = [(d, v) for d, v in records if d >= cutoff]
    if len(window) != days or any((window[i][0] - window[i - 1][0]).days != 1 for i in range(1, days)):
        raise ValueError("Gap in observed history; no profile update")
    return window


def strength(ap: int) -> tuple[float, float, float]:
    # Saturating logarithmic visual encoding: resilient to large storm spikes.
    # Brightness/width/scale are graphic variables, NOT geographic ovals.
    x = min(1.0, math.log1p(ap) / math.log1p(100))
    return 0.21 + 0.77 * x, 1.6 + 5.6 * x, 0.82 + 0.20 * x


def make_svg(series: list[tuple[date, int]]) -> str:
    if len(series) != DAYS:
        raise ValueError("Expected 365 distinct daily records")
    start, end = series[0][0], series[-1][0]
    first, last = strength(series[0][1]), strength(series[-1][1])
    entries = []
    for i, (_, ap) in enumerate(series):
        o, w, scale = strength(ap)
        pct = (i / DAYS) * 100
        entries.append(f"{pct:.5f}%{{opacity:{o:.3f};stroke-width:{w:.3f};transform:scale({scale:.3f})}}")
    entries.append(f"100%{{opacity:{first[0]:.3f};stroke-width:{first[1]:.3f};transform:scale({first[2]:.3f})}}")
    grid = ''.join(f'<path d="M{885-60*math.cos(a*math.pi/180):.1f} {120-60*math.sin(a*math.pi/180):.1f}L{885+60*math.cos(a*math.pi/180):.1f} {120+60*math.sin(a*math.pi/180):.1f}"/>' for a in range(0, 180, 30))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="215" viewBox="0 0 1000 215" role="img" aria-labelledby="title desc">
<title id="title">Xander Gray — 365-day geomagnetic history</title>
<desc id="desc">A one-minute repeating historical display of daily planetary Ap from {start.isoformat()} through {end.isoformat()}. The auroral ring represents geomagnetic activity by brightness and thickness. It is not a measured auroral oval, an aurora forecast, or live data.</desc>
<style>
#auroral-intensity{{transform-box:view-box;transform-origin:885px 120px;animation:intensity {DURATION_S}s linear infinite}}
#orbit-marker{{transform-box:view-box;transform-origin:885px 120px;animation:orbit {DURATION_S}s linear infinite}}
@keyframes intensity{{{''.join(entries)}}}
@keyframes orbit{{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}
@media(prefers-reduced-motion:reduce){{#auroral-intensity,#orbit-marker{{animation:none!important}}}}
</style>
<defs><clipPath id="globe"><circle cx="885" cy="120" r="60"/></clipPath>
<filter id="soft" x="-45%" y="-45%" width="190%" height="190%"><feGaussianBlur stdDeviation="4.0"/></filter></defs>
<rect width="1000" height="215" fill="#080c10"/>
<path d="M18 28L28 18H972L982 28V187L972 197H28L18 187Z" fill="#0d1319" stroke="#34414d"/>
<path d="M18 18H34M18 18V34M982 18H966M982 18V34M18 197H34M18 197V181M982 197H966M982 197V181" stroke="#b8a06a" stroke-width="2" fill="none"/>
<path d="M726 35V183M48 66H686" fill="none" stroke="#344751"/>
<g font-family="Consolas,Menlo,monospace">
<text x="48" y="46" fill="#99a5af" font-size="11">PUBLIC OPERATING PROFILE / XGCS</text>
<text x="50" y="148" fill="#99a5af" font-size="12">FOUNDER &amp; CEO / SYSTEMS ARCHITECT</text>
<text x="50" y="168" fill="#99a5af" font-size="12">QUANTITATIVE RESEARCH / AGENTIC ENGINEERING</text>
<text x="742" y="41" fill="#e8edf2" font-size="11">GEOMAGNETIC / 365D</text>
<text x="742" y="55" fill="#99a5af" font-size="9">DAILY Ap / HISTORICAL</text>
<text x="742" y="189" fill="#99a5af" font-size="9">{start.strftime('%d %b %y').upper()} - {end.strftime('%d %b %y').upper()}</text>
</g>
<text x="48" y="115" fill="#e8edf2" font-family="DejaVu Sans,Arial,Helvetica,sans-serif" font-size="43" font-weight="700">XANDER GRAY</text>
<path d="M48 179H150L161 172H333" stroke="#b8a06a" stroke-width="1.4" fill="none"/>
<circle cx="885" cy="120" r="61" fill="#0a2731" stroke="#467888"/>
<g clip-path="url(#globe)" stroke="#35616d" stroke-width=".65" fill="none" opacity=".5">
<circle cx="885" cy="120" r="20"/><circle cx="885" cy="120" r="41"/>{grid}
<path d="{COAST}" stroke="#83adb5" opacity=".8" stroke-width=".8"/></g>
<g id="auroral-intensity" fill="none" stroke="#48dec0" stroke-width="{last[1]:.3f}" opacity="{last[0]:.3f}" style="transform:scale({last[2]:.3f})">
<circle cx="885" cy="120" r="48" filter="url(#soft)"/><circle cx="885" cy="120" r="48"/>
</g>
<g id="orbit-marker"><circle cx="885" cy="59" r="3" fill="#b8a06a"/></g>
</svg>
'''


def make_data(series: list[tuple[date, int]]) -> str:
    value_digest = hashlib.sha256((''.join(f'{d.isoformat()}:{ap};' for d, ap in series)).encode()).hexdigest()
    obj = {
        "metric": "daily planetary Ap (dimensionless)",
        "interval_utc": f"{series[0][0].isoformat()}/{series[-1][0].isoformat()}",
        "observation_count": len(series),
        "provider": "CelesTrak CSSI observed space-weather data (GFZ-derived geomagnetic indices)",
        "source": SOURCE,
        "citation": SOURCE_CREDIT,
        "source_selected_values_sha256": value_digest,
        "interpretation": "Auroral ring is a graphic intensity encoding of observed Ap, not an actual auroral footprint or live data.",
        "loop_seconds": DURATION_S,
        "observations": [{"date": d.isoformat(), "Ap": ap} for d, ap in series],
    }
    return json.dumps(obj, indent=2, ensure_ascii=False) + '\n'


def update_readme(text: str, series: list[tuple[date, int]]) -> str:
    a, b = series[0][0], series[-1][0]
    img = f'<img src="{IMAGE_PATH}" alt="Xander Gray. Stylized daily planetary Ap geomagnetic history, {a.isoformat()} through {b.isoformat()}, 365 observed days in a 60-second animation; not a real auroral-oval observation or live data." width="100%">'
    old_header = r'^<img src="assets/profile-geomagnetic-(?:90d|365d)\.svg" alt="[^"]+" width="100%">'
    updated, count = re.subn(old_header, lambda _: img, text, count=1)
    if count != 1:
        raise ValueError('Expected existing profile image at top of README')
    attribution = (f'<sub>The 60-second loop represents 365 **observed daily planetary Ap** values from '
                   f'{a.strftime("%d %B %Y")} through {b.strftime("%d %B %Y")}. '
                   f'Data source: <a href="{SOURCE}">CelesTrak observed space-weather history</a>, '
                   f'derived from <a href="https://kp.gfz.de/en/data">GFZ geomagnetic indices</a>. '
                   f'Credit: Matzka et al. (2021), <a href="https://doi.org/10.1029/2020SW002641">'
                   f'The geomagnetic Kp index and derived indices of geomagnetic activity</a>, CC BY 4.0. '
                   f'<a href="{DATA_PATH}">View 365 source values and method</a>. '
                   'The moving glow is a **stylized intensity indicator**, not a measured auroral footprint, '
                   'an official aurora forecast, or a live feed. Recent measurements can be revised; '
                   'the historical window updates weekly. Reduced-motion preferences disable animation.</sub>')
    footer_regex = r'(<details>\s*<summary><sub>Earth-state visualization data and methodology</sub></summary>\s*)<sub>.*?</sub>(\s*</details>)'
    updated, count = re.subn(footer_regex, lambda m: m.group(1) + attribution + m.group(2), updated, count=1, flags=re.S)
    if count != 1:
        raise ValueError('Expected one existing scientific attribution footer')
    return updated


def build(repo: Path, source_text: str, today: date) -> tuple[str, str, str]:
    series = select_window(parse_observed(source_text), today)
    svg = make_svg(series)
    data = make_data(series)
    current = (repo / 'README.md').read_text(encoding='utf-8')
    readme = update_readme(current, series)
    return svg, data, readme


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    svg, data, readme = build(repo, fetch_source(), datetime.now(timezone.utc).date())
    for relative, content in [(IMAGE_PATH, svg), (DATA_PATH, data), ('README.md', readme)]:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_text(encoding='utf-8') != content:
            path.write_text(content, encoding='utf-8')
            print('Updated', relative)
        else:
            print('Unchanged', relative)


if __name__ == '__main__':
    main()
