"""
配置快照管理器
用于保存和恢复处理开始时的LLM配置，确保历史任务不受后续配置变更影响
"""

import logging
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import os

from backend.models.enums import ProcessMode, LLMStatusInfo, LLMConfigStatus

logger = logging.getLogger(__name__)


@dataclass
class ConfigSnapshot:
    """
    配置快照数据类
    保存处理开始时的完整配置信息
    """
    project_id: str
    mode: ProcessMode
    llm_provider: str
    llm_model: str
    llm_config_snapshot: Dict[str, Any] = field(default_factory=dict)
    is_locked: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    stored_at: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于持久化）"""
        return {
            "project_id": self.project_id,
            "mode": self.mode.value,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_config_snapshot": self.llm_config_snapshot,
            "is_locked": self.is_locked,
            "created_at": self.created_at.isoformat(),
            "stored_at": str(self.stored_at) if self.stored_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigSnapshot":
        """从字典恢复"""
        mode = ProcessMode(data.get("mode", ProcessMode.RAW_TRANSCRIPT.value))
        created_at = datetime.fromisoformat(data.get("created_at"))
        stored_at = Path(data.get("stored_at")) if data.get("stored_at") else None
        
        return cls(
            project_id=data.get("project_id", ""),
            mode=mode,
            llm_provider=data.get("llm_provider", ""),
            llm_model=data.get("llm_model", ""),
            llm_config_snapshot=data.get("llm_config_snapshot", {}),
            is_locked=data.get("is_locked", True),
            created_at=created_at,
            stored_at=stored_at
        )


class ConfigSnapshotManager:
    """
    配置快照管理器
    负责创建、保存和加载配置快照
    """

    def __init__(self, snapshots_dir: Optional[Path] = None):
        if snapshots_dir is None:
            # 默认存储路径
            from backend.core.config import get_project_root
            snapshots_dir = get_project_root() / "data" / "snapshots"
        
        self.snapshots_dir = snapshots_dir
        self._cache: Dict[str, ConfigSnapshot] = {}
        
        # 确保目录存在
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"配置快照管理器初始化: {snapshots_dir}")

    def create_snapshot(
        self,
        project_id: str,
        mode: ProcessMode,
        llm_status: Optional[LLMStatusInfo] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        lock_config: bool = True
    ) -> ConfigSnapshot:
        """
        创建并保存配置快照

        Args:
            project_id: 项目ID
            mode: 处理模式
            llm_status: LLM状态信息
            llm_config: LLM配置字典
            lock_config: 是否锁定配置

        Returns:
            配置快照对象
        """
        # 收集配置信息
        llm_provider = llm_status.provider if llm_status else ""
        llm_model = llm_status.model if llm_status else ""
        
        # 创建快照对象
        snapshot = ConfigSnapshot(
            project_id=project_id,
            mode=mode,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_config_snapshot=llm_config or {},
            is_locked=lock_config
        )
        
        # 保存到文件
        self._save_snapshot(snapshot)
        
        # 缓存
        self._cache[project_id] = snapshot
        
        logger.info(f"创建配置快照: {project_id}, 模式: {mode.value}")
        return snapshot

    def get_snapshot(self, project_id: str) -> Optional[ConfigSnapshot]:
        """
        获取项目的配置快照

        Args:
            project_id: 项目ID

        Returns:
            配置快照，如果不存在返回None
        """
        # 先查缓存
        if project_id in self._cache:
            return self._cache[project_id]
        
        # 再查文件
        snapshot_path = self._get_snapshot_path(project_id)
        if snapshot_path.exists():
            snapshot = self._load_snapshot(snapshot_path)
            self._cache[project_id] = snapshot
            return snapshot
        
        return None

    def has_snapshot(self, project_id: str) -> bool:
        """检查项目是否有配置快照"""
        return (project_id in self._cache) or self._get_snapshot_path(project_id).exists()

    def validate_snapshot(self, snapshot: ConfigSnapshot, current_llm_available: bool) -> Dict[str, Any]:
        """
        验证配置快照是否仍然有效

        Args:
            snapshot: 配置快照
            current_llm_available: 当前LLM是否可用

        Returns:
            验证结果字典
        """
        result = {
            "valid": True,
            "warnings": [],
            "recommendations": []
        }
        
        # 检查锁定状态
        if snapshot.is_locked:
            result["warnings"].append("配置已锁定，将使用处理开始时的配置")
        else:
            result["warnings"].append("配置未锁定，可能使用了最新配置")
        
        # 检查LLM可用性
        if snapshot.mode.requires_llm and not current_llm_available:
            result["valid"] = False
            result["recommendations"].append("当前LLM不可用，建议降级到字幕模式")
        
        return result

    def list_snapshots(self) -> List[ConfigSnapshot]:
        """列出所有配置快照"""
        snapshots = []
        for snapshot_file in self.snapshots_dir.glob("*.json"):
            try:
                snapshot = self._load_snapshot(snapshot_file)
                snapshots.append(snapshot)
            except Exception as e:
                logger.warning(f"加载快照失败: {snapshot_file.name}, 错误: {e}")
        
        # 按创建时间排序
        snapshots.sort(key=lambda s: s.created_at, reverse=True)
        return snapshots

    def delete_snapshot(self, project_id: str) -> bool:
        """删除项目的配置快照"""
        snapshot_path = self._get_snapshot_path(project_id)
        
        if snapshot_path.exists():
            snapshot_path.unlink()
            if project_id in self._cache:
                del self._cache[project_id]
            logger.info(f"删除配置快照: {project_id}")
            return True
        
        return False

    def cleanup_old_snapshots(self, keep_days: int = 30) -> int:
        """
        清理旧的配置快照

        Args:
            keep_days: 保留天数

        Returns:
            清理的快照数量
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0
        
        for snapshot_file in self.snapshots_dir.glob("*.json"):
            try:
                snapshot = self._load_snapshot(snapshot_file)
                if snapshot.created_at < cutoff:
                    snapshot_file.unlink()
                    deleted_count += 1
                    
                    # 清除缓存
                    if snapshot.project_id in self._cache:
                        del self._cache[snapshot.project_id]
                        
            except Exception as e:
                logger.warning(f"清理快照失败: {snapshot_file.name}, 错误: {e}")
        
        logger.info(f"清理配置快照: 删除 {deleted_count} 个，保留 {keep_days} 天以内")
        return deleted_count

    def _get_snapshot_path(self, project_id: str) -> Path:
        """获取快照文件路径"""
        # 清理文件名中的非法字符
        safe_project_id = "".join(c for c in project_id if c.isalnum() or c in "_-")
        return self.snapshots_dir / f"{safe_project_id}.json"

    def _save_snapshot(self, snapshot: ConfigSnapshot) -> None:
        """保存快照到文件"""
        snapshot_path = self._get_snapshot_path(snapshot.project_id)
        snapshot.stored_at = snapshot_path
        
        try:
            with open(snapshot_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存配置快照失败: {snapshot_path}", exc_info=True)
            raise

    def _load_snapshot(self, path: Path) -> ConfigSnapshot:
        """从文件加载快照"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        snapshot = ConfigSnapshot.from_dict(data)
        snapshot.stored_at = path
        return snapshot


# 全局管理器实例
_snapshot_manager: Optional[ConfigSnapshotManager] = None


def get_snapshot_manager() -> ConfigSnapshotManager:
    """获取全局配置快照管理器"""
    global _snapshot_manager
    if _snapshot_manager is None:
        _snapshot_manager = ConfigSnapshotManager()
    return _snapshot_manager

