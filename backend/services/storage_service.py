"""
存储服务
提供文件存储和管理功能
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class StorageService:
    """文件存储服务"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.base_storage_path = Path(f"./data/projects/{project_id}")
        self.base_storage_path.mkdir(parents=True, exist_ok=True)

    def save_file(self, file_path: Path, safe_filename: str, file_type: str) -> str:
        """
        保存文件到项目存储目录
        
        :param file_path: 源文件路径
        :param safe_filename: 安全文件名
        :param file_type: 文件类型 (raw, subtitle, video)
        :return: 保存后的文件路径
        """
        # 创建文件类型目录
        type_dir = self.base_storage_path / file_type
        type_dir.mkdir(exist_ok=True)
        
        # 目标路径
        target_path = type_dir / safe_filename
        
        # 复制文件
        shutil.copy(str(file_path), str(target_path))
        
        logger.info(f"文件保存成功: {target_path}")
        return str(target_path)

    def get_project_storage_info(self) -> Dict[str, Any]:
        """
        获取项目存储信息
        
        :return: 存储信息字典
        """
        total_size = 0
        file_count = 0
        
        if self.base_storage_path.exists():
            for file_path in self.base_storage_path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1
        
        return {
            "total_size_bytes": total_size,
            "total_size_human": self._format_size(total_size),
            "file_count": file_count,
            "storage_path": str(self.base_storage_path),
            "exists": self.base_storage_path.exists()
        }

    def cleanup_old_files(self, project_id: str, keep_days: int = 30):
        """
        清理项目旧文件
        
        :param project_id: 项目ID
        :param keep_days: 保留天数
        """
        if not self.base_storage_path.exists():
            return
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        for file_path in self.base_storage_path.rglob("*"):
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_date:
                    try:
                        file_path.unlink()
                        logger.info(f"清理旧文件: {file_path}")
                    except Exception as e:
                        logger.error(f"清理文件失败 {file_path}: {e}")

    def _format_size(self, size_bytes: int) -> str:
        """
        格式化文件大小为人类可读格式
        
        :param size_bytes: 文件大小（字节）
        :return: 格式化后的字符串
        """
        if size_bytes == 0:
            return "0 B"
        
        size_units = ["B", "KB", "MB", "GB", "TB"]
        index = 0
        
        while size_bytes >= 1024 and index < len(size_units) - 1:
            size_bytes /= 1024
            index += 1
        
        return f"{size_bytes:.2f} {size_units[index]}"

    def get_file_path(self, file_type: str, filename: str) -> Optional[str]:
        """
        获取文件路径
        
        :param file_type: 文件类型
        :param filename: 文件名
        :return: 文件路径，如果不存在返回None
        """
        file_path = self.base_storage_path / file_type / filename
        return str(file_path) if file_path.exists() else None

    def delete_file(self, file_type: str, filename: str) -> bool:
        """
        删除文件
        
        :param file_type: 文件类型
        :param filename: 文件名
        :return: 是否删除成功
        """
        file_path = self.base_storage_path / file_type / filename
        if file_path.exists():
            file_path.unlink()
            logger.info(f"文件已删除: {file_path}")
            return True
        return False

    def list_files(self, file_type: Optional[str] = None) -> list:
        """
        列出项目文件
        
        :param file_type: 文件类型过滤（可选）
        :return: 文件列表
        """
        files = []
        
        if not self.base_storage_path.exists():
            return files
        
        target_dir = self.base_storage_path / file_type if file_type else self.base_storage_path
        
        if not target_dir.exists():
            return files
        
        for file_path in target_dir.rglob("*"):
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime)
                })
        
        return files
