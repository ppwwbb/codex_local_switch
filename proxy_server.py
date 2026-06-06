"""
代理服务器模块
基于 FastAPI，接收 Responses API 请求并翻译后转发到上游 Provider。
"""
import asyncio
import json
import threading
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse

import protocol_adapter
from config import Provider


class ProxyServer:
    """可动态启停的本地代理服务器"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8317):
        self.host = host
        self.port = port
        self.provider: Optional[Provider] = None
        self._app = FastAPI(title="LocalSwitch Proxy")
        self._setup_routes()
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        self._running = False
        self._log_callback = None  # 日志回调函数

    def set_provider(self, provider: Provider) -> None:
        self.provider = provider

    def set_log_callback(self, callback):
        """设置日志回调，接收 (level, message)"""
        self._log_callback = callback

    def _log(self, level: str, message: str) -> None:
        if self._log_callback:
            try:
                self._log_callback(level, message)
            except Exception:
                pass
        else:
            print(f"[{level}] {message}")

    def _setup_routes(self) -> None:
        app = self._app

        @app.get("/health")
        async def health():
            return {"status": "ok", "service": "localswitch"}

        @app.get("/v1/models")
        async def list_models():
            # 返回当前 provider 配置的默认模型
            if self.provider:
                return {
                    "object": "list",
                    "data": [
                        {
                            "id": self.provider.model,
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "localswitch",
                        }
                    ],
                }
            return {"object": "list", "data": []}

        @app.post("/v1/responses")
        async def responses_endpoint(request: Request, authorization: Optional[str] = Header(None)):
            if not self.provider:
                return JSONResponse({"error": "No provider configured"}, status_code=503)

            body = await request.json()
            self._log("INFO", f"Request /v1/responses model={body.get('model')} stream={body.get('stream', False)}")

            # 1. 协议转换：Responses -> Chat Completions
            chat_payload = protocol_adapter.responses_to_chat_completions(body)
            self._log("DEBUG", f"Converted payload: {json.dumps(chat_payload, ensure_ascii=False)[:500]}")

            # 2. 准备上游请求头（伪装为 Claude Code CLI 以通过 Kimi 白名单）
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.provider.api_key}",
                "User-Agent": "claude-code/2.1.0 (cli)",
            }

            target_url = self.provider.base_url.rstrip("/") + "/chat/completions"
            stream_mode = body.get("stream", False)

            if stream_mode:
                return await self._handle_streaming(target_url, headers, chat_payload, body.get("model", ""), body)
            else:
                return await self._handle_non_streaming(target_url, headers, chat_payload)

        @app.post("/v1/chat/completions")
        async def chat_completions_proxy(request: Request):
            """直接透传 Chat Completions 请求（供测试或 fallback 使用）"""
            if not self.provider:
                return JSONResponse({"error": "No provider configured"}, status_code=503)
            body = await request.json()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.provider.api_key}",
                "User-Agent": "claude-code/2.1.0 (cli)",
            }
            target_url = self.provider.base_url.rstrip("/") + "/chat/completions"
            stream_mode = body.get("stream", False)
            if stream_mode:
                return await self._handle_streaming(target_url, headers, body, body.get("model", ""))
            else:
                return await self._handle_non_streaming(target_url, headers, body)

    async def _handle_non_streaming(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> JSONResponse:
        try:
            resp = await self._client.post(url, headers=headers, json=payload)
            self._log("INFO", f"Upstream response status={resp.status_code}")

            if resp.status_code != 200:
                self._log("ERROR", f"Upstream error: {resp.text[:500]}")
                return JSONResponse({"error": "Upstream error", "detail": resp.text}, status_code=resp.status_code)

            chat_resp = resp.json()
            # 3. 协议转换回 Responses 格式
            response_payload = protocol_adapter.chat_completions_to_responses(chat_resp)
            self._log("DEBUG", f"Response payload: {json.dumps(response_payload, ensure_ascii=False)[:500]}")
            return JSONResponse(response_payload)
        except Exception as e:
            self._log("ERROR", f"Proxy error: {str(e)}")
            return JSONResponse({"error": "Proxy internal error", "detail": str(e)}, status_code=500)

    async def _handle_streaming(self, url: str, headers: Dict[str, str], payload: Dict[str, Any],
                                 model: str, original_request: Optional[Dict[str, Any]] = None) -> StreamingResponse:
        async def event_generator():
            state = {}
            try:
                async with self._client.stream("POST", url, headers=headers, json=payload) as resp:
                    self._log("INFO", f"Upstream streaming status={resp.status_code}")
                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        self._log("ERROR", f"Upstream streaming error: {err_text.decode()[:500]}")
                        yield protocol_adapter._sse_event("error", {"error": err_text.decode()}, 0)
                        return

                    async for line in resp.aiter_lines():
                        # 兼容 data:xxx 和 data: xxx（Kimi 部分返回无空格）
                        if not line.startswith("data:"):
                            continue
                        data_str = line[len("data:"):].strip()
                        if data_str == "[DONE]":
                            self._log("DEBUG", "Upstream sent [DONE]")
                            # 兜底：若上游在 [DONE] 前未发 finish_reason，补 emit close
                            if not state.get("done"):
                                seq = state.get("seq", 0)
                                status = "completed"
                                incomplete_details = None
                                finish_reason = state.get("finish_reason")
                                if finish_reason in ("stop", "tool_calls", "function_call"):
                                    status = "completed"
                                    incomplete_details = None
                                elif finish_reason == "length":
                                    status = "incomplete"
                                    incomplete_details = {"reason": "max_output_tokens"}
                                elif finish_reason == "content_filter":
                                    status = "incomplete"
                                    incomplete_details = {"reason": "content_filter"}
                                elif finish_reason:
                                    status = "incomplete"
                                    incomplete_details = {"reason": finish_reason}
                                else:
                                    status = "incomplete"
                                    incomplete_details = {"reason": "interrupted"}

                                envelope = protocol_adapter._build_envelope(
                                    state.get("response_id", ""),
                                    state.get("created_at", int(time.time())),
                                    state.get("model", model),
                                    status,
                                    original_request,
                                )
                                output = []
                                if state.get("buffer"):
                                    output.append({
                                        "type": "message",
                                        "status": "completed",
                                        "role": state.get("role", "assistant"),
                                        "id": state.get("msg_id", ""),
                                        "content": [{"type": "output_text", "text": state["buffer"], "annotations": []}],
                                    })
                                envelope["output"] = output
                                envelope["incomplete_details"] = incomplete_details
                                envelope["error"] = None
                                envelope["usage"] = protocol_adapter._normalize_usage_to_responses(state.get("usage"))

                                yield protocol_adapter._sse_event("response.completed", {
                                    "type": "response.completed",
                                    "response": envelope,
                                }, seq)
                                yield protocol_adapter._sse_event("done", {"type": "done"}, seq + 1)
                            break

                        if not data_str:
                            continue
                        self._log("DEBUG", f"Upstream SSE data: {data_str[:300]}")
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        events = protocol_adapter.translate_chat_stream_chunk(chunk, state, original_request)
                        self._log("DEBUG", f"Translated {len(events)} events, seq={state.get('seq', 0)}")
                        for ev in events:
                            yield ev
            except Exception as e:
                self._log("ERROR", f"Streaming error: {str(e)}")
                yield protocol_adapter._sse_event("error", {"error": str(e)}, 0)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    def start(self) -> None:
        if self._running:
            return
        self._running = True

        def run_server():
            import uvicorn
            config = uvicorn.Config(self._app, host=self.host, port=self.port, log_level="warning", access_log=False)
            self._server = uvicorn.Server(config)
            self._log("INFO", f"Proxy server starting at http://{self.host}:{self.port}")
            try:
                self._server.run()
            except Exception as e:
                self._log("ERROR", f"Server error: {e}")
            finally:
                self._running = False

        self._thread = threading.Thread(target=run_server, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._running or not self._server:
            return
        self._log("INFO", "Proxy server stopping...")
        self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._running = False
        self._log("INFO", "Proxy server stopped")

    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()
