"""
复用库管理器
管理可复用片段的存储和检索
"""
import json
import logging
import shutil
import threading
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import hashlib

from .exceptions import ReuseLibraryError

logger = logging.getLogger(__name__)

class ReuseLibrary:
    """复用库管理器"""
    
    def __init__(self, library_dir: Path = None):
        if library_dir is None:
            library_dir = Path(__file__).parent.parent.parent / "data" / "reuse_library"
        
        self.library_dir = library_dir
        self.library_dir.mkdir(parents=True, exist_ok=True)
        
        self.clips_dir = self.library_dir / "clips"
        self.clips_dir.mkdir(exist_ok=True)
        
        self.metadata_dir = self.library_dir / "metadata"
        self.metadata_dir.mkdir(exist_ok=True)
        
        self.index_file = self.library_dir / "index.json"
        
        self._lock = threading.Lock()
        self._index = {}
        self._load_index()
    
    def _load_index(self):
        """加载索引"""
        with self._lock:
            if self.index_file.exists():
                try:
                    with open(self.index_file, 'r', encoding='utf-8') as f:
                        self._index = json.load(f)
                except Exception as e:
                    logger.error(f"索引加载失败: {e}")
                    self._index = self._create_empty_index()
            else:
                self._index = self._create_empty_index()
    
    def _create_empty_index(self) -> Dict:
        """创建空索引结构"""
        return {
            "version": "1.0",
            "clips": [],
            "by_product": {},
            "by_category": {},
            "by_tag": {},
            "by_reuse_value": {},
            "last_updated": None
        }
    
    def _save_index(self):
        """保存索引"""
        with self._lock:
            self._index["last_updated"] = datetime.now().isoformat()
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
    
    def _generate_id(self, clip_path: Path) -> str:
        """生成片段ID"""
        return hashlib.md5(str(clip_path).encode()).hexdigest()[:12]
    
    def _update_index(self, clip_info: Dict):
        """更新索引"""
        clip_id = clip_info["id"]
        product_name = clip_info.get("product_name")
        category = clip_info.get("category")
        tags = clip_info.get("tags", [])
        reuse_value = clip_info.get("reuse_value", 0.0)
        
        # 产品索引
        if product_name:
            if product_name not in self._index["by_product"]:
                self._index["by_product"][product_name] = []
            if clip_id not in self._index["by_product"][product_name]:
                self._index["by_product"][product_name].append(clip_id)
        
        # 类别索引
        if category:
            if category not in self._index["by_category"]:
                self._index["by_category"][category] = []
            if clip_id not in self._index["by_category"][category]:
                self._index["by_category"][category].append(clip_id)
        
        # 标签索引
        for tag in tags:
            if tag not in self._index["by_tag"]:
                self._index["by_tag"][tag] = []
            if clip_id not in self._index["by_tag"][tag]:
                self._index["by_tag"][tag].append(clip_id)
        
        # 复用价值索引（分段）
        value_range = f"{int(reuse_value * 10) * 10}-{int(reuse_value * 10) * 10 + 10}"
        if value_range not in self._index["by_reuse_value"]:
            self._index["by_reuse_value"][value_range] = []
        if clip_id not in self._index["by_reuse_value"][value_range]:
            self._index["by_reuse_value"][value_range].append(clip_id)
    
    def add_clip(self, clip_path: Path, metadata: Dict, copy_file: bool = True) -> str:
        """
        添加片段到复用库

        Args:
            clip_path: 片段文件路径
            metadata: 元数据
            copy_file: 是否复制视频文件到复用库（默认True）

        Returns:
            片段ID
        """
        with self._lock:
            clip_id = self._generate_id(clip_path)

            existing_clips = {clip["id"]: clip for clip in self._index["clips"]}
            if clip_id in existing_clips:
                logger.warning(f"片段已存在: {clip_id}")
                return clip_id

            relative_path = None
            if copy_file and clip_path.exists():
                dest_clip_path = self.clips_dir / f"{clip_id}.mp4"
                try:
                    shutil.copy2(clip_path, dest_clip_path)
                    relative_path = f"clips/{clip_id}.mp4"
                    logger.info(f"已复制视频文件到: {dest_clip_path}")
                except Exception as e:
                    logger.error(f"复制视频文件失败: {e}，使用原始路径")
                    relative_path = str(clip_path) if clip_path.is_absolute() else str(clip_path)
            else:
                if clip_path.is_absolute():
                    relative_path = str(clip_path)
                else:
                    relative_path = str(clip_path.relative_to(self.library_dir)) if clip_path.exists() else str(clip_path)

            clip_info = {
                "id": clip_id,
                "path": relative_path,
                "duration": metadata.get("duration", 0.0),
                "product_name": metadata.get("product_name"),
                "category": metadata.get("category"),
                "reuse_value": metadata.get("reuse_value", 0.0),
                "tags": metadata.get("tags", []),
                "source_clip_id": metadata.get("source_clip_id"),
                "source_video": metadata.get("source_video"),
                "source_start": metadata.get("source_start"),
                "source_end": metadata.get("source_end"),
                "added_at": datetime.now().isoformat(),
                "file_exists": clip_path.exists() if not copy_file else True
            }

            self._index["clips"].append(clip_info)

            self._update_index(clip_info)

            self._save_index()

            logger.info(f"添加片段到复用库: {clip_id}, 路径: {relative_path}")
            return clip_id
    
    def search_by_product(self, product_name: str) -> List[Dict]:
        """
        按产品名搜索
        
        Args:
            product_name: 产品名称
        
        Returns:
            匹配的片段列表
        """
        clip_ids = self._index["by_product"].get(product_name, [])
        return [clip for clip in self._index["clips"] if clip["id"] in clip_ids]
    
    def search_by_category(self, category: str) -> List[Dict]:
        """
        按类别搜索
        
        Args:
            category: 类别名称
        
        Returns:
            匹配的片段列表
        """
        clip_ids = self._index["by_category"].get(category, [])
        return [clip for clip in self._index["clips"] if clip["id"] in clip_ids]
    
    def search_by_tag(self, tag: str) -> List[Dict]:
        """
        按标签搜索
        
        Args:
            tag: 标签名称
        
        Returns:
            匹配的片段列表
        """
        clip_ids = self._index["by_tag"].get(tag, [])
        return [clip for clip in self._index["clips"] if clip["id"] in clip_ids]
    
    def get_high_reuse_clips(self, min_value: float = 0.7) -> List[Dict]:
        """
        获取高复用价值片段
        
        Args:
            min_value: 最小复用价值
        
        Returns:
            高复用价值片段列表
        """
        return [
            clip for clip in self._index["clips"]
            if clip.get("reuse_value", 0.0) >= min_value
        ]
    
    def get_clip_by_id(self, clip_id: str) -> Optional[Dict]:
        """
        按ID获取片段

        Args:
            clip_id: 片段ID

        Returns:
            片段信息或None
        """
        for clip in self._index["clips"]:
            if clip["id"] == clip_id:
                return clip
        return None

    def get_clip_full_path(self, clip_id: str) -> Optional[Path]:
        """获取片段的绝对路径"""
        clip = self.get_clip_by_id(clip_id)
        if not clip:
            return None

        path = Path(clip["path"])
        if path.is_absolute():
            return path if path.exists() else None

        full_path = self.library_dir / path
        return full_path if full_path.exists() else None
    
    def delete_clip(self, clip_id: str) -> bool:
        """
        删除片段
        
        Args:
            clip_id: 片段ID
        
        Returns:
            是否删除成功
        """
        with self._lock:
            # 查找并删除
            clip = self.get_clip_by_id(clip_id)
            if not clip:
                return False
            
            # 从列表中删除
            self._index["clips"] = [c for c in self._index["clips"] if c["id"] != clip_id]
            
            # 从索引中删除
            product_name = clip.get("product_name")
            if product_name and clip_id in self._index["by_product"].get(product_name, []):
                self._index["by_product"][product_name].remove(clip_id)
            
            category = clip.get("category")
            if category and clip_id in self._index["by_category"].get(category, []):
                self._index["by_category"][category].remove(clip_id)
            
            for tag, ids in self._index["by_tag"].items():
                if clip_id in ids:
                    ids.remove(clip_id)
            
            # 删除文件
            clip_path = self.library_dir / clip["path"]
            if clip_path.exists():
                clip_path.unlink()
            
            # 删除元数据
            metadata_path = self.metadata_dir / f"{clip_id}.json"
            if metadata_path.exists():
                metadata_path.unlink()
            
            # 保存索引
            self._save_index()
            
            logger.info(f"删除片段: {clip_id}")
            return True
    
    def get_all_clips(self) -> List[Dict]:
        """获取所有片段"""
        return self._index["clips"]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._index["clips"])
        by_product = len(self._index["by_product"])
        by_category = len(self._index["by_category"])
        by_tag = len(self._index["by_tag"])
        
        avg_reuse_value = 0.0
        if total > 0:
            avg_reuse_value = sum(clip.get("reuse_value", 0.0) for clip in self._index["clips"]) / total
        
        return {
            "total_clips": total,
            "total_products": by_product,
            "total_categories": by_category,
            "total_tags": by_tag,
            "avg_reuse_value": round(avg_reuse_value, 2),
            "last_updated": self._index["last_updated"]
        }