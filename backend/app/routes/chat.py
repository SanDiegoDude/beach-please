"""Streaming agent chat endpoint."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent import run_chat

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("/chat")
async def chat(req: ChatRequest) -> EventSourceResponse:
    user_messages: list[dict[str, str]] = [m.model_dump() for m in req.messages]

    async def event_stream():
        try:
            async for event in run_chat(user_messages):
                yield {"event": "message", "data": json.dumps(event)}
        except Exception as exc:
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "message": str(exc)}),
            }

    return EventSourceResponse(event_stream())
