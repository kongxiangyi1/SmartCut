"""
环境检测器
用于检测当前运行环境的配置
"""

import os
from typing import Optional


class EnvironmentDetector:
    """环境检测器类"""
    
    @staticmethod
    def is_production() -> bool:
        """检查是否为生产环境"""
        return os.getenv("ENVIRONMENT", "development").lower() == "production"
    
    @staticmethod
    def is_development() -> bool:
        """检查是否为开发环境"""
        return os.getenv("ENVIRONMENT", "development").lower() == "development"
    
    @staticmethod
    def get_env_variable(name: str, default: Optional[str] = None) -> Optional[str]:
        """获取环境变量"""
        return os.getenv(name, default)
    
    @staticmethod
    def get_api_key(service: str) -> Optional[str]:
        """获取API密钥"""
        return os.getenv(f"{service.upper()}_API_KEY")
    
    @staticmethod
    def has_gpu() -> bool:
        """检查是否有GPU可用"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
