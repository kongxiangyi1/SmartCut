"""
素材导出 API
支持批量导出切片视频和字幕文件
"""

import logging
import zipfile
import io
import subprocess
import platform
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from backend.core.path_utils import get_project_directory

logger = logging.getLogger(__name__)
router = APIRouter()


class ExportRequest(BaseModel):
    """导出请求"""
    project_id: str
    clip_ids: List[str] = Field(..., description="需要导出的切片ID列表")
    include_subtitles: bool = Field(True, description="是否包含字幕文件")
    include_video: bool = Field(True, description="是否包含视频文件")


@router.post("/export_materials")
async def export_materials(request: ExportRequest):
    """
    批量导出素材包（视频+字幕）

    返回ZIP文件，包含选定的切片视频和字幕文件

    Args:
        request: 导出请求

    Returns:
        ZIP文件流
    """
    try:
        project_id = request.project_id
        clip_ids = request.clip_ids
        include_subtitles = request.include_subtitles
        include_video = request.include_video

        if not clip_ids:
            raise HTTPException(status_code=400, detail="请选择要导出的切片")

        project_dir = get_project_directory(project_id)
        clips_dir = project_dir / "output" / "clips"

        if not clips_dir.exists():
            raise HTTPException(status_code=404, detail="切片目录不存在")

        files_to_export: List[tuple] = []

        for clip_id in clip_ids:
            if include_video:
                video_files = list(clips_dir.glob(f"{clip_id}_*.mp4"))
                for vf in video_files:
                    rel_path = Path("videos") / vf.name
                    files_to_export.append((rel_path, vf))

            if include_subtitles:
                subtitle_files = list(clips_dir.glob(f"{clip_id}_*.srt"))
                for sf in subtitle_files:
                    rel_path = Path("subtitles") / sf.name
                    files_to_export.append((rel_path, sf))

        if not files_to_export:
            raise HTTPException(status_code=404, detail="未找到要导出的文件")

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for rel_path, abs_path in files_to_export:
                if abs_path.exists():
                    zip_file.write(abs_path, rel_path)
                    logger.info(f"添加到ZIP: {rel_path}")

        zip_buffer.seek(0)

        safe_project_id = project_id[:8] if len(project_id) > 8 else project_id
        zip_filename = f"autoclip_export_{safe_project_id}.zip"

        logger.info(f"素材包导出成功: {zip_filename}, 包含 {len(files_to_export)} 个文件")

        return StreamingResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{zip_filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"素材导出异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list_clips")
async def list_project_clips(
    project_id: str = Query(..., description="项目ID")
):
    """
    获取项目的切片列表及文件信息

    Args:
        project_id: 项目ID

    Returns:
        切片列表，包含视频和字幕文件信息
    """
    try:
        project_dir = get_project_directory(project_id)
        clips_dir = project_dir / "output" / "clips"

        if not clips_dir.exists():
            return {
                "success": True,
                "clips": [],
                "total": 0
            }

        clips = []
        for clip_file in sorted(clips_dir.glob("*.mp4")):
            clip_id = clip_file.stem.split("_")[0] if "_" in clip_file.stem else clip_file.stem
            title = "_".join(clip_file.stem.split("_")[1:]) if "_" in clip_file.stem else clip_file.stem

            subtitle_file = clip_file.with_suffix('.srt')
            has_subtitle = subtitle_file.exists()

            video_size = clip_file.stat().st_size if clip_file.exists() else 0
            subtitle_size = subtitle_file.stat().st_size if subtitle_file.exists() else 0

            clips.append({
                "clip_id": clip_id,
                "title": title,
                "video_file": clip_file.name,
                "subtitle_file": subtitle_file.name if has_subtitle else None,
                "has_subtitle": has_subtitle,
                "video_size": video_size,
                "subtitle_size": subtitle_size,
                "video_path": str(clip_file.relative_to(project_dir)) if clip_file.exists() else None,
                "subtitle_path": str(subtitle_file.relative_to(project_dir)) if subtitle_file.exists() else None
            })

        return {
            "success": True,
            "clips": clips,
            "total": len(clips)
        }

    except Exception as e:
        logger.error(f"获取切片列表异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download_single")
async def download_single_file(
    project_id: str = Query(..., description="项目ID"),
    clip_id: str = Query(..., description="切片ID"),
    file_type: str = Query("video", description="文件类型: video/subtitle")
):
    """
    下载单个切片文件（视频或字幕）

    Args:
        project_id: 项目ID
        clip_id: 切片ID
        file_type: 文件类型 (video/subtitle)

    Returns:
        文件流
    """
    try:
        project_dir = get_project_directory(project_id)
        clips_dir = project_dir / "output" / "clips"

        if not clips_dir.exists():
            raise HTTPException(status_code=404, detail="切片目录不存在")

        if file_type == "video":
            files = list(clips_dir.glob(f"{clip_id}_*.mp4"))
            media_type = "video/mp4"
        else:
            files = list(clips_dir.glob(f"{clip_id}_*.srt"))
            media_type = "application/octet-stream"

        if not files:
            raise HTTPException(status_code=404, detail=f"未找到{file_type}文件")

        file_path = files[0]

        with open(file_path, 'rb') as f:
            file_content = f.read()

        filename = file_path.name

        return StreamingResponse(
            iter([file_content]),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件下载异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/open_folder")
async def open_clips_folder(
    project_id: str = Query(..., description="项目ID")
):
    """
    在文件资源管理器中打开项目的切片目录

    Args:
        project_id: 项目ID

    Returns:
        操作结果
    """
    try:
        project_dir = get_project_directory(project_id)
        clips_dir = project_dir / "output" / "clips"

        if not clips_dir.exists():
            clips_dir.mkdir(parents=True, exist_ok=True)

        # 根据操作系统打开文件夹
        folder_path = str(clips_dir.absolute())

        if platform.system() == 'Windows':
            subprocess.run(['explorer', folder_path], check=True)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', folder_path], check=True)
        else:  # Linux
            subprocess.run(['xdg-open', folder_path], check=True)

        logger.info(f"打开文件夹: {folder_path}")

        return {
            "success": True,
            "message": "已在文件资源管理器中打开文件夹",
            "path": folder_path
        }

    except Exception as e:
        logger.error(f"打开文件夹异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))
