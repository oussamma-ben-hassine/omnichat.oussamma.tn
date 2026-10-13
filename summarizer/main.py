import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
from nio import AsyncClient, RoomMessagesResponse

app = FastAPI(title="Matrix AI Digest & Summarizer", version="1.0.0")

HOMESERVER = os.getenv("MATRIX_HOMESERVER_URL", "http://conduit:6167")
BOT_USER = os.getenv("MATRIX_BOT_USERNAME", "@summarizer:matrix.oussamma.tn")
BOT_PASS = os.getenv("MATRIX_BOT_PASSWORD", "changeme")
AI_BASE = os.getenv("OPENAI_API_BASE", "https://ai.oussamma.tn/v1")
AI_KEY = os.getenv("AI_API_KEY", "")

# Montage des fichiers statiques pour l'interface web
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Interface OmniChat"}


async def fetch_today_messages() -> List[Dict[str, Any]]:
    """Récupère tous les messages de la journée sur tous les salons Matrix retransmis par le pont."""
    client = AsyncClient(HOMESERVER, BOT_USER)
    try:
        login_res = await client.login(BOT_PASS)
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
                        # Filtrer les messages textes envoyés
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
    finally:
        await client.close()

async def generate_summary_with_ai(messages: List[Dict[str, Any]]) -> str:
    """Envoie les conversations formatées au service LLM pour analyse."""
    if not messages:
        return "Aucune discussion détectée aujourd'hui sur vos comptes connectés (Messenger / Instagram)."

    # Formatage du texte pour l'IA
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
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            return f"Erreur lors de la génération IA : {resp.status_code} - {resp.text}"

@app.get("/health")
def health():
    return {"status": "ok", "service": "matrix-ai-summarizer"}

@app.get("/api/digest/now")
async def trigger_digest_now():
    """Déclenche immédiatement le résumé du jour."""
    try:
        messages = await fetch_today_messages()
        summary = await generate_summary_with_ai(messages)
        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "messages_count": len(messages),
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
