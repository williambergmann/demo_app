# Cayenne Finder

## Architecture
- Flask app (`app.py`) that proxies requests to the Anthropic Messages API with web search
- Single-page frontend (`templates/cayenne.html`) with preset search queries for Porsche Cayenne listings
- Deployed on Render (auto-deploys from `master` branch)
- Config: `render.yaml`, `requirements.txt`

## Anthropic API
- API version header: `anthropic-version: 2023-06-01`
- Web search requires beta header: `anthropic-beta: web-search-2025-03-05`
- Web search tool type: `web_search_20250305`
- Current model: `claude-sonnet-4-6`

## Deployment
- Render deploys from `master` branch
- After merging PRs, wait for Render to auto-redeploy
- Python 3.11.7, gunicorn with 120s timeout

## Security
- API keys are stored in browser localStorage, passed via `X-Api-Key` header
- `.env` is gitignored — never commit secrets
- Never write API keys or secrets to files in this repo
