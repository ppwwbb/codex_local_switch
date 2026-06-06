# 问题解决全过程

## 背景问题

你的场景：
1. **Codex CLI** 使用 OpenAI **Responses API**（`POST /v1/responses`）
2. **Kimi Code** 端点只兼容 **Chat Completions API**（`POST /v1/chat/completions`）
3. **CC Switch** 是纯代理，不做协议转换，直接转发 → **400/403 报错**

LocalSwitch 的核心任务：**让 Codex 以为在和 Responses API 对话，实际在 Kimi 的 Chat Completions 上跑**。

---

## 第一步：请求链路建立

### 1.1 Codex 发出的请求

```bash
POST http://127.0.0.1:8317/v1/responses
Content-Type: application/json
Authorization: Bearer dummy-token

{
  "model": "kimi-for-coding",
  "input": "hello",
  "stream": true,
  "tools": [
    {"type": "namespace", "name": "mcp", "tools": [...]}
  ]
}
```

### 1.2 LocalSwitch 接收请求

```python
# proxy_server.py
@app.post("/v1/responses")
async def responses_endpoint(request: Request):
    body = await request.json()  # 拿到原始 Responses 请求体
```

### 1.3 遇到的第一个问题

Kimi 收到请求后直接 403：
```
"Kimi For Coding is currently only available for Coding Agents"
```

**原因**：Kimi 端点有 User-Agent 白名单，只接受来自 Claude Code CLI 的请求。

**解决**：
```python
headers = {
    "User-Agent": "claude-code/2.1.0 (cli)"  # 伪装成 Claude Code
}
```

---

## 第二步：Request 转换（Responses → Chat Completions）

### 2.1 原始请求体

Codex 发送的是 Responses API 格式：
```json
{
  "model": "kimi-for-coding",
  "input": [
    {"type": "message", "role": "user", "content": "hello"}
  ],
  "instructions": "You are a helpful assistant",
  "tools": [
    {"type": "namespace", "name": "mcp", "tools": [...]}
  ],
  "tool_choice": {"type": "namespace"},
  "text": {
    "format": {"type": "json_schema", "name": "schema1", "schema": {...}}
  },
  "max_output_tokens": 4096,
  "stream": true
}
```

### 2.2 转换函数

```python
# protocol_adapter.py
chat_payload = responses_to_chat_completions(body)
```

### 2.3 逐字段转换

| Responses 字段 | Chat Completions 字段 | 转换逻辑 |
|---------------|----------------------|---------|
| `input: "hello"` | `messages` | `[{"role":"user","content":"hello"}]` |
| `input: [{"type":"message",...}]` | `messages` | 遍历数组，按 `type` 转换每个 item |
| `instructions` | `messages[0]` | 转为 `{"role":"system","content":"..."}` |
| `tools: [{"type":"namespace"}]` | `tools` | **过滤掉 namespace**，只提取内层 function |
| `tool_choice: {"type":"namespace"}` | `tool_choice` | **回退为 `"auto"`** |
| `text.format` | `response_format` | 结构重组：`{type, json_schema: {name, schema}}` |
| `max_output_tokens` | `max_tokens` | 字段重命名 |
| `stream` | `stream` | 透传 |

### 2.4 转换后的请求体

```json
{
  "model": "kimi-for-coding",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "hello"}
  ],
  "tools": [
    {"type": "function", "function": {"name": "..."}}
  ],
  "tool_choice": "auto",
  "response_format": {
    "type": "json_schema",
    "json_schema": {"name": "schema1", "schema": {...}}
  },
  "max_tokens": 4096,
  "stream": true
}
```

### 2.5 发送给 Kimi

```python
# proxy_server.py
async with httpx_client.stream("POST", kimi_url, headers=headers, json=chat_payload) as resp:
    # 开始接收 streaming 响应
```

---

## 第三步：Kimi 返回的响应

### 3.1 Kimi 返回的 SSE 流

```
data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"choices":[{"delta":{"content":"!"},"finish_reason":null}]}

data: {"choices":[{"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### 3.2 解析每个 chunk

```python
# proxy_server.py
async for line in resp.aiter_lines():
    if line.startswith("data:"):
        data_str = line[len("data:"):].strip()
        chunk = json.loads(data_str)  # 解析为 dict
