"""
账户健康检查路由
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/check")
async def check_account_health():
    """检查账户健康状态"""
    return {
        "status": "healthy",
        "account_status": "active",
        "limits": {
            "max_projects": 100,
            "used_projects": 0
        }
    }
