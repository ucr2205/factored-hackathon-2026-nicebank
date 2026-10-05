# Pitch deck

Final presentation: 6 slides in English, 16:9, NiceBank brand.

| File | What |
|---|---|
| [`deck/NiceBank-pitch.pdf`](deck/NiceBank-pitch.pdf) | The deck: the problem in the bank's data, the product, architecture and decisions, data / ML / evaluation, results and what a bank would need next |
| [`deck/deck.html`](deck/deck.html) | Its source (HTML + CSS, the same fonts and colors as the video in `video/assets/`) |
| [`deck/img/`](deck/img/) | Real screens of the app used on the slides |

Rebuild the PDF from `video/` with `node tools/deck-pdf.mjs ../docs/pitch/deck/NiceBank-pitch.pdf` (Playwright with
the local Chrome). Every figure comes from `eval/reports/test-v2-20261004T213856Z.md`, `docs/eda_findings.md`,
`docs/ml_report.md` and `docs/production_gap.md`.
