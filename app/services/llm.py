"""OpenAI GPT wrapper with tool-calling support."""

import asyncio
import json
import logging

import openai

from app.config import get_settings

logger = logging.getLogger(__name__)


async def call_llm(
    messages: list[dict],
    tools: list[dict] | None = None,
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> object:
    """Call OpenAI with messages and optional tools.

    Returns the response message object from the API (an OpenAI
    ``ChatCompletionMessage``).
    """
    settings = get_settings()
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    kwargs: dict = {
        "model": settings.OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    try:
        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message
    except openai.APIError as exc:
        logger.error("OpenAI API error: %s", exc)
        raise


async def call_llm_with_tools(
    messages: list[dict],
    tools: list[dict],
    tool_handlers: dict[str, callable],
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> str:
    """Call LLM with tools, execute any tool calls, and return the final text
    response.

    The function loops: call the LLM, if the response contains tool calls
    execute them, append results back, and call the LLM again.  Stops when the
    LLM returns a plain text response or after 5 iterations.
    """
    settings = get_settings()
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    current_messages = list(messages)

    for _ in range(5):
        kwargs: dict = {
            "model": settings.OPENAI_MODEL,
            "messages": current_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await client.chat.completions.create(**kwargs)
        except openai.APIError as exc:
            logger.error("OpenAI API error during tool loop: %s", exc)
            return "I'm sorry, I'm having trouble processing that right now."

        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or ""

        # Append assistant message with tool calls
        current_messages.append(msg.model_dump())

        for tc in msg.tool_calls:
            handler = tool_handlers.get(tc.function.name)
            if handler:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**args)
                else:
                    result = handler(**args)

                result_str = json.dumps(result) if not isinstance(result, str) else result
            else:
                result_str = json.dumps({"error": f"Unknown tool: {tc.function.name}"})

            current_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    # Fallback if we exhausted iterations
    return "I'm sorry, I'm having trouble processing that. Could you try rephrasing?"
