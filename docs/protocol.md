# 协议转换规范

## 概述

LocalSwitch 的核心职责：**OpenAI Responses API ↔ OpenAI Chat Completions API** 的双向协议转换。

- **上游请求**：Codex CLI 使用 Responses API (`/v1/responses`)
- **下游转发**：Kimi Code 仅支持 Chat Completions API (`/v1/chat/completions`)

---

## Request 转换：Responses → Chat Completions

### 顶层字段映射

| Responses API | Chat Completions | 转换规则 |
|--------------|------------------|---------|
| `model` | `model` | 透传 |
| `input` | `messages` | `input` 字符串 → `[{"role":"user","content":"..."}]`<br>`input` 数组 → 遍历 items 按 `type` 转换 |
| `instructions` | `messages[0]` | 作为前置 `system` 消息 |
| `max_output_tokens` | `max_tokens` | 字段重命名 |
| `stream` | `stream` | 透传 |
| `temperature` | `temperature` | 透传 |
| `top_p` | `top_p` | 透传 |
| `stop` | `stop` | 透传 |
| `tools` | `tools` | 过滤 `namespace` 类型，保留 `function` |
| `tool_choice` | `tool_choice` | `namespace` → 回退为 `"auto"` |
| `text.format` | `response_format` | 结构转换（见下方） |

### `input` 字段转换

Responses API 的 `input` 支持多种类型：

```json
// 字符串形式
{"input": "hello"}

// 数组形式
{"input": [
  {"type": "message", "role": "user", "content": "hello"},
  {"type": "function_call", "call_id": "c1", "name": "foo", "arguments": "{}"},
  {"type": "function_call_output", "call_id": "c1", "output": "result"}
]}
```

转换规则：

| input item `type` | Chat message |
|-------------------|--------------|
| `message` | `{role, content}` |
| `function_call` | `{role:"assistant", content:"", tool_calls:[...]}` |
| `function_call_output` | `{role:"tool", tool_call_id, content}` |
| `input_image` | `{role:"user", content:[{"type":"image_url",...}]}` |
| `input_file` | 占位文本 `[File]` |

### Content Part 规范化

Responses API 的 `content` 可能是字符串或 content part 数组：

```json
{"type": "input_text", "text": "hello"}
{"type": "output_text", "text": "world"}
```

转换时统一提取 `text` 字段，拼接为纯字符串。

### Tools 过滤

Kimi Code 不支持 `namespace` 类型的 tools：

```json
// Responses API 中的 namespace tool（Kimi 不支持）
{"type": "namespace", "name": "mcp", "tools": [...]}

// 转换结果：提取内层 function tools
{"type": "function", "function": {"name": "...", "parameters": {...}}}
```

### Response Format 转换

```json
// Responses API 格式
{"text": {"format": {"type": "json_schema", "name": "schema1", "schema": {...}}}}

// Chat Completions 格式
{"response_format": {"type": "json_schema", "json_schema": {"name": "schema1", "schema": {...}}}}
```

---

## Response 转换：Chat Completions → Responses

### 非 Streaming 响应

```json
// Chat Completions 响应
{
  "id": "chatcmpl-xxx",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Hello!",
      "tool_calls": [...]
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}

// Responses API 响应
{
  "id": "resp_xxx",
  "object": "response",
  "created_at": 1234567890,
  "model": "kimi-for-coding",
  "status": "completed",
  "output": [
    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Hello!"}]}
  ],
  "usage": {
    "input_tokens": 10,
    "output_tokens": 20,
    "total_tokens": 30,
    "input_tokens_details": {"cached_tokens": 0},
    "output_tokens_details": {"reasoning_tokens": 0}
  }
}
```

### Streaming 响应（SSE）

Chat Completions streaming 的 SSE 格式：

```
data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"choices":[{"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

转换后的 Responses SSE 格式：

```
event: response.created
data: {"type":"response.created","response":{...},"sequence_number":0}

event: response.in_progress
data: {"type":"response.in_progress","response":{...},"sequence_number":1}

event: response.output_item.added
data: {"type":"response.output_item.added","output_index":0,"item":{...},"sequence_number":2}

