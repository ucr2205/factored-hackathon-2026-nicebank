# Email assets

The NiceBank mark (email header) and card-brand logos embedded in notification emails as inline (CID) images, looked up by brand:
`visa.png`, `mastercard.png`, `amex.png` (PNG, about 96 px wide, transparent or white background).

Email clients do not render SVG reliably (Gmail strips it), so logos must be PNG. When a file is missing,
the email shows the brand name as text instead. Keep the source and license of each file below.

| File | Source | License / terms |
|---|---|---|
| `nicebank-mark.png` | `scripts/build_brand_assets.py` from `docs/brand/nicebank-logo-source.jpg` | Team-owned NiceBank logo |
