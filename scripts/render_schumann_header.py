"""Render the existing profile header from a cited numeric Schumann snapshot.

Default use is offline and deterministic. --import-measurements accepts an
exported station series.json with its public source manifest, never a screenshot.
"""

import argparse
from datetime import datetime, timezone
from html import escape
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/schumann-snapshot.json"


def import_measurements(path):
    dataset = json.loads(path.read_text(encoding="utf-8"))
    manifest = dataset["manifest"]
    if manifest["doi"] != "10.5281/zenodo.13220677" or manifest["license"] != "CC BY 4.0":
        raise ValueError("Expected the attributed CC BY 4.0 Nagycenk measurement archive")
    series = {item["id"]: item for item in dataset["series"]}
    channels = {f"f{mode}": {p["timestamp"]: p["value"] for p in series[f"nagycenk_ez_m{mode}_frequency_hz"]["points"]}
                for mode in (1, 2, 3)}
    common = set.intersection(*(set(values) for values in channels.values()))
    complete = [stamp for stamp in common if all(values[stamp] is not None for values in channels.values())]
    latest_time = max(complete)
    day = latest_time[:10]
    samples = [{"time": stamp, **{key: values.get(stamp) for key, values in channels.items()}}
               for stamp in sorted(set.union(*(set(values) for values in channels.values()))) if stamp.startswith(day)]
    snapshot = {"schema_version": 1, "dataset": manifest["source_title"], "data_kind": "historical_measurements",
                "live": False, "station": manifest["station"], "unit": "Hz", "interval_minutes": 30,
                "source_url": manifest["source_url"], "doi": manifest["doi"], "license": manifest["license"],
                "license_url": manifest["license_url"], "attribution": manifest["attribution"],
                "observation_date": day, "latest": {"time": latest_time, **{key: values[latest_time] for key, values in channels.items()}},
                "trace_scale": "Each mode uses its own displayed-day min/max; all labels are measured Hz.",
                "source_files": manifest["files"], "samples": samples,
                "note": "Archived station observations. No interpolation, synthetic waveform, or live-feed claim. Data selected for the final recorded day."}
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def panel(snapshot, dark):
    colors = {"muted": "#99a5af" if dark else "#4c5a66", "text": "#c6ced5" if dark else "#18222b",
              "panel": "#0a1015" if dark else "#ffffff", "border": "#46535e" if dark else "#7f8b95",
              "grid": "#1d2933" if dark else "#d1d6da", "date": "#8db89f" if dark else "#2f6e52"}
    strokes = ["#72a8b8", "#b8a06a", "#b97762"] if dark else ["#336f80", "#6f5c32", "#8b4f3b"]
    focuses = ["#d7f2f7", "#f1d899", "#ffd0c2"] if dark else ["#0b4f64", "#513f19", "#6d2e1f"]
    samples = snapshot["samples"]
    if len(samples) < 2 or snapshot["live"] is not False:
        raise ValueError("Expected multiple historical measurements")
    result = ['  <g class="mono">',
              f'    <text x="748" y="94" fill="{colors["muted"]}" font-size="12" letter-spacing="1.2">SCHUMANN / NCK</text>',
              f'    <polygon points="748,107 944,107 952,115 952,203 756,203 748,195" fill="{colors["panel"]}" stroke="{colors["border"]}"/>',
              f'    <path d="M772 123V194M814 123V194M856 123V194M898 123V194M940 123V194M772 146H948M772 169H948" stroke="{colors["grid"]}"/>']
    for mode in range(1, 4):
        key, index = f"f{mode}", mode - 1
        values = [sample[key] for sample in samples if sample[key] is not None]
        if not values or not all(math.isfinite(value) for value in values):
            raise ValueError("Invalid modal frequency values")
        lo, hi = min(values), max(values)
        middle = 136 + index * 23
        result.append(f'    <text x="752" y="{137 + index * 23}" fill="{strokes[index]}" font-size="8">f{mode}</text>')
        def point(i, value):
            x = 776 + i / (len(samples) - 1) * 168
            y = middle + 8 - ((value - lo) / (hi - lo) * 16 if hi != lo else 8)
            return x, y
        segments, segment = [], []
        for i, sample in enumerate(samples):
            if sample[key] is None:
                if segment:
                    segments.append(segment)
                    segment = []
            else:
                segment.append(point(i, sample[key]))
        if segment:
            segments.append(segment)
        for segment in segments:
            points = " ".join(f"{x:.2f},{y:.2f}" for x, y in segment)
            result.append(f'    <polyline points="{points}" fill="none" stroke="{strokes[index]}" stroke-width="1.5"/>')
            result.append(f'    <polyline class="telemetry-focus channel-{chr(97+index)}" points="{points}" fill="none" stroke="{focuses[index]}" stroke-width="2.5"/>')
        latest_index = next(i for i, sample in enumerate(samples) if sample["time"] == snapshot["latest"]["time"])
        x, y = point(latest_index, snapshot["latest"][key])
        result.append(f'    <rect class="sample-node channel-{chr(97+index)}" x="{x-3.5:.2f}" y="{y-3.5:.2f}" width="7" height="7" fill="{strokes[index]}"/>')
    for mode, x, y in [(1, 748, 223), (2, 858, 223), (3, 748, 243)]:
        value = snapshot["latest"][f"f{mode}"]
        result.append(f'    <text x="{x}" y="{y}" fill="{colors["muted"]}" font-size="11">f{mode} / <tspan fill="{colors["text"]}">{value:.3f} Hz</tspan></text>')
    result.append(f'    <text x="858" y="243" fill="{colors["muted"]}" font-size="11">Ez / <tspan fill="{colors["text"]}">NCK</tspan></text>')
    stamp = datetime.fromisoformat(snapshot["latest"]["time"]).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    result.append(f'    <text x="748" y="266" fill="{colors["date"]}" font-size="9">NCK / {stamp} / ARCHIVE</text>')
    result.append('  </g>')
    return "\n".join(result)


def render():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for theme in ("dark", "light"):
        path = ROOT / "assets" / f"command-header-{theme}.svg"
        svg = path.read_text(encoding="utf-8")
        description = ("Xander Gray, founder and CEO, systems architect, and quantitative market researcher. "
                       "Three traces show measured Schumann mode frequencies in Hz from Nagycenk's Ez channel on "
                       f"{snapshot['observation_date']}. Historical CC BY 4.0 station data, not a live feed. "
                       "Channel emphasis animation does not change the underlying observations.")
        svg, count = re.subn(r'<desc id="desc">.*?</desc>', f'<desc id="desc">{escape(description)}</desc>', svg, count=1, flags=re.S)
        if count != 1:
            raise ValueError("Header description not found")
        svg, count = re.subn(r'  <g class="mono">.*?</g>', lambda _: panel(snapshot, theme == "dark"), svg, count=1, flags=re.S)
        if count != 1:
            raise ValueError("Existing header panel not found")
        path.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--import-measurements", type=Path)
    args = parser.parse_args()
    if args.import_measurements:
        import_measurements(args.import_measurements)
    render()
    print("Rendered both profile header themes from the attributed Schumann measurement snapshot.")
