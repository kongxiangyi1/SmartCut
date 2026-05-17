"""
任务相关路由
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    return {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "任务状态查询"
    }


@router.delete("/{task_id}")
async def revoke_task(task_id: str):
    """撤销任务"""
    return {
        "success": True,
        "task_id": task_id,
        "message": "任务已撤销"
    }
