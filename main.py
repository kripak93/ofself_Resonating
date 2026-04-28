from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os, httpx, anthropic, hashlib, hmac, json

load_dotenv()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="change-this-in-production")
templates = Jinja2Templates(directory="templates")

API_KEY = os.getenv("PARADIGM_API_KEY")
CLIENT_ID = os.getenv("PARADIGM_CLIENT_ID")
REDIRECT_URI = "http://localhost:8000/auth/callback"
BASE_URL = os.getenv("PARADIGM_BASE_URL")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

INTERNAL_HEADLESS_SECRET = os.getenv("INTERNAL_HEADLESS_SECRET")
PERSONAS_APP_ID = os.getenv("PERSONAS_APP_ID")
PERSONAS_HMAC_KEY = os.getenv("PERSONAS_HMAC_KEY")
PERSONAS_BASE_URL = os.getenv("PERSONAS_BASE_URL", "https://personas.ofself.ai")

def make_hmac_signature(payload: str, secret: str) -> str:
    return "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

async def register_personas_app(name: str) -> dict:
    if not INTERNAL_HEADLESS_SECRET:
        raise HTTPException(status_code=500, detail="INTERNAL_HEADLESS_SECRET is not configured")

    body = json.dumps({"name": name}, separators=(",", ":"))
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Signature": make_hmac_signature(body, INTERNAL_HEADLESS_SECRET),
    }

    async with httpx.AsyncClient() as client:
        url = f"{PERSONAS_BASE_URL}/api/v1/internal/headless/apps/register"
        response = await client.post(url, headers=headers, content=body, timeout=30.0)
        response.raise_for_status()
        return response.json()

async def call_personas_headless_route(path: str, payload: dict) -> dict:
    if not PERSONAS_APP_ID or not PERSONAS_HMAC_KEY:
        raise HTTPException(status_code=500, detail="PERSONAS_APP_ID and PERSONAS_HMAC_KEY must be configured")

    body = json.dumps(payload, separators=(",", ":"))
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Signature": make_hmac_signature(body, PERSONAS_HMAC_KEY),
    }

    async with httpx.AsyncClient() as client:
        url = f"{PERSONAS_BASE_URL}{path}"
        response = await client.post(url, headers=headers, content=body, timeout=30.0)
        response.raise_for_status()
        return response.json()

class DebateInput(BaseModel):
    topic: str
    argument: str
    mode: str = "counter"
    rule: str = ""

@app.get("/")
def root(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        return RedirectResponse("/debate")
    return RedirectResponse("/login")

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
    username = params.get("username", "")
    if not user_id:
        return {"error": "No user_id returned"}
    request.session["user_id"] = user_id
    request.session["username"] = username
    return RedirectResponse("/debate")

class PersonasRegisterRequest(BaseModel):
    name: str

@app.post("/personas/register")
async def personas_register(payload: PersonasRegisterRequest):
    result = await register_personas_app(payload.name)
    return {
        "message": "Store PERSONAS_APP_ID and PERSONAS_HMAC_KEY securely in your environment.",
        **result,
    }

@app.get("/personas/list")
async def personas_list():
    return await call_personas_headless_route("/api/v1/headless/personas", {"app_id": PERSONAS_APP_ID})

@app.get("/debate")
def debate_page(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login")
    return templates.TemplateResponse("debate.html", {
        "request": request,
        "username": request.session.get("username", "")
    })

@app.post("/debate")
async def debate(payload: DebateInput, request: Request):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    mode_prompts = {
        "counter": "You are a sharp devil's advocate. Challenge the argument directly.",
        "facilitate": "You are a facilitator. Find common ground and steelman both sides.",
        "steelman": "First strengthen the user's argument, then offer one key challenge."
    }

    persona = mode_prompts.get(payload.mode, mode_prompts["counter"])

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": (
                f"Topic: {payload.topic}\n"
                f"Rule for this exploration: {payload.rule}\n\n"
                f"The user argues: {payload.argument}\n\n"
                f"{persona} "
                f"Respond in 2-3 concise paragraphs. Respect the rule."
            )
        }]
    )
    return {"counter": message.content[0].text}