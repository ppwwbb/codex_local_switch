# LocalSwitch

本地 API 协议转换代理，解决 Codex 与 Kimi Code 等仅兼容 Chat Completions API 的端点之间的协议不匹配问题。

## 项目背景

在使用 Codex + CC Switch 接入 Kimi Code 模型时，遇到以下兼容性问题：
- Codex 默认使用 OpenAI **Responses API**（`/v1/responses`）
- Kimi Code 端点（`https://api.kimi.com/coding/v1`）仅兼容 **Chat Completions API**
- CC Switch 作为单纯代理无法解决协议层不匹配

LocalSwitch 作为本地协议翻译代理，接收 Codex 的 Responses API 请求，翻译为 Chat Completions 格式后转发到上游 Provider，再将响应翻译回 Responses 格式返回。

## 功能特性

- **协议转换**：Responses API ↔ Chat Completions API（支持文本输出与工具调用）
- **流式支持**：支持 SSE streaming 模式的实时转换
- **图形界面**：基于 tkinter 的可视化配置界面，参考 CC Switch 布局，零额外依赖
- **多 Provider 架构**：代码结构预留多 Provider 扩展（当前版本管理多个配置，运行时激活一个）
- **配置持久化**：配置自动保存到 `~/.localswitch/config.json`

## 环境要求

- Python 3.7+
- Windows / macOS / Linux

## 安装

```bash
# 克隆仓库
git clone <repo-url>
cd localswitch

# 安装依赖
pip install -r requirements.txt
```

## 使用

```bash
python main.py
```

### 快速开始

1. **配置 Provider**
   - 打开 "Provider 配置" 标签页
   - 选择默认 Provider 或点击「+ 添加」新建
   - 填写：
     - 名称：`Kimi Code`
     - Base URL：`https://api.kimi.com/coding/v1`
     - API Key：你的 Kimi Code API Key
     - 默认模型：`kimi-k2-0711-preview`
   - 点击「保存当前配置」

2. **启动代理**
   - 切换到 "代理控制" 标签页
   - 确认监听地址和端口（默认 `127.0.0.1:8317`）
   - 点击「▶ 启动代理」

3. **配置 Codex / Claude Code**
   - 若使用 Claude Code：
     ```bash
     export ANTHROPIC_BASE_URL=http://127.0.0.1:8317/v1
     export ANTHROPIC_AUTH_TOKEN=任意值（LocalSwitch 会自动替换为真实 Key）
     ```
   - 若 Codex 使用 OpenAI 协议：
     ```bash
     export OPENAI_BASE_URL=http://127.0.0.1:8317/v1
     export OPENAI_API_KEY=任意值
     ```

## 项目结构

```
localswitch/
├── main.py              # 程序入口
├── config.py            # 配置模型与持久化
├── proxy_server.py      # FastAPI 代理服务器
├── protocol_adapter.py  # 协议转换核心
├── gui/
│   ├── main_window.py   # 主窗口
│   ├── provider_tab.py  # Provider 配置页
│   ├── proxy_tab.py     # 代理控制/日志页
│   └── log_widget.py    # 日志组件
├── requirements.txt
└── README.md
```

## 技术栈

- **HTTP 服务端**：FastAPI + Uvicorn
- **HTTP 客户端**：httpx（异步 + streaming 支持）
- **GUI**：tkinter（Python 内置，零额外依赖）
- **配置**：dataclasses + JSON

## 协议转换细节

### Request 转换

| Responses API | Chat Completions |
|--------------|------------------|
| `input` (str/list) | `messages` |
| `instructions` | `messages` 前置 `system` |
| `max_output_tokens` | `max_tokens` |
| `tools` / `tool_choice` | 字段映射（名称兼容调整） |
| `text.format` | `response_format` |

### Response 转换

| Chat Completions | Responses API |
|-----------------|---------------|
| `choices[0].message.content` | `output[0].content[0].text` |
| `choices[0].message.tool_calls` | `output[*].type=function_call` |
| `usage.prompt_tokens` | `usage.input_tokens` |
| `usage.completion_tokens` | `usage.output_tokens` |

## 验证

启动代理后，可用 curl 测试：

```bash
curl http://127.0.0.1:8317/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test" \
  -d '{"model":"kimi-k2-0711-preview","input":"hello"}'
```

## 许可证

MIT
