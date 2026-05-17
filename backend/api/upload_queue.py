"""
上传队列路由
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def get_upload_queue_status():
    """获取上传队列状态"""
    return {
        "queue_size": 0,
        "active_uploads": 0,
        "status": "idle"
    }
