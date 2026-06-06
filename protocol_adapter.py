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

def normalize_content(content: Any) -> str:
    """
    将 Responses API 中的 content 转换为纯文本字符串。

    Responses API 的 content 可能是：
    - 简单字符串
    - content part 数组，如 [{"type": "input_text", "text": "..."}, ...]
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict):
                part_type = part.get("type", "")
                if part_type in ("input_text", "output_text", "text"):
                    texts.append(part.get("text", ""))
                elif part_type == "refusal":
                    texts.append(part.get("refusal", ""))
                # input_image 等暂不支持转换为文本，直接跳过
        return "\n".join(texts)
    return str(content) if content is not None else ""


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
                content = normalize_content(item.get("content", ""))
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


def filter_and_convert_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    过滤掉 Kimi 不支持的 tool 类型（如 namespace），只保留 function 类型。
    如果 namespace 内嵌有子 tools，会递归提取其中的 function。
    """
    result = []
    for t in tools:
        t_type = t.get("type")
        if t_type == "function":
            result.append(convert_tool_name_for_chat(t))
        elif t_type == "namespace":
            # namespace 类型可能包含子 tools，尝试提取 function
            for sub in t.get("tools", []):
                if sub.get("type") == "function":
                    result.append(convert_tool_name_for_chat(sub))
        # 忽略其他不支持的类型（plugin 等如需支持可在此扩展）
    return result


def convert_response_format(fmt: Any) -> Any:
    """
    将 Responses API 的 text.format 转换为 Chat Completions API 的 response_format。

    Responses API 中 json_schema 的格式:
        {"type": "json_schema", "name": "...", "schema": {...}, "strict": true}

    Chat Completions API 中需要的格式:
        {"type": "json_schema", "json_schema": {"name": "...", "schema": {...}, "strict": true}}
    """
    if not isinstance(fmt, dict):
        return fmt
    fmt_type = fmt.get("type")
    if fmt_type == "json_schema":
        return {
            "type": "json_schema",
            "json_schema": {
                "name": fmt.get("name", "schema"),
                "schema": fmt.get("schema", {}),
                "strict": fmt.get("strict", False),
            }
        }
    elif fmt_type == "json_object":
        return {"type": "json_object"}
    # 其他类型（text 等）直接透传
    return fmt


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

    # tools / tool_choice（过滤不支持的 namespace 等类型）
    if "tools" in payload:
        result["tools"] = filter_and_convert_tools(payload["tools"])
    if "tool_choice" in payload:
        tc = payload["tool_choice"]
        # Kimi 不支持 namespace 相关的 tool_choice，若出现则回退为 auto
        if isinstance(tc, dict) and tc.get("type") == "namespace":
            result["tool_choice"] = "auto"
        else:
            result["tool_choice"] = tc

    # response_format（转换 json_schema 等格式差异）
    if "text" in payload and isinstance(payload["text"], dict):
        text_cfg = payload["text"]
        if text_cfg.get("format"):
            result["response_format"] = convert_response_format(text_cfg["format"])
    elif "response_format" in payload:
        result["response_format"] = convert_response_format(payload["response_format"])

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

def _build_envelope(response_id: str, created_at: int, model: str, status: str,
                    original_request: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """构造 Responses 协议 envelope，回灌原始请求字段以保证协议合规。"""
    req = original_request or {}
    return {
        "id": response_id,
        "object": "response",
        "created_at": created_at,
        "status": status,
        "model": model or "unknown",
        "tools": req.get("tools", []),
        "tool_choice": req.get("tool_choice", "auto"),
        "parallel_tool_calls": req.get("parallel_tool_calls", True),
        "reasoning": req.get("reasoning", {"effort": None, "summary": None}),
        "text": req.get("text", {"format": {"type": "text"}}),
        "metadata": req.get("metadata", None),
        "previous_response_id": req.get("previous_response_id", None),
        "instructions": req.get("instructions", None),
        "temperature": req.get("temperature", None),
        "top_p": req.get("top_p", None),
        "max_output_tokens": req.get("max_output_tokens", None),
        "truncation": "disabled",
    }


def _sse_event(event: str, data: Dict[str, Any], seq: int) -> str:
    """生成 SSE event，payload 中注入 sequence_number。"""
    data["sequence_number"] = seq
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _normalize_usage_to_responses(usage: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """把 Chat Completions usage 翻译为 Responses 风格，并补全必需字段。"""
    if not usage:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        }
    already_responses = "input_tokens" in usage or "output_tokens" in usage
    input_tokens = usage.get("input_tokens" if already_responses else "prompt_tokens", 0)
    output_tokens = usage.get("output_tokens" if already_responses else "completion_tokens", 0)
    total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    }


