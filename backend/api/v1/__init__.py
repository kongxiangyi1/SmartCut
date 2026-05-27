"""
API v1 package for FastAPI routes.
统一管理所有API路由
"""

from fastapi import APIRouter

# 创建主路由器
api_router = APIRouter()

# 导入所有路由模块
from .health import router as health_router
from .projects import router as projects_router
from .clips import router as clips_router
from .collections import router as collections_router
from .settings import router as settings_router
from .pipeline_switch import router as pipeline_switch_router
from .video_categories import router as video_categories_router

# 注册所有路由
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(clips_router, prefix="/clips", tags=["clips"])
api_router.include_router(collections_router, prefix="/collections", tags=["collections"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_router.include_router(pipeline_switch_router, tags=["pipeline"])
api_router.include_router(video_categories_router, prefix="/video-categories", tags=["video-categories"])

__all__ = ["api_router"]
