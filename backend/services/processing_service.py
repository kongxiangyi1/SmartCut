"""
处理服务
提供视频处理相关的业务逻辑操作
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import logging

from backend.services.base import BaseService
from backend.services.simple_pipeline_adapter import SimplePipelineAdapter

logger = logging.getLogger(__name__)


class ProcessingService:
    """处理服务类，提供视频处理相关的业务逻辑"""

    def __init__(self, db: Session):
        self.db = db

    def create_pipeline_adapter(self, project_id: str, task_id: str) -> SimplePipelineAdapter:
        """创建流水线适配器"""
        return SimplePipelineAdapter(project_id, task_id)

    async def process_project(self, project_id: str, task_id: str, input_video_path: str, 
                              input_srt_path: Optional[str] = None) -> Dict[str, Any]:
        """处理项目"""
        adapter = self.create_pipeline_adapter(project_id, task_id)
        return await adapter.process_project_sync(input_video_path, input_srt_path)
