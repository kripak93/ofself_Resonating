import hmac, hashlib, json, httpx
from dotenv import load_dotenv
import os

load_dotenv()

HEADLESS_URL          = os.getenv("HEADLESS_PLUGIN_URL")   # e.g. https://plugins.ofself.ai/headless
HEADLESS_APP_ID       = os.getenv("HEADLESS_APP_ID")
HEADLESS_ADMIN_SECRET = os.getenv("HEADLESS_ADMIN_SECRET")

resp = httpx.put(
    f"{HEADLESS_URL}/apps/{HEADLESS_APP_ID}",
    json={"llm_provider": "ofself", "llm_model": "gpt-5.2"},
    headers={
        "Content-Type": "application/json",
        "X-Admin-Secret": HEADLESS_ADMIN_SECRET,
    }
)
print(resp.status_code)
print(resp.text)
