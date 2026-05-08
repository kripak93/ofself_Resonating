from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os, hmac, hashlib, json, httpx

load_dotenv()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="change-this-in-production")
templates = Jinja2Templates(directory="templates")

API_KEY         = os.getenv("PARADIGM_API_KEY")
CLIENT_ID       = os.getenv("PARADIGM_CLIENT_ID")
REDIRECT_URI    = "http://localhost:8000/auth/callback"
BASE_URL        = os.getenv("PARADIGM_BASE_URL")
HEADLESS_URL    = os.getenv("HEADLESS_PLUGIN_URL")   # e.g. https://plugins.ofself.ai/headless
HEADLESS_KEY    = os.getenv("HEADLESS_API_KEY")       # hl_<key_id>.<secret>
HEADLESS_HMAC   = os.getenv("HEADLESS_HMAC_SECRET")   # hmac_secret from registration

class DebateInput(BaseModel):
    topic: str
    argument: str
    mode: str = "counter"
    rule: str = ""
    conversation_id: str = ""

mode_prompts = {
    "counter":    "You are a sharp devil's advocate in a debate. Challenge every argument the user makes directly and forcefully. Do not agree with them.",
    "facilitate": "You are a debate facilitator. Find common ground, steelman both sides, and help the user refine their thinking.",
    "steelman":   "First strengthen the user's argument as powerfully as possible, then offer the single strongest challenge to it."
}

@app.get("/")
def root(request: Request):
    return RedirectResponse("/debate" if request.session.get("user_id") else "/login")

@app.get("/login")
def login():
    auth_url = (
        f"https://app.ofself.ai/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
    )
    return RedirectResponse(auth_url)

@app.get("/auth/callback")
async def callback(request: Request):
    params = dict(request.query_params)
    user_id = params.get("user_id")
    if not user_id:
        return {"error": "No user_id returned"}
    request.session["user_id"] = user_id
    request.session["username"] = params.get("username", "")
    return RedirectResponse("/debate")

@app.get("/debate")
def debate_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login")
    return templates.TemplateResponse("debate.html", {
        "request": request,
        "username": request.session.get("username", "")
    })

@app.get("/me")
async def me(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/api/v1/third-party/me",
            headers={"X-API-Key": API_KEY, "X-User-ID": user_id}
        )
    return resp.json()

@app.post("/debate")
async def debate(payload: DebateInput, request: Request):
    user_id = request.session.get("user_id")
    username = request.session.get("username", "User")
    if not user_id:
        return {"error": "Not logged in"}

    persona = mode_prompts.get(payload.mode, mode_prompts["counter"])
    system_prompt = (
        f"{persona}\n\n"
        f"The debate topic is: {payload.topic}\n"
        f"The rule for this exploration: {payload.rule}\n\n"
        f"You have access to {username}'s identity graph — their declared beliefs, values, "
        f"and knowledge. Use this to make your responses personal and precise. "
        f"Keep responses to 2-3 focused paragraphs."
    )

    body = {
        "paradigm_user_id": user_id,
        "message":          payload.argument,
        "variables":        {"debate_prompt": system_prompt},
    }
    if payload.conversation_id:
        body["conversation_id"] = payload.conversation_id

    raw_body = json.dumps(body, separators=(',', ':'), sort_keys=True).encode('utf-8')
    sig = hmac.new(HEADLESS_HMAC.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type":         "application/json",
        "X-Headless-Key":       HEADLESS_KEY,
        "X-Headless-Signature": f"sha256={sig}",
    }

    async def stream_response():
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{HEADLESS_URL}/chat",
                content=raw_body,
                headers=headers,
            )
            print("HEADLESS STATUS:", resp.status_code)
            data = resp.json()
            print("HEADLESS RESPONSE:", data)

            if data.get("requires_realm_assignment"):
                # Use the plugin's /authorize EP to get the proper sub-entity consent URL
                auth_body = json.dumps(
                    {"paradigm_user_id": user_id},
                    separators=(',', ':'), sort_keys=True
                ).encode('utf-8')
                auth_sig = hmac.new(
                    HEADLESS_HMAC.encode('utf-8'), auth_body, hashlib.sha256
                ).hexdigest()
                auth_resp = await client.post(
                    f"{HEADLESS_URL}/authorize",
                    content=auth_body,
                    headers={
                        "Content-Type":         "application/json",
                        "X-Headless-Key":       HEADLESS_KEY,
                        "X-Headless-Signature": f"sha256={auth_sig}",
                    },
                )
                consent_url = auth_resp.json().get("consent_url", "")
                yield f"data:{json.dumps({'type': 'auth_required', 'url': consent_url})}\n\n"
                return

            if data.get("error"):
                yield f"data:{json.dumps({'type': 'error', 'message': data.get('message', 'Unknown error')})}\n\n"
                return

            text = data.get("assistant_text", "")
            conversation_id = data.get("conversation_id", "")
            yield f"data:{json.dumps({'type': 'chunk', 'text': text})}\n\n"
            yield f"data:{json.dumps({'type': 'done', 'conversation_id': conversation_id})}\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")
