"""
缩略图生成器 - 从视频中提取缩略图
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def generate_project_thumbnail(
    video_path: str,
    output_path: str,
    project_id: str = None,
    time_offset: float = 5.0,
    width: int = 640,
    height: int = 360
) -> bool:
    """
    从视频中提取缩略图

    Args:
        video_path: 视频文件路径或视频对象
        output_path: 缩略图输出路径
        project_id: 项目ID（可选，用于日志记录）
        time_offset: 从哪个时间点提取（秒）
        width: 缩略图宽度
        height: 缩略图高度

    Returns:
        是否成功生成缩略图
    """
    try:
        # 处理视频路径 - 如果是 Path 对象或包含 project_id 的路径
        if isinstance(video_path, Path):
            video_path_obj = video_path
        else:
            # 如果 video_path 是项目ID，构建正确的视频路径
            if project_id and str(video_path) == str(project_id):
                from backend.core.path_utils import get_project_raw_dir
                raw_dir = get_project_raw_dir(project_id)
                # 查找 raw 目录中的视频文件
                video_files = list(raw_dir.glob("*.mp4")) + list(raw_dir.glob("*.mkv")) + list(raw_dir.glob("*.avi"))
                if video_files:
                    video_path_obj = video_files[0]
                else:
                    logger.error(f"在项目目录中未找到视频文件: {raw_dir}")
                    return False
            else:
                video_path_obj = Path(str(video_path))
        
        if not video_path_obj.exists():
            logger.error(f"视频文件不存在: {video_path_obj}")
            return False

        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', str(time_offset),
            '-vframes', '1',
            '-vf', f'scale={width}:{height}',
            '-y',
            str(output_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0 and output_path_obj.exists():
            logger.info(f"成功生成缩略图: {output_path}")
            return True
        else:
            logger.error(f"生成缩略图失败: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("生成缩略图超时")
        return False
    except Exception as e:
        logger.error(f"生成缩略图异常: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False


def generate_multiple_thumbnails(
    video_path: str,
    output_dir: str,
    count: int = 5,
    interval: Optional[float] = None
) -> list:
    """
    从视频中提取多个缩略图

    Args:
        video_path: 视频文件路径
        output_dir: 输出目录
        count: 缩略图数量
        interval: 缩略图之间的间隔（秒），如果为None则自动计算

    Returns:
        生成的缩略图路径列表
    """
    try:
        video_path = Path(video_path)
        if not video_path.exists():
            logger.error(f"视频文件不存在: {video_path}")
            return []

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 获取视频时长
        duration = get_video_duration(video_path)
        if not duration:
            logger.error("无法获取视频时长")
            return []

        # 计算缩略图时间点
        if interval is None:
            start_time = duration * 0.1  # 从10%处开始
            end_time = duration * 0.9  # 到90%处结束
            interval = (end_time - start_time) / (count - 1) if count > 1 else 0

        thumbnails = []
        for i in range(count):
            time_offset = duration * 0.1 + (i * interval)
            output_path = output_dir / f"thumbnail_{i+1:02d}.jpg"

            if generate_project_thumbnail(
                str(video_path),
                str(output_path),
                time_offset=time_offset
            ):
                thumbnails.append(str(output_path))

        logger.info(f"成功生成 {len(thumbnails)} 个缩略图")
        return thumbnails

    except Exception as e:
        logger.error(f"生成多个缩略图异常: {e}")
        return []


def get_video_duration(video_path: str) -> Optional[float]:
    """
    获取视频时长

    Args:
        video_path: 视频文件路径

    Returns:
        视频时长（秒），如果失败返回None
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return float(result.stdout.strip())
        else:
            logger.error(f"获取视频时长失败: {result.stderr}")
            return None

    except Exception as e:
        logger.error(f"获取视频时长异常: {e}")
        return None