def translate_chat_stream_chunk(chunk: Dict[str, Any], state: Dict[str, Any],
                                original_request: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    逐 chunk 实时转换 Chat Completions streaming chunk -> Responses SSE events

    state 用于维护跨 chunk 的状态，首次调用前传 {}。
    original_request 为入站 Responses API 原始 body，用于 envelope 回灌字段。
    返回一个 event 字符串列表（可能为空）。
    """
    events = []
    choices = chunk.get("choices")
    if choices is None or len(choices) == 0:
        choices = [{}]
    choice = choices[0]
    delta = choice.get("delta") or {}
    finish_reason = choice.get("finish_reason")
    model = chunk.get("model", "")
    usage = chunk.get("usage")
    if not usage and choice.get("usage"):
        usage = choice["usage"]

    # 初始化状态
    if "response_id" not in state:
        state["response_id"] = generate_response_id()
        state["msg_id"] = generate_message_id()
        state["created_at"] = int(time.time())
        state["role"] = "assistant"
        state["started"] = False
        state["content_started"] = False
        state["done"] = False
        state["seq"] = 0
        state["buffer"] = ""
        state["finish_reason"] = None
        state["usage"] = None

        # response.created + response.in_progress（OpenAI 协议要求成对出现）
        envelope = _build_envelope(state["response_id"], state["created_at"], model, "in_progress", original_request)
        envelope["output"] = []
        envelope["usage"] = None
        envelope["incomplete_details"] = None
        envelope["error"] = None

        events.append(_sse_event("response.created", {
            "type": "response.created",
            "response": envelope.copy(),
        }, state["seq"]))
        state["seq"] += 1

        events.append(_sse_event("response.in_progress", {
            "type": "response.in_progress",
            "response": envelope,
        }, state["seq"]))
        state["seq"] += 1

    if state.get("done"):
        return events

    if delta.get("role"):
        state["role"] = delta["role"]

    if model and not state.get("model"):
        state["model"] = model

    if usage:
        state["usage"] = usage

    # 开始 output item
    if not state["started"]:
        state["started"] = True
        events.append(_sse_event("response.output_item.added", {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {
                "type": "message",
                "status": "in_progress",
                "role": state["role"],
                "id": state["msg_id"],
                "content": [],
            }
        }, state["seq"]))
        state["seq"] += 1

    content = delta.get("content")
    if isinstance(content, list):
        content = normalize_content(content)
    elif not isinstance(content, str):
        content = str(content) if content is not None else ""

    if content and not state["content_started"]:
        state["content_started"] = True
        events.append(_sse_event("response.content_part.added", {
            "type": "response.content_part.added",
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": "", "annotations": []}
        }, state["seq"]))
        state["seq"] += 1

    if content:
        state["buffer"] += content
        events.append(_sse_event("response.output_text.delta", {
            "type": "response.output_text.delta",
            "item_id": state["msg_id"],
            "output_index": 0,
            "content_index": 0,
            "delta": content,
        }, state["seq"]))
        state["seq"] += 1

    if finish_reason:
        state["finish_reason"] = finish_reason
        if state["content_started"]:
            events.append(_sse_event("response.output_text.done", {
                "type": "response.output_text.done",
                "item_id": state["msg_id"],
                "output_index": 0,
                "content_index": 0,
                "text": state["buffer"],
            }, state["seq"]))
            state["seq"] += 1

            events.append(_sse_event("response.content_part.done", {
                "type": "response.content_part.done",
                "item_id": state["msg_id"],
                "output_index": 0,
                "content_index": 0,
                "part": {
                    "type": "output_text",
                    "text": state["buffer"],
                    "annotations": [],
                },
            }, state["seq"]))
            state["seq"] += 1

        events.append(_sse_event("response.output_item.done", {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {
                "type": "message",
                "status": "completed",
                "role": state["role"],
                "id": state["msg_id"],
                "content": [{"type": "output_text", "text": state["buffer"], "annotations": []}],
            }
        }, state["seq"]))
        state["seq"] += 1

        # response.completed envelope
        status = "completed"
        incomplete_details = None
        if finish_reason in ("stop", "tool_calls", "function_call"):
            status = "completed"
        elif finish_reason == "length":
            status = "incomplete"
            incomplete_details = {"reason": "max_output_tokens"}
        elif finish_reason == "content_filter":
            status = "incomplete"
            incomplete_details = {"reason": "content_filter"}
        elif finish_reason:
            status = "incomplete"
            incomplete_details = {"reason": finish_reason}

        envelope = _build_envelope(state["response_id"], state["created_at"],
                                   state.get("model", model), status, original_request)
        envelope["output"] = [
            {
                "type": "message",
                "status": "completed",
                "role": state["role"],
                "id": state["msg_id"],
                "content": [{"type": "output_text", "text": state["buffer"], "annotations": []}],
            }
        ]
        envelope["incomplete_details"] = incomplete_details
        envelope["error"] = None
        envelope["usage"] = _normalize_usage_to_responses(state.get("usage"))

        events.append(_sse_event("response.completed", {
            "type": "response.completed",
            "response": envelope,
        }, state["seq"]))
        state["seq"] += 1

        events.append(_sse_event("done", {"type": "done"}, state["seq"]))
        state["seq"] += 1
        state["done"] = True

    return events
