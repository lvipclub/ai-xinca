#!/usr/bin/env python3
"""
XINCA Havi Chat API
FastAPI service that provides AI chat for help.xinca.com using FAQ knowledge base
and DeepSeek via OpenRouter.
"""
import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Configuration ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash-vision-exp")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# seed-qa.json lives FLAT next to this script on the VPS (/var/www/ai-xinca-chat/),
# but in the repo it's at src/data/seed-qa.json (deploy.sh rsyncs it flat).
# 2026-09-07: qa_count was 0 in production — the repo-only path missed the live file.
QA_DATA_PATHS = [
    Path(__file__).parent / "seed-qa.json",                          # live VPS layout (flat)
    Path(__file__).parent.parent / "src" / "data" / "seed-qa.json",  # repo layout (local dev)
]

# --- App ---
app = FastAPI(title="XINCA Havi Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Data ---
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []

class ChatResponse(BaseModel):
    response: str
    sources: list[dict] = []

# --- Load QA data at startup ---
qa_entries: list[dict] = []

def load_qa():
    global qa_entries
    for candidate in QA_DATA_PATHS:
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                qa_entries = json.load(f)
            print(f"Loaded {len(qa_entries)} QA entries from {candidate}")
            return
        except Exception:
            continue
    print(f"Warning: Could not load QA data from any of: {[str(p) for p in QA_DATA_PATHS]}")
    qa_entries = []

@app.on_event("startup")
async def startup():
    load_qa()

# --- Simple keyword matching for FAQ retrieval ---
def search_faq(query: str, top_k: int = 5) -> list[dict]:
    """Simple keyword-based FAQ retrieval."""
    query_lower = query.lower()
    words = set(query_lower.split())
    
    scored = []
    for entry in qa_entries:
        # Combine question, answer, tags for matching
        text = (
            entry.get("question", "") + " " +
            entry.get("answer", "") + " " +
            " ".join(entry.get("tags", []))
        ).lower()
        
        # Simple score: count matching words
        score = sum(1 for w in words if w in text)
        
        # Bonus for tag matches
        for tag in entry.get("tags", []):
            if tag.lower() in query_lower:
                score += 3
        
        # Bonus for category match
        cat = entry.get("category", "").lower()
        if cat in query_lower:
            score += 2
        
        if score > 0:
            scored.append((score, entry))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:top_k]]

# --- System prompt ---
SYSTEM_PROMPT = """You are Lady Havi, AI host for XINCA HVAC. Answer questions using only the provided FAQ context. Be concise, cite sources, and stay on HVAC/IAQ/IoT topics.

Rules:
- Use only the provided context to answer. If the context doesn't contain the answer, say "I don't have specific information on that topic. Try the Knowledge Base search for more."
- Be concise and direct.
- Cite sources by mentioning the FAQ entry number when relevant.
- Stay strictly on HVAC, IAQ, IoT, and building automation topics.
- Do not mention Belimo, Honeywell, JCI, or Siemens by name.
- If asked about those companies, refer to them generically (e.g., "manufacturers", "major brands", "industry suppliers").
"""

# --- Endpoints ---
@app.get("/api/health")
async def health():
    return {"status": "ok", "model": OPENROUTER_MODEL, "qa_count": len(qa_entries)}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")
    
    user_message = request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Search FAQ for relevant context
    relevant_faqs = search_faq(user_message, top_k=5)
    
    # Build context from FAQs
    context_parts = []
    for i, faq in enumerate(relevant_faqs, 1):
        context_parts.append(
            f"[FAQ {i}] Q: {faq['question']}\nA: {faq['answer']}\nCategory: {faq.get('category', 'general')}\nTags: {', '.join(faq.get('tags', []))}"
        )
    
    context_text = "\n\n".join(context_parts) if context_parts else "No direct FAQ match found. Use your general HVAC knowledge."
    
    # Build messages for the LLM
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"FAQ CONTEXT:\n{context_text}"},
    ]
    
    # Add conversation history (last 6 messages)
    for msg in request.history[-6:]:
        messages.append({"role": msg.role, "content": msg.content})
    
    # Add current user message
    messages.append({"role": "user", "content": user_message})
    
    # Call OpenRouter
    # 2026-09-07: deepseek-v4-flash-vision-exp is a REASONING model. A tight
    # max_tokens budget can be fully consumed by reasoning
    # (finish_reason=length, content=None -> pydantic 500). The carousel picker
    # hit the same at 3000 and was fixed in 06da44e with 65536. Here 16384
    # covers worst-case reasoning + a chat answer; reasoning is disabled for
    # snappy interactive-chat latency (verified via OpenRouter reasoning param).
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 16384,
        "reasoning": {"enabled": False},
    }
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response_text = None
            for attempt in range(2):  # one retry absorbs a reasoning-exhausted response
                resp = await client.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://help.xinca.com",
                        "X-Title": "XINCA Havi Chat",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

                if "choices" in data and data["choices"]:
                    response_text = data["choices"][0]["message"].get("content")
                    if response_text:
                        break
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")

    if not response_text:
        raise HTTPException(status_code=502, detail="LLM returned empty content after retry")
    
    # Build sources list
    sources = []
    for faq in relevant_faqs:
        sources.append({
            "id": faq["id"],
            "question": faq["question"],
            "category": faq.get("category", "general"),
        })
    
    return ChatResponse(response=response_text, sources=sources)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)