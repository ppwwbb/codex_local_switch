# LocalSwitch 项目文档

## 文档索引

| 文档 | 说明 |
|------|------|
| [api.md](api.md) | 前后端 REST API 接口规范 |
| [protocol.md](protocol.md) | OpenAI Responses API ↔ Chat Completions API 协议转换规范 |
| [architecture.md](architecture.md) | 项目架构设计与模块说明 |

## 快速启动

```bash
# 启动 Python 后端
python main.py

# 编译并运行 Tauri 前端
cd src-tauri
cargo tauri dev
```

## 项目结构

```
localswitch/
├── src/                    # Web 前端（HTML/CSS/JS）
├── src-tauri/              # Tauri Rust 窗口管理
├── backend/                # Python FastAPI 后端
├── docs/                   # 项目文档
├── config.py               # 配置模型与持久化
├── proxy_server.py         # 代理服务器（FastAPI）
├── protocol_adapter.py     # 协议转换核心
└── main.py                 # Python 入口
```
