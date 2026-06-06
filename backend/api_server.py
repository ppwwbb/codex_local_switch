"""
Python 后端 API 服务（FastAPI）
供前端 Web UI 调用，管理配置、代理启停、日志查询。
代理服务本身仍运行在独立端口（默认 8317），供 Codex 调用。
"""
import json
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_config, save_config, Provider
from proxy_server import ProxyServer


# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------

class ProviderUpdate(BaseModel):
    name: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class ProxyStartRequest(BaseModel):
    port: int = 8317


# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------

app = FastAPI(title="LocalSwitch API")

# CORS：允许前端页面访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内存中的日志环形缓冲区（最多保留 500 条）
_MAX_LOGS = 500
_log_buffer: List[Dict[str, Any]] = []
_log_lock = threading.Lock()
_log_counter = {"total": 0, "success": 0, "failed": 0, "today": 0}

# 代理服务实例
_proxy = ProxyServer(host="127.0.0.1", port=8317)


def _add_log(level: str, message: str) -> None:
    with _log_lock:
        entry = {
            "timestamp": time.strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        }
        _log_buffer.append(entry)
        if len(_log_buffer) > _MAX_LOGS:
            _log_buffer.pop(0)
        _log_counter["total"] += 1
        if level == "INFO":
            _log_counter["success"] += 1
        elif level == "ERROR":
            _log_counter["failed"] += 1
        _log_counter["today"] += 1


# 让 ProxyServer 的日志回灌到我们的缓冲区
def _proxy_log_callback(level: str, message: str) -> None:
    _add_log(level, message)


_proxy.set_log_callback(_proxy_log_callback)


# ---------------------------------------------------------------------------
# 静态文件服务（前端页面）
# ---------------------------------------------------------------------------

@app.get("/")
async def index():
    """返回前端主页面"""
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    return FileResponse(os.path.join(frontend_dir, "index.html"))


@app.get("/style.css")
async def style_css():
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    return FileResponse(os.path.join(frontend_dir, "style.css"), media_type="text/css")


@app.get("/main.js")
async def main_js():
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
    return FileResponse(os.path.join(frontend_dir, "main.js"), media_type="application/javascript")


# ---------------------------------------------------------------------------
# Provider API
# ---------------------------------------------------------------------------

@app.get("/api/providers")
async def get_providers():
    cfg = load_config()
    return {
        "providers": [
            {
                "id": p.id,
                "name": p.name,
                "base_url": p.base_url,
                "api_key": p.api_key,
                "model": p.model,
                "enabled": p.enabled,
            }
            for p in cfg.providers
        ],
        "current_id": cfg.current_provider_id,
    }


@app.post("/api/providers")
async def create_provider():
    cfg = load_config()
    new_id = "provider_" + uuid.uuid4().hex[:6]
    p = Provider(id=new_id, name="新 Provider")
    cfg.providers.append(p)
    if not cfg.current_provider_id:
        cfg.current_provider_id = new_id
    save_config(cfg)
    return {"id": new_id}


@app.put("/api/providers/{provider_id}")
async def update_provider(provider_id: str, body: ProviderUpdate):
    cfg = load_config()
    p = next((x for x in cfg.providers if x.id == provider_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    p.name = body.name or p.name
    p.base_url = body.base_url
    p.api_key = body.api_key
    p.model = body.model
    save_config(cfg)
    return {"ok": True}


@app.delete("/api/providers/{provider_id}")
async def delete_provider(provider_id: str):
    cfg = load_config()
    cfg.providers = [x for x in cfg.providers if x.id != provider_id]
    if cfg.current_provider_id == provider_id:
        cfg.current_provider_id = cfg.providers[0].id if cfg.providers else None
    save_config(cfg)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Proxy API
# ---------------------------------------------------------------------------

@app.get("/api/proxy/status")
async def proxy_status():
    cfg = load_config()
    return {
        "running": _proxy.is_running(),
        "host": cfg.listen_host,
        "port": cfg.listen_port,
    }


@app.post("/api/proxy/start")
async def proxy_start(req: ProxyStartRequest):
    cfg = load_config()
    provider = cfg.get_current_provider()
    if not provider:
        raise HTTPException(status_code=400, detail="No provider configured")
    if not provider.api_key:
        raise HTTPException(status_code=400, detail="API Key is empty")
    if not provider.base_url:
        raise HTTPException(status_code=400, detail="Base URL is empty")

    _proxy.host = cfg.listen_host
    _proxy.port = req.port
    _proxy.set_provider(provider)
    cfg.listen_port = req.port
    save_config(cfg)

    _proxy.start()
    _add_log("INFO", f"代理启动成功，监听 http://{_proxy.host}:{_proxy.port}")
    _add_log("INFO", f"当前上游: {provider.name} ({provider.base_url})")
    return {"ok": True}


@app.post("/api/proxy/stop")
async def proxy_stop():
    _proxy.stop()
    _add_log("INFO", "代理已停止")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Logs API
# ---------------------------------------------------------------------------

@app.get("/api/logs")
async def get_logs():
    with _log_lock:
        return {
            "entries": list(_log_buffer),
            "stats": dict(_log_counter),
        }


@app.post("/api/log/clear")
async def clear_logs():
    with _log_lock:
        _log_buffer.clear()
        _log_counter.update({"total": 0, "success": 0, "failed": 0, "today": 0})
    return {"ok": True}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def run_api_server(host: str = "127.0.0.1", port: int = 8318):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_api_server()
