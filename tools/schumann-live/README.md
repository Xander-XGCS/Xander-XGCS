# Schumann profile banner (self-hosted candidate)

This is a bounded daily-update service for the **GitHub profile header**. It does not consume GitHub Actions. **Not deployed** as part of this repository. README must stay on the existing archived image until a live public endpoint, source reuse rights, actual measurement freshness, and GitHub's rendered refresh have been verified.

## Why BGS?

The British Geological Survey's Eskdalemuir induction-coil page publishes a spectrogram for the previous UTC day (North coil, currentSpectrogramCH1.jpg). The source file was verified publicly showing 2026-11-07 on 2026-11-08. The raw chart itself includes the observation date in its title; it is not a constant 7.83 Hz simulated waveform.

Sources:
- https://geomag.bgs.ac.uk/research/inductioncoils.html
- https://geomag.bgs.ac.uk/images/currentSpectrogramCH1.jpg

**Rights**: A 2019 BGS archive release is explicitly OGL with acknowledgement, but that does *not* establish the rights for today's continually published image. Before enabling public reproduction, secure permission or confirmed applicable licensing from BGS (contact the BGS IPR team if needed). Do not copy these images into the repository before rights clearance. For HeartMath, request written reuse permission; its general image policy is not a blanket license.

## Run on an already-authorized self-hosted machine

Python 3.12, Pillow 11.x:

```sh
python -m pip install -r tools/schumann-live/requirements.txt
python -m unittest discover -s tools/schumann-live -p "test_*.py"
SCHUMANN_OUTPUT_DIR=/var/lib/xgcs-schumann python tools/schumann-live/schumann_live.py --once
```

By default, **no network image fetch occurs** and the output says UNAVAILABLE. Once source rights are explicitly confirmed, use `SCHUMANN_REUSE_APPROVED=yes` and run an HTTP service behind a **separately authorized** HTTPS route. A service example (adjust host mounts, routing and permissions yourself):

```sh
SCHUMANN_REUSE_APPROVED=yes SCHUMANN_OUTPUT_DIR=/var/lib/xgcs-schumann SCHUMANN_HOST=127.0.0.1 python tools/schumann-live/schumann_live.py
```

The service serves `/profile-banner.png`, `/status.json`, and `/healthz`, polling only once every six hours by default. HTTP responses use no-store headers. Do not expose direct origin ports or create a public Cloudflare route without the authorized routing process.

## Status semantics

- **CURRENT**: BGS image successfully parsed, file HTTP Last-Modified was within 48h, digest not stale across checks. This verifies *publication freshness*, not the exact observation time.
- **DELAYED**: source file is valid but its publication metadata is stale, unavailable, or unchanged across >48h.
- **UNAVAILABLE**: permissions not attested, fetching failed, or source image invalid. Fail closed, do not display a fabricated chart.

The observation date is visibly printed in the unmodified spectrogram panel. The service intentionally reports `observed_utc: null` because **we have not built a machine-verifiable timestamp extractor**. The file modification time must never be relabeled as the measurement time. Until timestamp verification is implemented, avoid claiming fully verified "live" measurements.

## Acceptance before README switch

1. Resolve license for the CURRENT BGS published image; record written grant or applicable license in issue #4.
2. Deploy to authorized low-cost/self-hosted HTTP endpoint, ensure TLS.
3. Compare observation dates in at least two source images over two daily cycles. Verify freshness and outage/unchanged-file fallbacks.
4. Confirm GitHub's Camo image caching refreshes the delivered header; do not assume no-store headers override GitHub caching.
5. Only then switch README's top `src` to the known live HTTPS endpoint. Preserve attribution at the bottom and link to BGS methodology.
6. No GitHub Actions, no arbitrary remote worker execution, and no image-faking.

The static 2020 SOUSY inset remains the active header until all gates pass.