event: response.content_part.added
data: {"type":"response.content_part.added","item_id":"msg_xxx","content_index":0,"part":{...},"sequence_number":3}

event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":"Hello",...,"sequence_number":4}

event: response.output_text.done
data: {"type":"response.output_text.done","text":"Hello",...,"sequence_number":5}

event: response.content_part.done
data: {"type":"response.content_part.done","part":{...},...,"sequence_number":6}

event: response.output_item.done
data: {"type":"response.output_item.done","output_index":0,"item":{...},...,"sequence_number":7}

event: response.completed
data: {"type":"response.completed","response":{...},"sequence_number":8}

event: done
data: {"type":"done","sequence_number":9}
```

### Streaming 状态机

```
Idle → Streaming → Done
 │        │
 │        ├─ response.created (seq=0)
 │        ├─ response.in_progress (seq=1)
 │        ├─ output_item.added (message)
 │        ├─ content_part.added
 │        ├─ output_text.delta * N
 │        ├─ output_text.done
 │        ├─ content_part.done
 │        ├─ output_item.done
 │        ├─ response.completed
 │        └─ done
 │
 └─ [DONE] 或 EOF 触发 Done
```

### 关键字段说明

| 字段 | 说明 | 必要性 |
|------|------|--------|
| `sequence_number` | 单调递增，从 0 开始 | **必须**，Codex CLI 严格检查 |
| `response.created` | 响应开始事件 | **必须**，必须紧跟 `response.in_progress` |
| `response.in_progress` | 响应进行中 | **必须**，必须与 `created` 成对出现 |
| `response.completed` | 响应完成 | **必须**，包含完整 envelope |
| `envelope` | 包含原始请求字段 | **必须**，Codex 用其反向路由 tools |

### Envelope 字段

`response.completed` 的 `response` 对象必须包含：

```json
{
  "id": "resp_xxx",
  "object": "response",
  "created_at": 1234567890,
  "status": "completed",
  "model": "kimi-for-coding",
  "tools": [],
  "tool_choice": "auto",
  "parallel_tool_calls": true,
  "reasoning": {"effort": null, "summary": null},
  "text": {"format": {"type": "text"}},
  "metadata": null,
  "previous_response_id": null,
  "instructions": null,
  "temperature": null,
  "top_p": null,
  "max_output_tokens": null,
  "truncation": "disabled",
  "output": [...],
  "incomplete_details": null,
  "error": null,
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
    "input_tokens_details": {"cached_tokens": 0},
    "output_tokens_details": {"reasoning_tokens": 0}
  }
}
```

### Usage 字段兼容

Codex CLI 严格要求 `usage` 包含以下字段：

```json
{
  "input_tokens": 0,
  "output_tokens": 0,
  "total_tokens": 0,
  "input_tokens_details": {"cached_tokens": 0},
  "output_tokens_details": {"reasoning_tokens": 0}
}
```

缺失任何字段会导致 Codex 断开连接并重试。

---

## 特殊处理

### User-Agent 伪装

Kimi Code 端点检查 User-Agent 白名单。必须发送：

```
User-Agent: claude-code/2.1.0 (cli)
```

### Tools Namespace

Kimi 不支持 `type: "namespace"` 的 tools。处理方式：
1. 遍历 `tools` 数组
2. 跳过 `type: "namespace"` 的项
3. 如果 `namespace` 包含内层 `type: "function"` 的 tools，提取并保留
4. 如果 `tool_choice.type` 为 `"namespace"`，回退为 `"auto"`

### Reasoning Content

部分模型（DeepSeek、Kimi）在 streaming 中返回 `delta.reasoning_content`：

```json
{"choices":[{"delta":{"reasoning_content":"Thinking..."}}]}
```

当前版本将其视为普通 `content` 输出（不做 reasoning 特殊处理）。

### Annotations

URL citation annotations 在 streaming chunk 中可能出现在 `delta.annotations`：

```json
{"choices":[{"delta":{"annotations":[{"type":"url_citation","url":"..."}]}}]}
```

当前版本暂不做特殊转换。
