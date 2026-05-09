"""
字幕处理 API
"""

import logging
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from backend.core.path_utils import get_project_directory

logger = logging.getLogger(__name__)
router = APIRouter()


class SubtitleBurnRequest(BaseModel):
    """字幕烧录请求"""
    project_id: str
    clip_ids: list[str] = Field(..., description="需要烧录字幕的切片ID列表")
    burn_subtitle: bool = Field(True, description="是否烧录字幕到视频")


class SubtitleStyleRequest(BaseModel):
    """字幕样式配置"""
    font_name: str = Field("微软雅黑", description="字体名称")
    font_size: int = Field(24, description="字体大小")
    primary_color: str = Field("ffffff", description="主颜色(RRGGBB)")
    outline_color: str = Field("000000", description="描边颜色(RRGGBB)")
    outline_width: int = Field(2, description="描边宽度")
    bold: bool = Field(False, description="是否加粗")
    margin_v: int = Field(60, description="垂直边距")


@router.post("/burn_subtitle")
async def burn_subtitle_to_clips(request: SubtitleBurnRequest):
    """
    批量烧录字幕到切片

    Args:
        request: 烧录请求

    Returns:
        操作结果
    """
    try:
        project_id = request.project_id
        clip_ids = request.clip_ids

        project_dir = get_project_directory(project_id)
        clips_dir = project_dir / "output" / "clips"
        metadata_dir = project_dir / "metadata"

        if not clips_dir.exists():
            raise HTTPException(status_code=404, detail="切片目录不存在")

        results = []
        success_count = 0
        failed_count = 0

        for clip_id in clip_ids:
            # 找到对应的视频和字幕文件
            clip_files = list(clips_dir.glob(f"{clip_id}_*.mp4"))
            if not clip_files:
                logger.warning(f"未找到切片 {clip_id} 的视频文件")
                failed_count += 1
                results.append({"clip_id": clip_id, "status": "failed", "reason": "视频文件不存在"})
                continue

            video_path = clip_files[0]
            srt_path = video_path.with_suffix('.srt')

            if not srt_path.exists():
                logger.warning(f"切片 {clip_id} 字幕文件不存在: {srt_path}")
                failed_count += 1
                results.append({"clip_id": clip_id, "status": "failed", "reason": "字幕文件不存在"})
                continue

            # 烧录字幕
            output_path = clips_dir / f"{clip_id}_with_subtitle.mp4"

            try:
                from backend.utils.subtitle_processor import SubtitleProcessor, SubtitleStyle

                # 使用默认样式
                style = SubtitleStyle()

                success = SubtitleProcessor.burn_subtitle_to_video(
                    video_path,
                    srt_path,
                    output_path,
                    style
                )

                if success:
                    success_count += 1
                    results.append({"clip_id": clip_id, "status": "success", "output": str(output_path.name)})
                    logger.info(f"切片 {clip_id} 字幕烧录成功: {output_path}")
                else:
                    failed_count += 1
                    results.append({"clip_id": clip_id, "status": "failed", "reason": "烧录失败"})

            except Exception as e:
                logger.error(f"切片 {clip_id} 字幕烧录异常: {e}")
                failed_count += 1
                results.append({"clip_id": clip_id, "status": "failed", "reason": str(e)})

        return {
            "success": True,
            "message": f"字幕烧录完成: {success_count} 成功, {failed_count} 失败",
            "results": results,
            "success_count": success_count,
            "failed_count": failed_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"字幕烧录API异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available_fonts")
async def get_available_fonts():
    """
    获取可用字体列表

    Returns:
        字体列表
    """
    # Windows 常见字体
    common_fonts = [
        {"name": "微软雅黑", "display": "微软雅黑", "default": True},
        {"name": "SimHei", "display": "黑体"},
        {"name": "SimSun", "display": "宋体"},
        {"name": "KaiTi", "display": "楷体"},
        {"name": "Microsoft YaHei", "display": "Microsoft YaHei"},
        {"name": "Arial", "display": "Arial"},
        {"name": "Georgia", "display": "Georgia"},
        {"name": "Times New Roman", "display": "Times New Roman"},
        {"name": "Verdana", "display": "Verdana"}
    ]

    # TODO: 实际检测系统可用字体
    return {
        "success": True,
        "fonts": common_fonts
    }
