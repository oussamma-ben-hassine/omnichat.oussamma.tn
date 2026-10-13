import os
import hashlib
import secrets
import base64
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, Response, HTTPException, Query, Depends
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import httpx
from nio import AsyncClient, RoomMessagesResponse

app = FastAPI(title="OmniChat AI Digest & Matrix Bridge", version="1.0.0")

# =============================================================================
# VARIABLES D'ENVIRONNEMENT & CONFIGURATION SSO OIDC
# =============================================================================
HOMESERVER = os.getenv("MATRIX_HOMESERVER_URL", "http://conduit:6167")
BOT_USER = os.getenv("MATRIX_BOT_USERNAME", "@summarizer:matrix.oussamma.tn")
BOT_PASS = os.getenv("MATRIX_BOT_PASSWORD", "changeme")
AI_BASE = os.getenv("OPENAI_API_BASE", "https://ai.oussamma.tn/v1")
AI_KEY = os.getenv("AI_API_KEY", "")

SESSION_SECRET = os.getenv("SESSION_SECRET", "omnichat-sso-secret-key-2026-prod")
SSO_BASE_URL = os.getenv("SSO_BASE_URL", "https://sso-a.oussamma.tn").rstrip("/")
SSO_CLIENT_ID = os.getenv("SSO_CLIENT_ID", "omnichat_matrix_client")
SSO_CLIENT_SECRET = os.getenv("SSO_CLIENT_SECRET", "sec_omnichat_matrix_secret_2026")
APP_URL = os.getenv("APP_URL", "https://omnichat.oussamma.tn").rstrip("/")
SSO_REDIRECT_URI = f"{APP_URL}/auth/callback"

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=86400 * 14)

# Montage de l'interface graphique
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# =============================================================================
# HELPER AUTHENTIFICATION SSO (OIDC / PKCE S256)
# =============================================================================
def generate_pkce_pair():
    verifier = secrets.token_urlsafe(64)[:64]
    digest = hashlib.sha256(verifier.encode('utf-8')).digest()
    challenge = base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
    return verifier, challenge

@app.get("/")
def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Interface OmniChat"}

@app.get("/auth/login")
def sso_login(request: Request):
    """Redirige l'utilisateur vers ton serveur SSO propriétaire."""
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(24)
    request.session["pkce_verifier"] = verifier
    request.session["oauth_state"] = state

    auth_url = (
        f"{SSO_BASE_URL}/oauth/authorize"
        f"?response_type=code"
        f"&client_id={SSO_CLIENT_ID}"
        f"&redirect_uri={SSO_REDIRECT_URI}"
        f"&scope=openid%20profile%20email"
        f"&state={state}"
        f"&code_challenge={challenge}"
        f"&code_challenge_method=S256"
    )
    return RedirectResponse(auth_url)

@app.get("/auth/callback")
async def sso_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None)
):
    """Échange le code d'autorisation contre un token et les informations de profil."""
    if error or not code:
        return RedirectResponse(f"/?auth_error={error or 'code_absent'}")

    stored_state = request.session.get("oauth_state")
    code_verifier = request.session.get("pkce_verifier", "")

    token_payload = {
        "grant_type": "authorization_code",
        "client_id": SSO_CLIENT_ID,
        "client_secret": SSO_CLIENT_SECRET,
        "code": code,
        "redirect_uri": SSO_REDIRECT_URI,
        "code_verifier": code_verifier
    }

    async with httpx.AsyncClient(timeout=15.0) as http_client:
        token_resp = await http_client.post(f"{SSO_BASE_URL}/oauth/token", data=token_payload)
        if token_resp.status_code != 200:
            return RedirectResponse("/?auth_error=token_exchange_failed")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        user_resp = await http_client.get(
            f"{SSO_BASE_URL}/oauth/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_resp.status_code == 200:
            user_info = user_resp.json()
            request.session["user"] = {
                "id": user_info.get("sub"),
                "email": user_info.get("email"),
                "name": user_info.get("name") or user_info.get("email", "").split("@")[0]
            }

    return RedirectResponse("/?logged_in=1")

@app.get("/api/auth/me")
def get_current_user(request: Request):
    """Retourne l'utilisateur connecté via SSO."""
    user = request.session.get("user")
    return {
        "authenticated": bool(user),
        "user": user,
        "sso_url": SSO_BASE_URL
    }

@app.get("/auth/logout")
def sso_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

# =============================================================================
# RECOLTE DES MESSAGES ET SYNTHÈSE IA
# =============================================================================
async def fetch_today_messages() -> List[Dict[str, Any]]:
    client = AsyncClient(HOMESERVER, BOT_USER)
    try:
        await client.login(BOT_PASS)
        await client.sync(timeout=10000)
        
        now = datetime.now(timezone.utc)
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        start_of_day_ts = int(start_of_day.timestamp() * 1000)

        collected = []
        for room_id, room in client.rooms.items():
            room_name = room.display_name or room_id
            res = await client.room_messages(room_id, start=room.prev_batch, limit=100)
            if isinstance(res, RoomMessagesResponse):
                for event in res.chunk:
                    if event.server_timestamp >= start_of_day_ts:
                        body = getattr(event, "body", None)
                        sender = getattr(event, "sender", "Inconnu")
                        if body and sender != BOT_USER:
                            collected.append({
                                "room": room_name,
                                "sender": sender,
                                "text": body,
                                "timestamp": datetime.fromtimestamp(event.server_timestamp / 1000, tz=timezone.utc).isoformat()
                            })
        return collected
    except Exception as e:
        print(f"Matrix sync notice: {e}")
        return []
    finally:
        await client.close()

async def generate_summary_with_ai(messages: List[Dict[str, Any]]) -> str:
    if not messages:
        return "Aucune discussion détectée aujourd'hui sur vos comptes connectés (Messenger / Instagram)."

    dialogue_text = "\n".join([f"[{m['room']}] {m['sender']}: {m['text']}" for m in messages])
    prompt = f"""Tu es l'assistant personnel d'Oussama.
Voici l'ensemble des messages reçus et envoyés aujourd'hui sur ses canaux de messagerie personnelle (Facebook Messenger, Instagram DM) :

---
{dialogue_text}
---

Génère un résumé structuré et clair de sa journée avec :
1. 📌 **Sujets Clés & Résumé Global** : ce qui s'est passé en 2-3 phrases.
2. 👥 **Discussions par Contact/Groupe** : faits marquants ou messages importants échangés.
3. ⚠️ **Actions requises & Questions en attente** : les points où quelqu'un attend une réponse ou une action de sa part.
4. 💡 **Informations ou détails à retenir**.
"""

    headers = {"Authorization": f"Bearer {AI_KEY}"} if AI_KEY else {}
    payload = {
        "model": "gemini-2.5-flash",
        "messages": [
            {"role": "system", "content": "Tu es un assistant de synthèse rapide, direct et efficace."},
            {"role": "user", "content": prompt}
        ]
    }

    async with httpx.AsyncClient(timeout=60.0) as http_client:
        resp = await http_client.post(f"{AI_BASE}/chat/completions", json=payload, headers=headers)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        return f"Erreur lors de la génération IA : {resp.status_code}"

@app.get("/health")
def health():
    return {"status": "ok", "service": "omnichat-matrix-digest", "sso": SSO_BASE_URL}

@app.get("/api/digest/now")
async def trigger_digest_now():
    messages = await fetch_today_messages()
    summary = await generate_summary_with_ai(messages)
    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "messages_count": len(messages),
        "summary": summary
    }
