"""
简化进度路由
"""

from fastapi import APIRouter, Query
from backend.services.simple_progress import get_multiple_progress_snapshots, get_progress_snapshot

router = APIRouter()


@router.get("/snapshot")
async def get_progress_snapshots(project_ids: list = Query(None)):
    """获取多个项目的进度快照"""
    if project_ids:
        snapshots = get_multiple_progress_snapshots(project_ids)
    else:
        snapshots = []
    
    return snapshots


@router.get("/snapshot/{project_id}")
async def get_single_progress_snapshot(project_id: str):
    """获取单个项目的进度快照"""
    snapshot = get_progress_snapshot(project_id)
    if snapshot:
        return snapshot
    return {"error": "项目未找到"}, 404
