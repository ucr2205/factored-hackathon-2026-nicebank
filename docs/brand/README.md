# NiceBank brand

- `nicebank-logo-source.jpg`: logo source (AI-generated for the team, 2000x2000, light and dark lockups).
- Colors: burgundy `#7A1F3D` (primary), rose `#E5769A` (accent), white; dark surfaces `#121212` / `#1E1E1E`.
- The symbol is a rounded square with an "N", a card chip and a shield.

Derived assets are generated, not edited by hand:

```bash
poetry run python scripts/build_brand_assets.py
```

It writes the favicon and app mark (`frontend/public/brand/`), the Keycloak login mark
(`infra/keycloak/themes/nicebank/login/resources/img/nicebank-mark.png`) and the email header mark
(`backend/internal/notify/assets/nicebank-mark.png`, embedded as an inline image). A vector (SVG) version of the
symbol would give sharper small sizes; replace the source and rerun the script when one exists.
