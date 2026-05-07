"""OpenAI-compatible agent with a tool-calling loop.

Works against:
- api.openai.com (default)
- LM Studio (http://localhost:1234/v1)
- Ollama (http://localhost:11434/v1)
- Any OpenAI-compatible chat completions endpoint with tool-calling support.

Streams events to the caller as JSON-serializable dicts. The HTTP route layer
wraps these in Server-Sent Events.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.config import get_settings
from app.personality import SYSTEM_PROMPT
from app.tools import TOOL_DISPATCH, TOOL_SCHEMAS

MAX_TOOL_LOOPS = 10


def _client() -> AsyncOpenAI:
    s = get_settings()
    return AsyncOpenAI(api_key=s.openai_api_key or "no-key", base_url=s.openai_base_url)


def _truncate(value: Any, limit: int = 280) -> str:
    s = json.dumps(value, default=str)
    return s if len(s) <= limit else s[:limit] + "..."


async def _dispatch(name: str, args: dict[str, Any]) -> Any:
    fn = TOOL_DISPATCH.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return await fn(**args)
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:
        return {"error": f"Tool {name} crashed: {exc}"}


async def run_chat(
    user_messages: list[dict[str, str]],
) -> AsyncIterator[dict[str, Any]]:
    """Run the agent loop and yield events.

    Event shapes:
        {"type": "status", "message": "..."}
        {"type": "tool_call", "name": "...", "arguments": {...}}
        {"type": "tool_result", "name": "...", "preview": "..."}
        {"type": "delta", "content": "..."}
        {"type": "done"}
        {"type": "error", "message": "..."}
    """
    settings = get_settings()
    client = _client()

    messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": SYSTEM_PROMPT}]
    cleaned = [
        m for m in user_messages
        if (m.get("content") or "").strip() and m.get("role") in ("user", "assistant")
    ]
    if not cleaned or cleaned[-1].get("role") != "user":
        yield {"type": "error", "message": "No user message in request."}
        return
    messages.extend(cleaned)  # type: ignore[arg-type]

    yield {"type": "status", "message": "Beach, Please is thinking..."}

    for loop_idx in range(MAX_TOOL_LOOPS):
        try:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.7,
            )
        except Exception as exc:
            yield {"type": "error", "message": f"LLM call failed: {exc}"}
            return

        choice = response.choices[0]
        msg = choice.message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            content = msg.content or ""
            if content:
                yield {"type": "delta", "content": content}
            else:
                async for chunk in _stream_final(client, messages, settings.openai_model):
                    yield chunk
            yield {"type": "done"}
            return

        async def _run_one(tc) -> tuple[str, str, Any]:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = await _dispatch(tc.function.name, args)
            return tc.id, tc.function.name, result

        for tc in tool_calls:
            try:
                args_preview = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args_preview = tc.function.arguments
            yield {
                "type": "tool_call",
                "name": tc.function.name,
                "arguments": args_preview,
            }

        results = await asyncio.gather(*[_run_one(tc) for tc in tool_calls])

        if settings.tool_results_as_user:
            # Local LLM templates (e.g. LM Studio Qwen) often choke on the
            # OpenAI `tool` role. Workaround: keep the assistant turn brief
            # (just the model's own thinking, never the tool-call schema),
            # then deliver results as a synthetic user message. This avoids
            # teaching the model to imitate "I'll call: foo()" in plain text
            # instead of emitting real tool_calls next round.
            assistant_text = (msg.content or "").strip() or "(used tools)"
            messages.append({
                "role": "assistant",
                "content": assistant_text,
            })  # type: ignore[arg-type]
            result_lines = [
                f"### {name} returned:\n```json\n{json.dumps(result, default=str)}\n```"
                for _tc_id, name, result in results
            ]
            messages.append({
                "role": "user",
                "content": (
                    "[SYSTEM: Here are the results of the tools you just invoked. "
                    "Do NOT describe future tool calls in plain text — if you need "
                    "more data, emit real tool_calls. Otherwise, write the final "
                    "answer for the original user question now.]\n\n"
                    + "\n\n".join(result_lines)
                ),
            })  # type: ignore[arg-type]
        else:
            messages.append({
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            })  # type: ignore[arg-type]
            for tc_id, name, result in results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": json.dumps(result, default=str),
                })  # type: ignore[arg-type]

        for _tc_id, name, result in results:
            yield {
                "type": "tool_result",
                "name": name,
                "preview": _truncate(result),
            }

    yield {
        "type": "delta",
        "content": "I hit my own thinking limit. Beach, please \u2014 try a more specific question.",
    }
    yield {"type": "done"}


async def _stream_final(
    client: AsyncOpenAI,
    messages: list[ChatCompletionMessageParam],
    model: str,
) -> AsyncIterator[dict[str, Any]]:
    """Re-issue the final assistant turn with streaming so tokens flow to the UI."""
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            stream=True,
        )
    except Exception as exc:
        yield {"type": "error", "message": f"Streaming failed: {exc}"}
        return

    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield {"type": "delta", "content": delta.content}


async def generate_blurb(beach_data: dict[str, Any]) -> str:
    """One-shot sassy blurb generator for the beach card. Non-streaming."""
    from app.personality import SASSY_BLURB_PROMPT

    settings = get_settings()
    client = _client()

    prompt = SASSY_BLURB_PROMPT.format(data=json.dumps(beach_data, default=str)[:2000])
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=80,
        )
        return (resp.choices[0].message.content or "").strip().strip('"')
    except Exception:
        return _fallback_blurb(beach_data)


def _fallback_blurb(beach_data: dict[str, Any]) -> str:
    """Used when the LLM is offline. Still on-brand."""
    name = beach_data.get("beach", {}).get("name", "this beach")
    rip = (beach_data.get("rip_currents") or {}).get("risk", "Unknown")
    if rip == "High":
        return f"High rip current risk at {name}. Stay on the sand, drama queen."
    if rip == "Moderate":
        return f"Moderate rip currents at {name}. Swim near a lifeguard, not your ex."
    return f"{name} is serving conditions. Sunscreen up and read the report."
