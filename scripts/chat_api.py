#!/usr/bin/env python3
"""
XINCA Havi Chat API
FastAPI service that provides AI chat for ai.xinca.com using FAQ knowledge base
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
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
QA_DATA_PATH = Path(__file__).parent.parent / "src" / "data" / "seed-qa.json"

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
    try:
        with open(QA_DATA_PATH, "r", encoding="utf-8") as f:
            qa_entries = json.load(f)
        print(f"Loaded {len(qa_entries)} QA entries")
    except Exception as e:
        print(f"Warning: Could not load QA data: {e}")
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
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://ai.xinca.com",
                    "X-Title": "XINCA Havi Chat",
                },
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            
            if "choices" not in data or not data["choices"]:
                raise HTTPException(status_code=502, detail="Invalid response from LLM")
            
            response_text = data["choices"][0]["message"]["content"]
            
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    
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