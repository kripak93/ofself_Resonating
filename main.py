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
PERSONAS_BASE   = os.getenv("PERSONAS_BASE_URL")
PERSONAS_APP_ID = os.getenv("PERSONAS_APP_ID")
PERSONAS_HMAC   = os.getenv("PERSONAS_HMAC_KEY")

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
    "app_id":           PERSONAS_APP_ID,
    "hmac_key":         PERSONAS_HMAC,
    "paradigm_user_id": user_id,
    "message":          payload.argument,
    "app_name":         "Debate Platform",
    "agent_name":       "Debate Moderator",
    "system_prompt":    system_prompt,
    "temperature":      0.7,
    "tools_config": {
        "web_search": False,
        "wikipedia":  False,
    }
}

    if payload.conversation_id:
        body["conversation_id"] = payload.conversation_id

    raw_body = json.dumps(body, separators=(',', ':'), sort_keys=True).encode('utf-8')
    sig = hmac.new(PERSONAS_HMAC.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type":         "application/json",
        "X-Internal-Signature": f"sha256={sig}"
    }

    async def stream_personas():
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{PERSONAS_BASE}/internal/headless/run/stream",
                content=raw_body,
                headers=headers
            ) as resp:
                print("PERSONAS STATUS:", resp.status_code)
                async for line in resp.aiter_lines():
                    print("LINE:", line)
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("requires_realm_assignment"):
                            yield f"data:{json.dumps({'type': 'auth_required', 'url': data['redirect_url']})}\n\n"
                            return
                    except:
                        pass

                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if not data_str:
                        continue
                    try:
                        data = json.loads(data_str)
                        event = data.get("event")
                        if event == "content":
                            chunk = data.get("text", "")
                            yield f"data:{json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                        elif event == "done":
                            conversation_id = data.get("conversation_id", "")
                            yield f"data:{json.dumps({'type': 'done', 'conversation_id': conversation_id})}\n\n"
                    except Exception as e:
                        print("PARSE ERROR:", e)
                        continue

    return StreamingResponse(stream_personas(), media_type="text/event-stream")