"""
协议转换模块：OpenAI Responses API <=> Chat Completions API

核心职责：
1. 将 Codex 发来的 Responses 请求体翻译为 Chat Completions 请求体
2. 将上游返回的 Chat Completions 响应翻译回 Responses 响应格式
3. 支持 streaming 与非 streaming 两种模式
"""
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Request 转换：Responses -> Chat Completions
# ---------------------------------------------------------------------------

def responses_input_to_messages(input_value: Any, instructions: Optional[str] = None) -> List[Dict[str, Any]]:
    """将 Responses API 的 input 字段转换为 Chat Completions 的 messages 列表"""
    messages = []

    if instructions:
        messages.append({"role": "system", "content": instructions})

    if isinstance(input_value, str):
        messages.append({"role": "user", "content": input_value})
    elif isinstance(input_value, list):
        for item in input_value:
            if isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content", "")
                # Responses API 可能使用 developer role，映射为 system
                if role == "developer":
                    role = "system"
                messages.append({"role": role, "content": content})
    return messages


def convert_tool_name_for_chat(tool: Dict[str, Any]) -> Dict[str, Any]:
    """将 Responses API 的 tool 格式转换为 Chat Completions 格式"""
    tool = dict(tool)
    if tool.get("type") == "function":
        # Responses API 中可能使用 name 字段，Chat Completions 使用 function.name
        if "name" in tool and "function" not in tool:
            tool["function"] = {"name": tool.pop("name")}
            if "parameters" in tool:
                tool["function"]["parameters"] = tool.pop("parameters")
            if "description" in tool:
                tool["function"]["description"] = tool.pop("description")
    return tool


def responses_to_chat_completions(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 Responses API 请求体翻译为 Chat Completions 请求体
    """
    result = {
        "model": payload.get("model", "kimi-k2-0711-preview"),
        "messages": responses_input_to_messages(
            payload.get("input", ""),
            payload.get("instructions")
        ),
    }

    # 透传常见参数（若存在则加入）
    for key in ("temperature", "top_p", "frequency_penalty", "presence_penalty",
                "stop", "seed", "n", "stream", "user"):
        if key in payload:
            result[key] = payload[key]

    # max_output_tokens -> max_tokens
    if "max_output_tokens" in payload:
        result["max_tokens"] = payload["max_output_tokens"]
    elif "max_tokens" in payload:
        result["max_tokens"] = payload["max_tokens"]

    # tools / tool_choice
    if "tools" in payload:
        result["tools"] = [convert_tool_name_for_chat(t) for t in payload["tools"]]
    if "tool_choice" in payload:
        result["tool_choice"] = payload["tool_choice"]

    # response_format（如有）
    if "text" in payload and isinstance(payload["text"], dict):
        text_cfg = payload["text"]
        if text_cfg.get("format"):
            result["response_format"] = text_cfg["format"]
    elif "response_format" in payload:
        result["response_format"] = payload["response_format"]

    return result


# ---------------------------------------------------------------------------
# Response 转换：Chat Completions -> Responses
# ---------------------------------------------------------------------------

def generate_response_id() -> str:
    return "resp_" + uuid.uuid4().hex[:16]


def generate_message_id() -> str:
    return "msg_" + uuid.uuid4().hex[:16]


def chat_choice_to_response_output(choice: Dict[str, Any]) -> List[Dict[str, Any]]:
    """将 Chat Completions choice 翻译为 Responses output 列表"""
    message = choice.get("message", {})
    if not message:
        message = choice.get("delta", {})  # streaming chunk 中的 delta

    role = message.get("role", "assistant")
    content = message.get("content")
    tool_calls = message.get("tool_calls")
    finish_reason = choice.get("finish_reason")

    output = []

    # 普通文本内容
    if content:
        output.append({
            "type": "message",
            "id": generate_message_id(),
            "role": role,
            "content": [
                {"type": "output_text", "text": content}
            ],
        })

    # tool_calls
    if tool_calls:
        for tc in tool_calls:
            function_info = tc.get("function", {})
            output.append({
                "type": "function_call",
                "id": tc.get("id", generate_message_id()),
                "call_id": tc.get("id", generate_message_id()),
                "name": function_info.get("name", ""),
                "arguments": function_info.get("arguments", ""),
            })

    return output


def chat_usage_to_response_usage(usage: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not usage:
        return {}
    return {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def chat_completions_to_responses(chat_resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 Chat Completions 响应翻译为 Responses 响应格式
    """
    choice = chat_resp.get("choices", [{}])[0]
    output = chat_choice_to_response_output(choice)

    return {
        "id": generate_response_id(),
        "object": "response",
        "created_at": int(time.time()),
        "model": chat_resp.get("model", ""),
        "output": output,
        "usage": chat_usage_to_response_usage(chat_resp.get("usage")),
        "incomplete_details": None,
        "instructions": None,
        "max_output_tokens": None,
        "parallel_tool_calls": True,
        "previous_response_id": None,
        "reasoning": {"effort": None, "generate_summary": None},
        "status": "completed",
        "temperature": None,
        "text": {"format": {"type": "text"}},
        "tool_choice": "auto",
        "tools": [],
        "top_p": None,
        "truncation": "disabled",
        "user": None,
    }


# ---------------------------------------------------------------------------
# Streaming 转换：Chat Completions SSE -> Responses SSE
# ---------------------------------------------------------------------------

def build_streaming_events(chat_chunks: List[Dict[str, Any]], model: str) -> List[str]:
    """
    将多个 Chat Completions streaming chunk 聚合后生成 Responses streaming events 列表

    注意：本函数用于聚合模式（一次性拿到所有 chunks）。
    若需逐 chunk 实时转换，请使用 translate_chat_stream_chunk。
    """
    events = []
    response_id = generate_response_id()
    msg_id = generate_message_id()
    created_at = int(time.time())

    # 1. response.created
    events.append(_sse_event("response.created", {
        "type": "response.created",
        "response": {
            "id": response_id,
            "object": "response",
            "created_at": created_at,
            "model": model,
            "output": [],
            "usage": None,
        }
    }))

    # 2. 收集 content
    content_parts = []
    role = "assistant"
    finish_reason = None

    for chunk in chat_chunks:
        choice = chunk.get("choices", [{}])[0]
        delta = choice.get("delta", {})
        if delta.get("role"):
            role = delta["role"]
        if delta.get("content"):
            content_parts.append(delta["content"])
        if choice.get("finish_reason"):
            finish_reason = choice["finish_reason"]

    text = "".join(content_parts)

    if text:
        # output_item.added
        events.append(_sse_event("response.output_item.added", {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "type": "message",
                "id": msg_id,
                "role": role,
                "content": [],
            }
        }))

        # content_part.added
        events.append(_sse_event("response.content_part.added", {
            "type": "response.content_part.added",
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": ""}
        }))

        # output_text.delta
        events.append(_sse_event("response.output_text.delta", {
            "type": "response.output_text.delta",
            "output_index": 0,
            "content_index": 0,
            "delta": text,
        }))

        # output_text.done
        events.append(_sse_event("response.output_text.done", {
            "type": "response.output_text.done",
            "output_index": 0,
            "content_index": 0,
        }))

        # output_item.done
        events.append(_sse_event("response.output_item.done", {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {
                "type": "message",
                "id": msg_id,
                "role": role,
                "content": [{"type": "output_text", "text": text}],
            }
        }))

    # 3. response.completed
    events.append(_sse_event("response.completed", {
        "type": ".response.completed",
        "response": {
            "id": response_id,
            "object": "response",
            "created_at": created_at,
            "model": model,
            "output": [
                {
                    "type": "message",
                    "id": msg_id,
                    "role": role,
                    "content": [{"type": "output_text", "text": text}] if text else [],
                }
            ] if text else [],
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "status": "completed",
        }
    }))

    # 4. done
    events.append(_sse_event("done", {"type": "done"}))

    return events


