"""
全局ID管理器

解决P0问题#3：ID分配混乱问题
实现步骤间ID的一致性管理，确保所有步骤使用相同的ID分配
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from collections import OrderedDict
import uuid

logger = logging.getLogger(__name__)


class GlobalIDManager:
    """
    全局ID管理器
    负责在Pipeline执行过程中统一管理ID分配
    """

    def __init__(self, project_id: str, metadata_dir: Path):
        self.project_id = project_id
        self.metadata_dir = metadata_dir
        self.id_mapping_path = metadata_dir / "global_id_mapping.json"
        self.id_counter = 0
        self._mapping = self._load_mapping()

    def _load_mapping(self) -> Dict[str, Any]:
        """加载ID映射文件"""
        if self.id_mapping_path.exists():
            try:
                with open(self.id_mapping_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.id_counter = data.get("counter", 0)
                    return data.get("mapping", {})
            except json.JSONDecodeError:
                logger.warning(f"ID映射文件损坏，重新初始化: {self.id_mapping_path}")
                return {}
        return {}

    def _save_mapping(self):
        """保存ID映射文件"""
        data = {
            "counter": self.id_counter,
            "mapping": self._mapping,
            "updated_at": "",
            "total_ids": len(self._mapping)
        }
        self.id_mapping_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.id_mapping_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_or_create_id(self, source: str, source_id: Any) -> str:
        """
        获取或创建ID映射
        
        Args:
            source: 来源标识（如 "step1", "step2"）
            source_id: 来源ID（可以是字符串、整数等）
            
        Returns:
            全局唯一ID
        """
        # 检查是否已存在映射
        mapping_key = self._build_mapping_key(source, source_id)
        if mapping_key in self._mapping:
            return self._mapping[mapping_key]
        
        # 创建新ID
        new_id = self._generate_id()
        self._mapping[mapping_key] = new_id
        self.id_counter += 1
        self._save_mapping()
        
        logger.debug(f"创建ID映射: {source}:{source_id} -> {new_id}")
        return new_id

    def _build_mapping_key(self, source: str, source_id: Any) -> str:
        """构建映射键"""
        return f"{source}:{source_id}"

    def _generate_id(self) -> str:
        """生成全局唯一ID"""
        # 使用时间戳+UUID确保全局唯一性
        timestamp = str(self.id_counter).zfill(6)
        uuid_suffix = str(uuid.uuid4().hex)[:8]
        return f"clip_{timestamp}_{uuid_suffix}"

    def get_by_source(self, source: str) -> Dict[Any, str]:
        """获取指定来源的ID映射"""
        result = {}
        for key, value in self._mapping.items():
            if key.startswith(f"{source}:"):
                source_id = key[len(f"{source}:"):]
                result[source_id] = value
        return result

    def get_source_by_global_id(self, global_id: str) -> Optional[str]:
        """通过全局ID反查来源"""
        for key, value in self._mapping.items():
            if value == global_id:
                return key.split(":")[0]
        return None

    def get_source_id_by_global_id(self, global_id: str) -> Optional[Any]:
        """通过全局ID反查来源ID"""
        for key, value in self._mapping.items():
            if value == global_id:
                return key.split(":")[1]
        return None


class IDMappingValidator:
    """
    ID映射验证器
    确保ID映射的完整性和一致性
    """

    def __init__(self, id_manager: GlobalIDManager):
        self.id_manager = id_manager

    def validate_step2_timeline(self, timeline_data: List[Dict]) -> bool:
        """
        验证Step2的时间线数据ID
        确保所有条目都有全局ID
        """
        missing_ids = []
        has_duplicates = []
        seen_ids = set()
        
        for i, item in enumerate(timeline_data):
            global_id = item.get("id")
            
            if global_id is None:
                # 自动生成全局ID
                source_id = item.get("chunk_index", i)
                global_id = self.id_manager.get_or_create_id("step2", source_id)
                item["id"] = global_id
                logger.warning(f"Step2条目缺少ID，自动生成: {global_id}")
            elif global_id in seen_ids:
                # 检测重复ID
                has_duplicates.append(global_id)
                logger.warning(f"检测到重复ID: {global_id}")
            else:
                seen_ids.add(global_id)
        
        if missing_ids:
            logger.error(f"Step2中 {len(missing_ids)} 个条目缺少ID")
            return False
        
        if has_duplicates:
            logger.error(f"Step2中检测到 {len(has_duplicates)} 个重复ID")
            return False
        
        return True

    def validate_step3_scoring(self, scored_data: List[Dict]) -> bool:
        """
        验证Step3的评分数据ID
        确保评分数据与时间线ID一致
        """
        # 检查ID是否与Step2一致
        global_ids = set(self.id_manager._mapping.values())
        missing_from_mapping = []
        
        for item in scored_data:
            item_id = item.get("id")
            if item_id and item_id not in global_ids:
                # ID不在映射中，可能是外部导入的数据
                # 为其创建映射
                source_id = item.get("chunk_index", "unknown")
                self.id_manager.get_or_create_id("step3", source_id)
        
        return True

    def validate_id_consistency(self, step2_data: List[Dict], step3_data: List[Dict]) -> bool:
        """
        验证步骤间ID一致性
        确保Step3的数据能关联到Step2的数据
        """
        step2_ids = {item.get("id") for item in step2_data if item.get("id")}
        step3_ids = {item.get("id") for item in step3_data if item.get("id")}
        
        # 检查Step3的ID是否都在Step2中存在
        missing_ids = step3_ids - step2_ids
        
        if missing_ids:
            logger.warning(f"Step3中 {len(missing_ids)} 个ID在Step2中不存在")
            # 自动添加缺失的ID映射
            for item in step3_data:
                item_id = item.get("id")
                if item_id and item_id not in step2_ids:
                    item["id"] = self.id_manager.get_or_create_id("step3", item.get("chunk_index", "unknown"))
                    logger.info(f"为Step3条目补充ID: {item_id} -> {item['id']}")
        
        return True
