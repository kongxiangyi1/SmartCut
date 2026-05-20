"""
流水线切换API
支持在原6步流水线和FunClip风格流水线之间切换
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class PipelineSwitchRequest(BaseModel):
    """流水线切换请求"""
    mode: str = "legacy"  # "legacy", "funclip", 或 "ab_test"
    ab_test_ratio: Optional[float] = 0.1


class PipelineSwitchResponse(BaseModel):
    """流水线切换响应"""
    current_mode: str
    message: str
    available_modes: list


@router.post("/pipeline/switch", response_model=PipelineSwitchResponse)
async def switch_pipeline_mode(request: PipelineSwitchRequest):
    """
    切换流水线模式

    - legacy: 使用原6步流水线（推荐用于2小时直播）
    - funclip: 使用FunClip风格的单步LLM流水线（快速）
    - ab_test: A/B测试模式
    """
    from backend.pipeline.pipeline_selector import pipeline_selector
    
    valid_modes = ["legacy", "funclip", "ab_test"]
    
    if request.mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"无效的模式: {request.mode}，可用模式: {valid_modes}"
        )
    
    # 更新选择器模式（使用持久化的set_mode方法）
    old_mode = pipeline_selector.mode
    pipeline_selector.set_mode(request.mode, request.ab_test_ratio)
    
    mode_descriptions = {
        "legacy": "原6步流水线（推荐用于2小时直播）",
        "funclip": "FunClip风格单步LLM流水线（快速，适合短视频）",
        "ab_test": "A/B测试模式"
    }
    
    return PipelineSwitchResponse(
        current_mode=pipeline_selector.mode,
        message=f"已从 {old_mode} ({mode_descriptions.get(old_mode, '')}) 切换到 {request.mode} ({mode_descriptions.get(request.mode, '')})。配置已保存，服务重启后仍有效。",
        available_modes=valid_modes
    )


@router.get("/pipeline/status")
async def get_pipeline_status():
    """
    获取当前流水线状态
    """
    from backend.pipeline.pipeline_selector import pipeline_selector
    
    mode_descriptions = {
        "legacy": "原6步流水线（推荐用于2小时直播）",
        "funclip": "FunClip风格单步LLM流水线（快速，适合短视频）",
        "ab_test": "A/B测试模式"
    }
    
    return {
        "current_mode": pipeline_selector.mode,
        "description": mode_descriptions.get(pipeline_selector.mode, ""),
        "ab_test_ratio": pipeline_selector.ab_test_ratio,
        "available_modes": ["legacy", "funclip", "ab_test"]
    }


@router.post("/pipeline/validate")
async def validate_pipeline():
    """
    验证流水线配置
    """
    try:
        from backend.pipeline.pipeline_selector import pipeline_selector
        
        # 测试流水线选择器
        test_project_id = "test_project"
        selected_mode = pipeline_selector.select_pipeline(test_project_id)
        
        return {
            "status": "success",
            "selected_mode": selected_mode,
            "available_modes": ["legacy", "funclip", "ab_test"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"验证失败: {str(e)}"
        )