def _sse_event(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def translate_chat_stream_chunk(chunk: Dict[str, Any], state: Dict[str, Any]) -> List[str]:
    """
    逐 chunk 实时转换 Chat Completions streaming chunk -> Responses SSE events

    state 用于维护跨 chunk 的状态，首次调用前传 {}。
    返回一个 event 字符串列表（可能为空）。
    """
    events = []
    choice = chunk.get("choices", [{}])[0]
    delta = choice.get("delta", {})
    finish_reason = choice.get("finish_reason")
    model = chunk.get("model", "")

    # 初始化状态
    if "response_id" not in state:
        state["response_id"] = generate_response_id()
        state["msg_id"] = generate_message_id()
        state["created_at"] = int(time.time())
        state["role"] = "assistant"
        state["started"] = False
        state["content_started"] = False
        state["done"] = False

        events.append(_sse_event("response.created", {
            "type": "response.created",
            "response": {
                "id": state["response_id"],
                "object": "response",
                "created_at": state["created_at"],
                "model": model,
                "output": [],
                "usage": None,
            }
        }))

    if state.get("done"):
        return events

    if delta.get("role"):
        state["role"] = delta["role"]

    # 开始 output item
    if not state["started"]:
        state["started"] = True
        events.append(_sse_event("response.output_item.added", {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "type": "message",
                "id": state["msg_id"],
                "role": state["role"],
                "content": [],
            }
        }))

    content = delta.get("content")
    if content and not state["content_started"]:
        state["content_started"] = True
        events.append(_sse_event("response.content_part.added", {
            "type": "response.content_part.added",
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": ""}
        }))

    if content:
        events.append(_sse_event("response.output_text.delta", {
            "type": "response.output_text.delta",
            "output_index": 0,
            "content_index": 0,
            "delta": content,
        }))

    if finish_reason:
        if state["content_started"]:
            events.append(_sse_event("response.output_text.done", {
                "type": "response.output_text.done",
                "output_index": 0,
                "content_index": 0,
            }))

        events.append(_sse_event("response.output_item.done", {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {
                "type": "message",
                "id": state["msg_id"],
                "role": state["role"],
                "content": [{"type": "output_text", "text": state.get("buffer", "")}] if state.get("buffer") else [],
            }
        }))

        events.append(_sse_event("response.completed", {
            "type": "response.completed",
            "response": {
                "id": state["response_id"],
                "object": "response",
                "created_at": state["created_at"],
                "model": model,
                "output": [],
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "status": "completed",
            }
        }))

        events.append(_sse_event("done", {"type": "done"}))
        state["done"] = True

    # 缓存已输出内容（用于最终的 output_item.done）
    if content:
        state["buffer"] = state.get("buffer", "") + content

    return events
