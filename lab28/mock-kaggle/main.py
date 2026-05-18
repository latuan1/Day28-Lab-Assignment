from __future__ import annotations

import hashlib
import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(title="Mock Kaggle GPU Service")


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"
    messages: list[ChatMessage] = Field(min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mock-kaggle"}


def deterministic_embedding(text: str, size: int = 384) -> list[float]:
    values: list[float] = []
    seed = text.encode("utf-8")

    for index in range(size):
        digest = hashlib.sha256(seed + index.to_bytes(2, "big")).digest()
        raw_value = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
        values.append(round((raw_value * 2.0) - 1.0, 6))

    return values


@app.post("/embed")
def embed(request: EmbedRequest) -> dict[str, list[list[float]]]:
    return {"embeddings": [deterministic_embedding(text) for text in request.texts]}


@app.post("/v1/chat/completions")
def chat_completions(request: ChatCompletionRequest) -> dict[str, Any]:
    user_messages = [message.content for message in request.messages if message.role == "user"]
    query = user_messages[-1] if user_messages else request.messages[-1].content
    answer = (
        "Mock Kaggle response: platform engineering connects ingestion, orchestration, "
        "vector search, model serving, and observability into one reliable AI workflow. "
        f"Received query context: {query[:180]}"
    )

    return {
        "id": "chatcmpl-mock-kaggle",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": max(1, len(query.split())),
            "completion_tokens": len(answer.split()),
            "total_tokens": max(1, len(query.split())) + len(answer.split()),
        },
    }
