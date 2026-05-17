"""
任务相关的Pydantic模式
"""
from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    """任务类型枚举"""
    VIDEO_PROCESSING = "video_processing"
    IMPORT = "import"
    EXPORT = "export"
    DOWNLOAD = "download"
    ANALYSIS = "analysis"


class TaskBase(BaseModel):
    """任务基础模式"""
    project_id: str
    task_type: TaskType


class TaskCreate(TaskBase):
    """创建任务模式"""
    pass


class TaskUpdate(BaseModel):
    """更新任务模式"""
    status: Optional[TaskStatus] = None
    progress: Optional[str] = None
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None


class TaskResponse(BaseModel):
    """任务响应模式"""
    id: str
    project_id: str
    task_type: TaskType
    status: TaskStatus
    progress: str
    celery_task_id: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
