# 架构设计文档

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      LocalSwitch Desktop                       │
│  ┌─────────────────┐          ┌──────────────────────────┐  │
│  │  Tauri Window   │          │    WebView Frontend      │  │
│  │  (Rust)         │◄────────►│    (HTML/CSS/JS)         │  │
│  │  - 窗口管理      │          │    - Provider 配置页       │  │
│  │  - 进程管理      │          │    - 代理控制页           │  │
│  │  - 系统托盘      │          │    - 设置页              │  │
│  └─────────────────┘          └──────────────────────────┘  │
│                        │                                       │
│                        │ fetch http://127.0.0.1:8318/api/*     │
│                        ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              Python Backend (FastAPI)                     │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │ │
│  │  │ API Server   │  │ Proxy Server │  │ Protocol     │   │ │
│  │  │ (端口 8318)   │  │ (端口 8317)   │  │ Adapter      │   │ │
│  │  │ - 配置管理    │  │ - 请求转发    │  │ - Responses  │   │ │
│  │  │ - 日志查询    │  │ - SSE流处理   │  │   ↔ Chat    │   │ │
│  │  │ - 统计聚合    │  │ - 头伪装      │  │   双向转换   │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP / SSE
                              ▼
                     ┌─────────────────┐
                     │  Kimi Code API  │
                     │ (上游 Provider)  │
                     └─────────────────┘
```

## 模块职责

### 1. Tauri (Rust)

**文件**: `src-tauri/src/main.rs`

| 职责 | 说明 |
|------|------|
| 窗口管理 | 创建 1000×720 主窗口，含系统标题栏 |
| 进程管理 | 启动时自动启动 Python 子进程，关闭时终止 |
| WebView | 加载前端页面（开发模式访问 `localhost:8318`，生产模式内嵌） |

**不处理业务逻辑**，纯窗口/进程管理。

### 2. Web 前端

**文件**: `src/index.html`, `src/style.css`, `src/main.js`

| 页面 | 功能 |
|------|------|
| Provider 配置 | 卡片列表、预设添加、模态框编辑、操作按钮（启用/测速/修改/复制/删除） |
| 代理控制 | 状态卡片、启动/停止、端口配置、日志查看、统计卡片 |
| 设置 | 主题切换、语言、开机自启 |

**通信方式**: 通过 `fetch()` 直接调用 Python FastAPI（`http://127.0.0.1:8318/api/*`）。

### 3. Python API Server

**文件**: `backend/api_server.py`

| 端点 | 功能 |
|------|------|
| `/api/providers` | Provider CRUD |
| `/api/proxy/start` | 启动代理服务 |
| `/api/proxy/stop` | 停止代理服务 |
| `/api/proxy/status` | 查询代理状态 |
| `/api/logs` | 获取日志和统计 |
| `/api/log/clear` | 清除日志 |
| `/`, `/style.css`, `/main.js` | 静态文件服务（前端页面） |

**FastAPI + Uvicorn**，端口 `8318`。

### 4. Proxy Server

**文件**: `proxy_server.py`

| 端点 | 功能 |
|------|------|
| `/health` | 健康检查 |
| `/v1/models` | 模型列表 |
| `/v1/responses` | Responses API → 协议转换 → Chat Completions |
| `/v1/chat/completions` | Chat Completions 透传 |

**FastAPI + httpx (async)**，端口 `8317`。

### 5. Protocol Adapter

**文件**: `protocol_adapter.py`

| 函数 | 功能 |
|------|------|
| `responses_to_chat_completions()` | Request 转换 |
| `chat_completions_to_responses()` | Response 转换（非 streaming） |
| `translate_chat_stream_chunk()` | Streaming chunk 转换 |
| `_build_envelope()` | 构造完整 Responses envelope |
| `_normalize_usage_to_responses()` | Usage 格式补全 |
| `_sse_event()` | SSE 事件格式化（含 sequence_number） |

---

## 数据流

### 正常请求流

```
Codex CLI
  │ POST /v1/responses (Responses API)
  ▼
Proxy Server (端口 8317)
  │ 1. 解析请求体
  │ 2. protocol_adapter.responses_to_chat_completions()
  ▼
Kimi Code API
  │ POST /v1/chat/completions
  ▼
Proxy Server
  │ 3. 接收 Chat Completions 响应
  │ 4. protocol_adapter.chat_completions_to_responses()
  ▼
Codex CLI
  │ 收到 Responses API 格式响应
```

### Streaming 请求流

```
Codex CLI
  │ POST /v1/responses stream=true
  ▼
Proxy Server
  │ 1. 转换请求 → Chat Completions
  │ 2. 向上游发送 stream=true
  ▼
Kimi Code API
  │ 返回 SSE stream
  ▼
Proxy Server
  │ 3. 逐 chunk 读取 SSE
  │ 4. protocol_adapter.translate_chat_stream_chunk()
  │ 5. 生成 Responses SSE 事件
  ▼
Codex CLI
  │ 收到 Responses SSE stream
```

### 前端管理流

```
用户操作 (Tauri WebView)
  │ fetch /api/providers
  ▼
API Server (端口 8318)
  │ 读写 config.json
  ▼
用户操作
  │ fetch /api/proxy/start
  ▼
API Server
  │ 调用 ProxyServer.start()
  │ Proxy 开始监听 8317
```

---

## 配置持久化

**文件**: `~/.localswitch/config.json`

```json
{
  "listen_host": "127.0.0.1",
  "listen_port": 8317,
  "providers": [
    {
      "id": "provider_xxx",
      "name": "Kimi Code",
      "api_key": "sk-...",
      "base_url": "https://api.kimi.com/coding/v1",
      "model": "kimi-for-coding",
      "enabled": true
    }
  ],
  "current_provider_id": "provider_xxx"
}
```

---

## 端口分配

| 端口 | 服务 | 用途 |
|------|------|------|
| 8317 | Proxy Server | Codex/Claude Code 连接 |
| 8318 | API Server | 前端管理界面调用 |

---

## 打包与部署

### 开发模式

```bash
# 1. 启动 Python 后端
python main.py

# 2. 启动 Tauri 开发模式
cd src-tauri
cargo tauri dev
```

### Release 构建

```bash
cd src-tauri
cargo tauri build
```

输出:
- `src-tauri/target/release/localswitch.exe` — 主程序
- `src-tauri/target/release/bundle/` — 安装包（msi, nsis）

### 运行时依赖

| 依赖 | 说明 |
|------|------|
| Python 3.8+ | 后端运行时 |
| WebView2 Runtime | Windows 系统通常已自带 |
| Rust Runtime | 已静态链接到 exe 中 |

---

## 扩展点

| 扩展方向 | 文件 | 说明 |
|----------|------|------|
| 新增 Provider | `config.py` + 前端 preset | 在 PRESET_PROVIDERS 中添加 |
| 新增协议转换 | `protocol_adapter.py` | 添加新的字段映射 |
| 新增前端页面 | `src/index.html` + `main.js` | 添加新的 tab 或功能 |
| 新增 API | `backend/api_server.py` | 添加新的 FastAPI 路由 |
| 打包平台 | `src-tauri/tauri.conf.json` | 配置 macOS/Linux 打包 |
