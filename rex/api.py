"""FastAPI service: uvicorn rex.api:app --reload"""
from uuid import uuid4
from fastapi import FastAPI
from pydantic import BaseModel
from rex.assistant.engine import RexAssistant, Session

app = FastAPI(title="REX AI", version="0.1.0")
bot = RexAssistant()
sessions: dict[str, Session] = {}

class ChatIn(BaseModel):
    message: str
    session_id: str | None = None

@app.get("/health")
def health(): return {"status": "ok", "courses": len(bot.kb.courses)}

@app.post("/chat")
def chat(body: ChatIn):
    sid = body.session_id or str(uuid4())
    s = sessions.setdefault(sid, Session())
    return {"session_id": sid, "reply": bot.reply(s, body.message)}
