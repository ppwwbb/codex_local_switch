"""
配置管理模块
使用 dataclasses + JSON 实现持久化，兼容 Python 3.7
"""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Provider:
    """上游 Provider 配置"""
    id: str
    name: str = "Kimi Code"
    api_key: str = ""
    base_url: str = "https://api.kimi.com/coding/v1"
    model: str = "kimi-k2-0711-preview"
    enabled: bool = True


@dataclass
class AppConfig:
    """应用全局配置"""
    listen_host: str = "127.0.0.1"
    listen_port: int = 8317
    providers: List[Provider] = field(default_factory=list)
    current_provider_id: Optional[str] = None
    log_level: str = "INFO"

    def get_current_provider(self) -> Optional[Provider]:
        """获取当前选中的 Provider"""
        if not self.current_provider_id:
            return None
        for p in self.providers:
            if p.id == self.current_provider_id:
                return p
        return None

    def add_provider(self, provider: Provider) -> None:
        """添加 Provider，若已存在则更新"""
        for i, p in enumerate(self.providers):
            if p.id == provider.id:
                self.providers[i] = provider
                return
        self.providers.append(provider)
        if self.current_provider_id is None:
            self.current_provider_id = provider.id

    def remove_provider(self, provider_id: str) -> None:
        """删除 Provider"""
        self.providers = [p for p in self.providers if p.id != provider_id]
        if self.current_provider_id == provider_id:
            self.current_provider_id = self.providers[0].id if self.providers else None


CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".localswitch", "config.json")


def _provider_to_dict(p: Provider) -> dict:
    return asdict(p)


def _provider_from_dict(data: dict) -> Provider:
    return Provider(**data)


def save_config(config: AppConfig) -> None:
    """保存配置到 JSON 文件"""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    data = {
        "listen_host": config.listen_host,
        "listen_port": config.listen_port,
        "current_provider_id": config.current_provider_id,
        "log_level": config.log_level,
        "providers": [_provider_to_dict(p) for p in config.providers],
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_config() -> AppConfig:
    """从 JSON 文件加载配置，若不存在则返回默认配置"""
    if not os.path.exists(CONFIG_PATH):
        default = AppConfig()
        default.add_provider(Provider(id="default"))
        save_config(default)
        return default

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    providers = [_provider_from_dict(p) for p in data.get("providers", [])]
    config = AppConfig(
        listen_host=data.get("listen_host", "127.0.0.1"),
        listen_port=data.get("listen_port", 8317),
        current_provider_id=data.get("current_provider_id"),
        log_level=data.get("log_level", "INFO"),
        providers=providers,
    )
    if not config.providers:
        config.add_provider(Provider(id="default"))
    if config.current_provider_id is None and config.providers:
        config.current_provider_id = config.providers[0].id
    return config
