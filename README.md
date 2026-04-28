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
   PARADIGM_APP_ID=...
   PARADIGM_CLIENT_ID=...
   PARADIGM_BASE_URL=https://api.ofself.ai
   ANTHROPIC_API_KEY=...
   INTERNAL_HEADLESS_SECRET=...
   PERSONAS_APP_ID=...
   PERSONAS_HMAC_KEY=...
   PERSONAS_BASE_URL=https://personas.ofself.ai
   ```

> `INTERNAL_HEADLESS_SECRET` is required only for app registration via `/personas/register`.

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
