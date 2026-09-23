# muse-aurelius

Code for Aurelius (Muse agent): Instagram Reel factory, automation skills, and scripts.

## Structure

- `skills/` — Reusable agent skills (reel-factory, instagram-automation, etsy-open-api, pinterest-api, etc.)
- `reel-factory/` — Reel rendering pipeline (`render_reel.py` + unit tests)
- `automation/` — Pi SSH helpers, Etsy/Pinterest automation scripts

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials
2. Install test deps: `pip install pytest`
3. Run tests: `cd reel-factory && python3 -m pytest test_render_reel.py -v`

## Privacy

All secrets are read from environment variables. No credentials are hardcoded.
See `.env.example` for the full list.
