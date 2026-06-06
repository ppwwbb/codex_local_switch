# LocalSwitch API 接口规范

## 概述

前端（Tauri WebView）与 Python 后端通过 HTTP REST API 通信。

- **Base URL**: `http://127.0.0.1:8318`
- **Content-Type**: `application/json`
- **CORS**: 已开启，允许所有来源（本地应用）

---

## Provider 管理

### 获取 Provider 列表

```
GET /api/providers
```

**Response**:
```json
{
  "providers": [
    {
      "id": "provider_xxx",
      "name": "Kimi Code",
      "base_url": "https://api.kimi.com/coding/v1",
      "api_key": "sk-...",
      "model": "kimi-for-coding",
      "enabled": true
    }
  ],
  "current_id": "provider_xxx"
}
```

### 创建 Provider

```
POST /api/providers
```

**Response**:
```json
{
  "id": "provider_xxx"
}
```

### 更新 Provider

```
PUT /api/providers/{provider_id}
```

**Request Body**:
```json
{
  "name": "Kimi Code",
  "base_url": "https://api.kimi.com/coding/v1",
  "api_key": "sk-...",
  "model": "kimi-for-coding"
}
```

**Response**:
```json
{
  "ok": true
}
```

### 删除 Provider

```
DELETE /api/providers/{provider_id}
```

**Response**:
```json
{
  "ok": true
}
```

---

## 代理控制

### 获取代理状态

```
GET /api/proxy/status
```

**Response**:
```json
{
  "running": true,
  "host": "127.0.0.1",
  "port": 8317
}
```

### 启动代理

```
POST /api/proxy/start
```

**Request Body**:
```json
{
  "port": 8317
}
```

**Response**:
```json
{
  "ok": true
}
```

**Error Response** (400):
```json
{
  "detail": "No provider configured"
}
```

### 停止代理

```
POST /api/proxy/stop
```

**Response**:
```json
{
  "ok": true
}
```

---

## 日志与统计

### 获取日志

```
GET /api/logs
```

**Response**:
```json
{
  "entries": [
    {
      "timestamp": "14:32:01",
      "level": "INFO",
      "message": "代理启动成功..."
    }
  ],
  "stats": {
    "total": 10,
    "success": 8,
    "failed": 2,
    "today": 10
  }
}
```

### 清除日志

```
POST /api/log/clear
```

**Response**:
```json
{
  "ok": true
}
```

---

## 静态文件（前端页面）

前端页面由 Python 后端直接提供：

| 路径 | 文件 |
|------|------|
| `GET /` | `src/index.html` |
| `GET /style.css` | `src/style.css` |
| `GET /main.js` | `src/main.js` |

---

## Codex 代理接口（外部调用）

代理服务监听 `http://127.0.0.1:8317`，接收 Codex/Claude Code 的请求：

| 路径 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/models` | GET | 模型列表 |
| `/v1/responses` | POST | Responses API（转换后转发到 Chat Completions） |
| `/v1/chat/completions` | POST | Chat Completions 透传 |

---

## 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | Provider 不存在 |
| 503 | 未配置 Provider |