```

### 3.3 遇到的第二个问题

**问题 A：Kimi 的 SSE 格式中 `data:` 后面没有空格**

之前代码只匹配 `data: `（带空格），导致所有 chunk 被跳过 → **Codex 看不到任何数据**。

**解决**：兼容有无空格两种格式：
```python
if line.startswith("data:"):
    data_str = line[len("data:"):].strip()
```

**问题 B：`delta.content` 可能是 null 或 list**

```python
content = delta.get("content")
if isinstance(content, list):
    content = normalize_content(content)  # 提取 text
```

**问题 C：`choices` 可能是 null**

```python
choices = chunk.get("choices") or []
choice = choices[0] if choices else {}
```

---

## 第四步：Response 转换（Chat Completions → Responses）

### 4.1 核心转换函数

```python
# protocol_adapter.py
events = translate_chat_stream_chunk(chunk, state, original_request)
```

### 4.2 状态机维护

用一个 `state` dict 维护跨 chunk 的状态：

```python
state = {
    "response_id": "resp_xxx",      # 本次响应唯一 ID
    "msg_id": "msg_xxx",            # message item ID
    "seq": 0,                        # sequence_number 计数器
    "buffer": "",                    # 累计的文本内容
    "started": False,               # 是否已发送 output_item.added
    "content_started": False,       # 是否已发送 content_part.added
    "done": False,                  # 是否已完成
    "finish_reason": None,          # 结束原因
    "usage": None,                  # usage 信息
}
```

### 4.3 每个 chunk 的处理

**第一个 chunk 收到时**（model 字段出现）：

```python
# 发送 response.created + response.in_progress（必须成对）
events.append(sse_event("response.created", {
    "type": "response.created",
    "response": envelope  # 包含原始请求的所有字段
}, seq=0))

events.append(sse_event("response.in_progress", {
    "type": "response.in_progress",
    "response": envelope
}, seq=1))
```

**收到 `delta.content` 时**：

```python
if not state["started"]:
    # 第一次收到 content，发送 output_item.added
    events.append(sse_event("response.output_item.added", {
        "type": "response.output_item.added",
        "output_index": 0,
        "item": {"type": "message", "status": "in_progress", "role": "assistant", "id": msg_id, "content": []}
    }, seq))
    state["started"] = True

if not state["content_started"]:
    # 第一次收到 content，发送 content_part.added
    events.append(sse_event("response.content_part.added", {
        "type": "response.content_part.added",
        "item_id": msg_id,
        "content_index": 0,
        "part": {"type": "output_text", "text": "", "annotations": []}
    }, seq))
    state["content_started"] = True

# 发送文本增量
events.append(sse_event("response.output_text.delta", {
    "type": "response.output_text.delta",
    "delta": content
}, seq))

state["buffer"] += content
```

**收到 `finish_reason` 时**：

```python
# 1. output_text.done
events.append(sse_event("response.output_text.done", {
    "type": "response.output_text.done",
    "text": state["buffer"]
}, seq))

# 2. content_part.done
events.append(sse_event("response.content_part.done", {
    "type": "response.content_part.done",
    "part": {"type": "output_text", "text": state["buffer"], "annotations": []}
}, seq))

# 3. output_item.done
events.append(sse_event("response.output_item.done", {
    "type": "response.output_item.done",
    "item": {"type": "message", "status": "completed", "content": [...]}
}, seq))

# 4. response.completed（含完整 envelope + usage）
events.append(sse_event("response.completed", {
    "type": "response.completed",
    "response": {
        "id": state["response_id"],
        "status": "completed",
        "output": [...],
        "usage": {
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0}
        }
    }
}, seq))

# 5. done
events.append(sse_event("done", {"type": "done"}, seq))
```

### 4.4 生成的 SSE 流

最终返回给 Codex 的是标准的 Responses SSE：

```
event: response.created
data: {"type":"response.created","response":{"id":"resp_xxx",...},"sequence_number":0}

event: response.in_progress
data: {"type":"response.in_progress","response":{...},"sequence_number":1}

event: response.output_item.added
data: {"type":"response.output_item.added","output_index":0,"item":{...},"sequence_number":2}

event: response.content_part.added
data: {"type":"response.content_part.added","item_id":"msg_xxx","content_index":0,"part":{...},"sequence_number":3}

