# Profile spectrogram and archived measurement snapshots

The profile now displays an original published **SOUSY Arctic station spectrogram** in a dark presentation, rather than the earlier three modal-frequency traces. It shows the measured NS and EW magnetic channels over 0–30 Hz on **4 December 2020, 00:00–15:37:51 UT**. This is an archived observation.

Source: Koloskov Oleksandr; Nickolaenko Alexander; Yampolsky Yuri; Budanov Oleg. *Spectrograms and frequencies of the first mode of Schumann Resonance according to multi-position monitoring…* [Zenodo / DOI 10.5281/zenodo.5919944](https://zenodo.org/records/5919944), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Archive member: `Sou_2020.zip`, `12/s20201204000000.png`.

The original PNG and source manifest are in `assets/schumann-spectrogram-source.png` and `assets/schumann-spectrogram.json`. `assets/schumann-spectrogram-dark.svg` embeds that unchanged PNG. Its margin-only colour transform darkens the publisher's cyan page and lightens typography; the heatmap rectangles and colour bars are rendered without that transform. A cyan backing restores the source PNG's transparent-cyan colour, preserving its intended heatmap appearance. Axes and source colour-scale values are retained. The frame is an attributed adaptation, not an inferred numeric spectrum.

Both the identity banner and spectrogram use dark assets in either GitHub theme. The canonical SVG renderer is in the private XGCS Schumann Resonance Lab repository at `tools/render_spectrogram.py`. This public profile contains only the permitted published figure, attribution, checksums and presentation assets.

## Earlier numeric snapshot

The earlier header used actual measured frequencies of Schumann modes 1–3 from the Nagycenk observatory's Ez electric-field channel. Its day was 20 February 2023; the final sample was 23:30 UT. The snapshot and renderer remain as historical provenance, and are no longer the displayed profile graphic.

Source: Sátori, Gabriella; Bozóki, Tamás; Prácser, Ernő. *Modeled and measured SR frequency data (Ez, NCK, Hungary)*, version 2.0. [Zenodo / DOI 10.5281/zenodo.13220677](https://zenodo.org/records/13220677). [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Only the measured `NCK_f1_2023_02_10-20.txt`, `NCK_f2_2023_02_10-20.txt`, and `NCK_f3_2023_02_10-20.txt` files are used. The record's modeled data are excluded. The profile snapshot selects the last recorded day and reshapes those observations into JSON; it does not interpolate values. Original file URLs, published checksums, and SHA-256 hashes are in `schumann-snapshot.json`.

Regenerate both themes offline with:

```sh
python scripts/render_schumann_header.py
```

To select the last measured day from an exported station dataset with its public manifest:

```sh
python scripts/render_schumann_header.py --import-measurements /path/to/series.json
```

The older `solar-wind-snapshot.json` remains as historical provenance and is no longer displayed in the profile header.
