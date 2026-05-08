import hmac, hashlib, json, httpx

PERSONAS_BASE   = "https://personas-ofself-api-hkdgezabafarfqdr.eastus2-01.azurewebsites.net/api/v1"
PERSONAS_APP_ID = "eaf6f80b-4b50-4a9b-a750-57d288262e52"
PERSONAS_HMAC   = "sk_hdls_b6932cfafa3ceb631905a21b8577c13a91728b629774cfcf"

body = {
    "app_id":       PERSONAS_APP_ID,
    "hmac_key":     PERSONAS_HMAC,
    "llm_provider": "anthropic",
    "llm_model":    "claude-sonnet-4-5"
}

raw = json.dumps(body, separators=(',', ':'), sort_keys=True).encode('utf-8')
sig = hmac.new(PERSONAS_HMAC.encode('utf-8'), raw, hashlib.sha256).hexdigest()

resp = httpx.put(
    f"{PERSONAS_BASE}/internal/headless/apps/{PERSONAS_APP_ID}",
    content=raw,
    headers={
        "Content-Type": "application/json",
        "X-Internal-Signature": f"sha256={sig}"
    }
)
print(resp.status_code)
print(resp.text)