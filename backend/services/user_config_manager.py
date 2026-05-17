"""
用户配置管理器
负责保存和加载用户的个性化配置
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)


class ConfigManager:
    """用户配置管理器 - 线程安全"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._config_file = self._get_config_file_path()
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _get_config_file_path(self) -> Path:
        """获取配置文件路径"""
        # 使用项目根目录
        project_root = Path(__file__).parent.parent.parent
        config_dir = project_root / "data"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "user_config.json"
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if self._config_file.exists():
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info(f"[OK] 用户配置已加载: {len(self._config)} 个配置项")
            else:
                logger.info("[NOTE] 未找到用户配置文件，将使用默认配置")
                self._config = {}
        except Exception as e:
            logger.error(f"[FAIL] 加载用户配置失败: {e}")
            self._config = {}
    
    def _save_config(self):
        """保存配置文件"""
        try:
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            logger.info(f"[OK] 用户配置已保存: {len(self._config)} 个配置项")
            return True
        except Exception as e:
            logger.error(f"[FAIL] 保存用户配置失败: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """设置配置项"""
        self._config[key] = value
        return self._save_config()
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config.copy()
    
    def update(self, config: Dict[str, Any]) -> bool:
        """批量更新配置"""
        self._config.update(config)
        return self._save_config()
    
    def clear(self) -> bool:
        """清除所有配置"""
        self._config = {}
        return self._save_config()


# 全局配置管理器实例
config_manager = ConfigManager()