event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":"Hello","sequence_number":4}

event: response.output_text.delta
data: {"type":"response.output_text.delta","delta":"!","sequence_number":5}

event: response.output_text.done
data: {"type":"response.output_text.done","text":"Hello!",...,"sequence_number":6}

event: response.content_part.done
data: {"type":"response.content_part.done","part":{...},...,"sequence_number":7}

event: response.output_item.done
data: {"type":"response.output_item.done","output_index":0,"item":{...},...,"sequence_number":8}

event: response.completed
data: {"type":"response.completed","response":{"id":"resp_xxx","status":"completed",...},"sequence_number":9}

event: done
data: {"type":"done","sequence_number":10}
```

### 4.5 关键注意事项

- **`sequence_number` 必须从 0 开始，严格递增**。Codex CLI 会检查，缺失或重复会导致断流重连。
- **`response.created` 和 `response.in_progress` 必须成对出现**，且顺序固定。
- **`envelope` 必须包含原始请求的所有字段**（`tools`, `tool_choice`, `reasoning`, `text` 等），Codex 用这些字段反向路由 namespace tools。
- **`usage` 必须包含 `cached_tokens` 和 `reasoning_tokens`**，否则 Codex 解析失败直接断流。

---

## 第五步：遇到的问题与解决

| 问题 | 现象 | 根因 | 解决 |
|------|------|------|------|
| 403 Forbidden | Kimi 返回"仅对 Coding Agents 开放" | User-Agent 不匹配 | 伪装为 `claude-code/2.1.0 (cli)` |
| 400 json_schema | "missing required parameter" | Responses `text.format` ≠ Chat `response_format` | 重组成 `{type, json_schema: {...}}` |
| 400 namespace | "unknown tool type: namespace" | Kimi 不支持 `type: "namespace"` | 过滤 namespace，提取内层 function |
| 400 input_text | "invalid part type: input_text" | Responses content part 数组不被接受 | `normalize_content()` 提取纯文本 |
| 无数据返回 | Codex 没有任何显示 | SSE 解析 `data: ` 要求空格，Kimi 无空格 | `startswith("data:")` + `.strip()` |
| 无数据返回 | Codex 收不到任何 event | `sequence_number` 缺失/不连续 | 每次 event 注入递增 `seq` |
| 无数据返回 | Codex 收不到任何 event | `envelope` 缺少 `tools/tool_choice` 等 | `_build_envelope()` 回灌原始请求字段 |
| 断流重连 | 收到数据后断开 | `usage` 缺少 `cached_tokens`/`reasoning_tokens` | `_normalize_usage()` 补全默认 0 |

---

## 第六步：总结

### 完整数据流

```
Codex CLI
  │ ① POST /v1/responses (Responses API)
  │
  ▼
LocalSwitch Proxy (端口 8317)
  │ ② 接收请求体
  │ ③ protocol_adapter.responses_to_chat_completions()
  │    - input → messages
  │    - tools 过滤 namespace
  │    - text.format → response_format
  │    - 伪装 User-Agent
  │ ④ 转发到 Kimi (Chat Completions)
  │
  ▼
Kimi Code API
  │ ⑤ 返回 Chat Completions SSE
  │
  ▼
LocalSwitch Proxy
  │ ⑥ 逐 chunk 读取 SSE
  │ ⑦ protocol_adapter.translate_chat_stream_chunk()
  │    - 维护状态机 (seq, buffer, flags)
  │    - 生成 response.created/in_progress
  │    - 生成 output_item/content_part/delta
  │    - 收到 finish_reason → 生成 done 事件
  │    - 构建完整 envelope + usage
  │ ⑧ 返回 Responses SSE 给 Codex
  │
  ▼
Codex CLI
  │ ⑨ 解析 Responses SSE，正常显示回复
```

### 核心设计

- **协议翻译层**（`protocol_adapter.py`）和 **HTTP 代理层**（`proxy_server.py`）完全解耦
- **状态机驱动**的 streaming 转换，保证 `sequence_number` 连续和事件顺序正确
- **防御式编程**：对 Kimi 的各种格式差异（空格、null、list 类型）做兼容处理
- **原始请求回灌**：`envelope` 完整保留原始请求字段，确保 Codex 反向路由 tools 不出错
