# Cayenne Finder

## Architecture
- Flask app (`app.py`) that proxies requests to the Anthropic Messages API with web search
- Single-page frontend (`templates/cayenne.html`) with preset search queries for Porsche Cayenne listings
- Deployed on Render (auto-deploys from `master` branch)
- Config: `render.yaml`, `requirements.txt`

## Anthropic API
- API version header: `anthropic-version: 2023-06-01`
- Web search is GA (no beta header needed)
- Web search tool type: `web_search_20260209` (supports dynamic filtering with Claude 4.6)
- Previous tool type `web_search_20250305` still works but lacks dynamic filtering
- Current model: `claude-sonnet-4-6`

## CLI
- `cli.py` — run searches from the command line
- Usage: `ANTHROPIC_API_KEY=sk-... python cli.py --preset 0` (or pass a custom query)
- `--list-presets` / `-l` to see available presets
- `--json` / `-j` for raw API response
- `--max-uses` / `-m` to limit web searches (default: 10)

## Deployment
- Render deploys from `master` branch
- After merging PRs, wait for Render to auto-redeploy
- Python 3.11.7, gunicorn with 120s timeout

## Security
- API keys are stored in browser localStorage, passed via `X-Api-Key` header
- `.env` is gitignored — never commit secrets
- Never write API keys or secrets to files in this repo
