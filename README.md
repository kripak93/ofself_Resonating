# Debate Platform

A simple FastAPI app for ofself debate sessions with Personas integration.

## Features

- FastAPI-based debate interface
- Login redirect to ofself auth
- Claude-based debate responses via Anthropic
- Personas app registration helper and HMAC-signed headless access

## Setup

1. Create a virtual environment and activate it:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install fastapi uvicorn jinja2 python-dotenv httpx anthropic
   ```
3. Add environment variables in `.env`:
   ```env
   PARADIGM_API_KEY=...
   PARADIGM_CLIENT_ID=...
   PARADIGM_BASE_URL=https://api.ofself.ai
   HEADLESS_PLUGIN_URL=https://plugins.ofself.ai/headless
   HEADLESS_API_KEY=hl_...          # returned at app registration
   HEADLESS_HMAC_SECRET=...         # returned at app registration
   HEADLESS_APP_ID=...              # for update_agent.py only
   HEADLESS_ADMIN_SECRET=...        # for update_agent.py only
   ```

> Register the app once via `POST /apps/register` (with `X-Admin-Secret`) to get `HEADLESS_API_KEY` and `HEADLESS_HMAC_SECRET`.

## Run

```powershell
uvicorn main:app --reload
```

## Routes

- `GET /` → redirects to `/login` or `/debate`
- `GET /login` → starts ofself auth flow
- `GET /auth/callback` → receives auth callback and stores session
- `GET /debate` → debate UI page
- `POST /debate` → submit debate prompt
- `POST /personas/register` → register a new Personas app
- `GET /personas/list` → list personas using app HMAC credentials

## Notes

- Store secrets securely and do not commit `.env`
- Use the app’s returned `app_id` and `hmac_key` for Personas headless requests
