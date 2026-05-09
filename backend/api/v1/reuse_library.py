"""
复用库API路由
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from pathlib import Path
import logging
import platform
import subprocess
import re

from backend.utils.reuse_library import ReuseLibrary

logger = logging.getLogger(__name__)

router = APIRouter()

reuse_library = ReuseLibrary()


class ReuseClipInfo(BaseModel):
    id: str
    path: str
    duration: float
    product_name: Optional[str] = None
    category: Optional[str] = None
    reuse_value: float
    tags: List[str] = []
    source_clip_id: Optional[str] = None
    source_video: Optional[str] = None
    source_start: Optional[float] = None
    source_end: Optional[float] = None
    added_at: Optional[str] = None


class ReuseLibraryStats(BaseModel):
    total_clips: int
    by_product: dict
    by_category: dict
    by_tag: dict
    by_reuse_value: dict
    last_updated: Optional[str] = None


class AddClipRequest(BaseModel):
    clip_path: str
    duration: float
    product_name: Optional[str] = None
    category: Optional[str] = None
    reuse_value: float = 0.0
    tags: List[str] = []
    source_clip_id: Optional[str] = None
    source_video: Optional[str] = None
    source_start: Optional[float] = None
    source_end: Optional[float] = None


@router.get("/stats", response_model=ReuseLibraryStats)
async def get_statistics():
    """获取复用库统计信息"""
    try:
        stats = reuse_library.get_statistics()
        return ReuseLibraryStats(
            total_clips=len(stats.get("clips", [])),
            by_product=stats.get("by_product", {}),
            by_category=stats.get("by_category", {}),
            by_tag=stats.get("by_tag", {}),
            by_reuse_value=stats.get("by_reuse_value", {}),
            last_updated=stats.get("last_updated")
        )
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clips", response_model=List[ReuseClipInfo])
async def get_all_clips():
    """获取所有复用片段"""
    try:
        clips = reuse_library.get_all_clips()
        return [ReuseClipInfo(**clip) for clip in clips]
    except Exception as e:
        logger.error(f"获取片段列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clips/high-value", response_model=List[ReuseClipInfo])
async def get_high_reuse_clips(min_value: float = Query(0.7, ge=0.0, le=1.0)):
    """获取高复用价值片段"""
    try:
        clips = reuse_library.get_high_reuse_clips(min_value)
        return [ReuseClipInfo(**clip) for clip in clips]
    except Exception as e:
        logger.error(f"获取高价值片段失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clips/search/product/{product_name}", response_model=List[ReuseClipInfo])
async def search_by_product(product_name: str):
    """按产品名搜索片段"""
    try:
        clips = reuse_library.search_by_product(product_name)
        return [ReuseClipInfo(**clip) for clip in clips]
    except Exception as e:
        logger.error(f"按产品搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clips/search/category/{category}", response_model=List[ReuseClipInfo])
async def search_by_category(category: str):
    """按类别搜索片段"""
    try:
        clips = reuse_library.search_by_category(category)
        return [ReuseClipInfo(**clip) for clip in clips]
    except Exception as e:
        logger.error(f"按类别搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clips/search/tag/{tag}", response_model=List[ReuseClipInfo])
async def search_by_tag(tag: str):
    """按标签搜索片段"""
    try:
        clips = reuse_library.search_by_tag(tag)
        return [ReuseClipInfo(**clip) for clip in clips]
    except Exception as e:
        logger.error(f"按标签搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clips/{clip_id}", response_model=ReuseClipInfo)
async def get_clip(clip_id: str):
    """获取单个片段信息"""
    try:
        clip = reuse_library.get_clip_by_id(clip_id)
        if not clip:
            raise HTTPException(status_code=404, detail="片段不存在")
        return ReuseClipInfo(**clip)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取片段失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clips", response_model=dict)
async def add_clip(request: AddClipRequest):
    """添加片段到复用库"""
    try:
        clip_path = Path(request.clip_path)
        if not clip_path.exists():
            raise HTTPException(status_code=400, detail="片段文件不存在")

        metadata = {
            "duration": request.duration,
            "product_name": request.product_name,
            "category": request.category,
            "reuse_value": request.reuse_value,
            "tags": request.tags,
            "source_clip_id": request.source_clip_id,
            "source_video": request.source_video,
            "source_start": request.source_start,
            "source_end": request.source_end
        }

        clip_id = reuse_library.add_clip(clip_path, metadata)
        return {"id": clip_id, "message": "添加成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加片段失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clips/{clip_id}")
async def delete_clip(clip_id: str):
    """删除片段"""
    try:
        success = reuse_library.delete_clip(clip_id)
        if not success:
            raise HTTPException(status_code=404, detail="片段不存在")
        return {"message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除片段失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clips/{clip_id}/video")
async def get_clip_video(clip_id: str, request: Request):
    """
    获取复用片段视频流
    """
    try:
        clip_path = reuse_library.get_clip_full_path(clip_id)
        if not clip_path or not clip_path.exists():
            raise HTTPException(status_code=404, detail="视频文件不存在")

        file_size = clip_path.stat().st_size

        range_header = request.headers.get("range")

        if range_header:
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

                def file_iterator(start: int = start, end: int = end):
                    with open(clip_path, 'rb') as f:
                        f.seek(start)
                        remaining = end - start + 1
                        while remaining > 0:
                            chunk_size = min(1024 * 1024, remaining)
                            data = f.read(chunk_size)
                            if not data:
                                break
                            remaining -= len(data)
                            yield data

                return StreamingResponse(
                    file_iterator(),
                    status_code=206,
                    media_type="video/mp4",
                    headers={
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Accept-Ranges": "bytes",
                        "Content-Length": str(end - start + 1)
                    }
                )

        return FileResponse(
            clip_path,
            media_type="video/mp4",
            filename=f"{clip_id}.mp4"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/open-folder")
async def open_library_folder():
    """
    在系统文件管理器中打开复用库目录
    """
    try:
        library_path = reuse_library.library_dir

        if not library_path.exists():
            raise HTTPException(status_code=404, detail="复用库目录不存在")

        system = platform.system()

        if system == "Windows":
            subprocess.Popen(f'explorer "{library_path}"')
        elif system == "Darwin":
            subprocess.Popen(["open", str(library_path)])
        else:
            subprocess.Popen(["xdg-open", str(library_path)])

        return {"message": "已在文件管理器中打开", "path": str(library_path)}

    except Exception as e:
        logger.error(f"打开文件夹失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ChartData(BaseModel):
    reuse_value_distribution: List[dict]
    product_distribution: List[dict]
    category_distribution: List[dict]
    total_clips: int
    total_products: int
    total_categories: int


@router.get("/stats/charts", response_model=ChartData)
async def get_chart_data():
    """获取图表数据"""
    try:
        stats = reuse_library.get_statistics()
        all_clips = reuse_library.get_all_clips()

        by_reuse_value = stats.get("by_reuse_value", {})
        reuse_value_data = []
        for range_key, clip_ids in by_reuse_value.items():
            reuse_value_data.append({
                "range": range_key,
                "count": len(clip_ids),
                "percentage": round(len(clip_ids) / max(len(all_clips), 1) * 100, 1)
            })

        by_product = stats.get("by_product", {})
        product_data = sorted([
            {"product": name, "count": len(ids)}
            for name, ids in by_product.items()
        ], key=lambda x: x["count"], reverse=True)[:10]

        by_category = stats.get("by_category", {})
        category_data = [
            {"category": name, "count": len(ids)}
            for name, ids in by_category.items()
        ]

        return ChartData(
            reuse_value_distribution=reuse_value_data,
            product_distribution=product_data,
            category_distribution=category_data,
            total_clips=len(all_clips),
            total_products=len(by_product),
            total_categories=len(by_category)
        )
    except Exception as e:
        logger.error(f"获取图表数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))