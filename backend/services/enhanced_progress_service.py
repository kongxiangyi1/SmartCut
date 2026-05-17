"""
增强的进度服务 - 管理项目处理进度
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)


class ProgressCache:
    """进度缓存类"""
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.lock = Lock()
    
    def get(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目进度"""
        with self.lock:
            return self.cache.get(project_id)
    
    def set(self, project_id: str, progress: Dict[str, Any]):
        """设置项目进度"""
        with self.lock:
            self.cache[project_id] = progress
    
    def delete(self, project_id: str):
        """删除项目进度"""
        with self.lock:
            if project_id in self.cache:
                del self.cache[project_id]
    
    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """获取所有进度"""
        with self.lock:
            return self.cache.copy()


class EnhancedProgressService:
    """增强的进度服务"""
    
    def __init__(self):
        self.progress_cache = ProgressCache()
        self.logger = logging.getLogger(__name__)
    
    def update_progress(self, project_id: str, stage: str, message: str, 
                       subpercent: float = None, metadata: Dict = None):
        """
        更新项目处理进度
        
        Args:
            project_id: 项目ID
            stage: 当前阶段
            message: 进度消息
            subpercent: 子进度百分比（0-100）
            metadata: 额外的元数据
        """
        progress = {
            "project_id": project_id,
            "stage": stage,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "subpercent": subpercent,
            "metadata": metadata or {}
        }
        
        self.progress_cache.set(project_id, progress)
        self.logger.info(f"进度更新 - {project_id}: {stage} - {message}")
    
    def get_progress(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目进度"""
        return self.progress_cache.get(project_id)
    
    def clear_progress(self, project_id: str):
        """清除项目进度"""
        self.progress_cache.delete(project_id)
        self.logger.info(f"进度已清除 - {project_id}")
    
    def get_all_progress(self) -> Dict[str, Dict[str, Any]]:
        """获取所有项目进度"""
        return self.progress_cache.get_all()


# 全局实例
progress_service = EnhancedProgressService()
