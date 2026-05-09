"""
依赖注入配置
提供FastAPI的依赖注入服务
"""

from typing import Generator
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services.project_service import ProjectService
from backend.services.clip_service import ClipService
from backend.services.collection_service import CollectionService
from backend.services.task_service import TaskService


def get_project_service(db: Session) -> ProjectService:
    """Get project service with database dependency."""
    return ProjectService(db)


def get_clip_service(db: Session) -> ClipService:
    """Get clip service with database dependency."""
    return ClipService(db)


def get_collection_service(db: Session) -> CollectionService:
    """Get collection service with database dependency."""
    return CollectionService(db)


def get_task_service(db: Session) -> TaskService:
    """Get task service with database dependency."""
    return TaskService(db) 