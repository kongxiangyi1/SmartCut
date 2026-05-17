"""
任务模型
"""
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Text
from backend.core.database import Base
from datetime import datetime
import enum
import uuid


class TaskType(str, enum.Enum):
    """任务类型枚举"""
    VIDEO_PROCESSING = "video_processing"
    IMPORT = "import"
    EXPORT = "export"
    DOWNLOAD = "download"
    ANALYSIS = "analysis"


class TaskStatus(str, enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(Base):
    """任务模型"""
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    progress = Column(String, default="0")  # 存储为JSON字符串
    celery_task_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "task_type": self.task_type.value,
            "status": self.status.value,
            "progress": self.progress,
            "celery_task_id": self.celery_task_id,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
