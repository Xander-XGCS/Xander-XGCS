# Profile measurement snapshot

The header uses actual measured frequencies of Schumann modes 1–3 from the Nagycenk observatory's Ez electric-field channel. The displayed day is 20 February 2023; the final sample is 23:30 UT. These are archived observations, not current station readings. Each trace is scaled independently to its displayed-day range; numeric labels remain measured Hz. Animation highlights the fixed traces and does not simulate new measurements.

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
