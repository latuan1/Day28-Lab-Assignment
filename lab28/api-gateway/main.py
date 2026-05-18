# api-gateway/main.py
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
import httpx, os, time

app = FastAPI(title="AI Platform API Gateway")
Instrumentator().instrument(app).expose(app)  # Integration 9: Prometheus

VLLM_URL = os.environ["VLLM_URL"]
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    embedding: list[float] | None = None


def normalize_embedding(embedding: list[float] | None) -> list[float]:
    if not embedding:
        return [0.0] * 384
    if len(embedding) >= 384:
        return embedding[:384]
    return embedding + ([0.0] * (384 - len(embedding)))


@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
    start = time.time()
    context = []

    # 1. Vector search
    async with httpx.AsyncClient() as client:
        collections_resp = await client.get(f"{QDRANT_URL}/collections")
        collections = collections_resp.json().get("result", {}).get("collections", [])
        has_documents = any(collection.get("name") == "documents" for collection in collections)

        if has_documents:
            search_resp = await client.post(f"{QDRANT_URL}/collections/documents/points/search", json={
                "vector": normalize_embedding(request.embedding),
                "limit": 3
            })
            if search_resp.status_code == 200:
                context = search_resp.json().get("result", [])

    # 2. LLM inference
    prompt = f"Context: {context}\n\nQuery: {request.query}"
    async with httpx.AsyncClient(timeout=30) as client:
        llm_resp = await client.post(f"{VLLM_URL}/v1/chat/completions", json={
            "model": "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
            "messages": [{"role": "user", "content": prompt}]
        })

    latency = (time.time() - start) * 1000
    result = llm_resp.json()

    return {
        "answer": result["choices"][0]["message"]["content"],
        "latency_ms": round(latency, 2),
        "model": result["model"]
    }

@app.get("/health")
def health():
    return {"status": "ok"}
