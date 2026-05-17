"""
路径工具模块
提供项目相关路径的便捷访问
"""
from pathlib import Path
import os

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
PROJECTS_DIR = DATA_DIR / "projects"
UPLOADS_DIR = DATA_DIR / "uploads"


def get_project_directory(project_id: str) -> Path:
    """
    获取项目的根目录

    Args:
        project_id: 项目ID

    Returns:
        项目目录路径
    """
    return PROJECTS_DIR / project_id


def get_project_raw_dir(project_id: str) -> Path:
    """
    获取项目的原始文件目录

    Args:
        project_id: 项目ID

    Returns:
        原始文件目录路径
    """
    return get_project_directory(project_id) / "raw"


def get_project_raw_directory(project_id: str) -> Path:
    """
    获取项目的原始文件目录（别名函数，保持向后兼容）

    Args:
        project_id: 项目ID

    Returns:
        原始文件目录路径
    """
    return get_project_raw_dir(project_id)


def get_project_metadata_dir(project_id: str) -> Path:
    """
    获取项目的元数据目录

    Args:
        project_id: 项目ID

    Returns:
        元数据目录路径
    """
    return get_project_directory(project_id) / "metadata"


def get_project_output_dir(project_id: str) -> Path:
    """
    获取项目的输出目录

    Args:
        project_id: 项目ID

    Returns:
        输出目录路径
    """
    return get_project_directory(project_id) / "output"


def get_project_clips_dir(project_id: str) -> Path:
    """
    获取项目的剪辑目录

    Args:
        project_id: 项目ID

    Returns:
        剪辑目录路径
    """
    return get_project_output_dir(project_id) / "clips"


def get_project_collections_dir(project_id: str) -> Path:
    """
    获取项目的合集目录

    Args:
        project_id: 项目ID

    Returns:
        合集目录路径
    """
    return get_project_output_dir(project_id) / "collections"


def ensure_project_dirs(project_id: str) -> Path:
    """
    确保项目所有必要目录存在

    Args:
        project_id: 项目ID

    Returns:
        项目根目录
    """
    project_dir = get_project_directory(project_id)
    (project_dir / "raw").mkdir(parents=True, exist_ok=True)
    (project_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (project_dir / "output").mkdir(parents=True, exist_ok=True)
    (project_dir / "output" / "clips").mkdir(parents=True, exist_ok=True)
    (project_dir / "output" / "collections").mkdir(parents=True, exist_ok=True)
    return project_dir
