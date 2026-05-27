"""
视频分类 API
提供视频分类列表接口
"""

import logging
from typing import Dict, List
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["video-categories"])
logger = logging.getLogger(__name__)


@router.get("")
def get_video_categories():
    """
    获取所有视频分类信息
    用于前端显示分类选择列表
    """
    from backend.core.shared_config import VideoCategory, VIDEO_CATEGORIES_CONFIG
    try:
        categories = []
        for cat_enum in VideoCategory:
            cat_config = VIDEO_CATEGORIES_CONFIG.get(cat_enum, {})
            categories.append({
                "value": cat_enum.value,
                "name": cat_config.get("name", cat_enum.value),
                "description": cat_config.get("description", ""),
                "icon": cat_config.get("icon", ""),
                "color": cat_config.get("color", "#4facfe")
            })
        
        return {
            "categories": categories,
            "default_category": VideoCategory.DEFAULT.value
        }
    except Exception as e:
        logger.error(f"获取视频分类失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
