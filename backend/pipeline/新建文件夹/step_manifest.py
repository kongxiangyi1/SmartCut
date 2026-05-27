"""
步骤数据契约管理器

解决P0问题#1：步骤间数据耦合过紧问题
实现步骤执行前的依赖验证，确保数据完整性
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# 定义每个步骤所需的数据契约
STEPS_DEPENDENCIES = {
    "step1_outline": {
        "required": [],
        "optional": [],
        "outputs": ["step1_chunks", "step1_srt_chunks", "step1_output.json"]
    },
    "step2_timeline": {
        "required": ["step1_srt_chunks"],
        "optional": [],
        "outputs": ["step2_timeline_chunks", "step2_llm_raw_output", "step2_timeline.json"]
    },
    "step3_scoring": {
        "required": ["step2_timeline.json"],
        "optional": ["step2_timeline_chunks"],
        "outputs": ["step3_scored_clips.json"]
    },
    "step4_title": {
        "required": ["step3_scored_clips.json"],
        "optional": [],
        "outputs": ["step4_titles.json"]
    },
    "step5_clustering": {
        "required": ["step4_titles.json"],
        "optional": [],
        "outputs": ["step5_clusters.json"]
    },
    "step6_video": {
        "required": ["step5_clusters.json", "input_video", "srt_file"],
        "optional": [],
        "outputs": ["clips", "collections"]
    }
}


class StepManifestManager:
    """
    步骤契约管理器
    负责检查步骤执行前的依赖条件，确保数据完整性
    """

    def __init__(self, project_id: str, metadata_dir: Path):
        self.project_id = project_id
        self.metadata_dir = metadata_dir
        self.manifest_path = metadata_dir / "step_manifest.json"
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        """加载或初始化manifest文件"""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Manifest文件损坏，重新初始化: {self.manifest_path}")
                return self._create_empty_manifest()
        return self._create_empty_manifest()

    def _create_empty_manifest(self) -> Dict[str, Any]:
        """创建空manifest"""
        manifest = {
            "project_id": self.project_id,
            "created_at": "",
            "updated_at": "",
            "steps": {}
        }
        self._save_manifest(manifest)
        return manifest

    def _save_manifest(self, manifest: Dict[str, Any]):
        """保存manifest"""
        manifest["updated_at"] = Path(__file__).parent.parent.name  # 简单版本标记
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def get_step_status(self, step_name: str) -> Optional[Dict[str, Any]]:
        """获取步骤执行状态"""
        return self._manifest.get("steps", {}).get(step_name)

    def mark_step_completed(self, step_name: str, success: bool = True, error: Optional[str] = None):
        """标记步骤完成状态"""
        if "steps" not in self._manifest:
            self._manifest["steps"] = {}
        
        self._manifest["steps"][step_name] = {
            "completed": success,
            "timestamp": "",
            "error": error,
            "output_files": []
        }
        self._save_manifest(self._manifest)

    def validate_step_dependencies(self, step_name: str) -> bool:
        """
        验证步骤执行所需的依赖是否满足
        
        Args:
            step_name: 要执行的步骤名称
            
        Returns:
            True - 所有依赖满足
            False - 依赖缺失或不完整
        """
        if step_name not in STEPS_DEPENDENCIES:
            logger.warning(f"未知步骤: {step_name}")
            return True  # 允许未知步骤通过（用于扩展）
        
        dependencies = STEPS_DEPENDENCIES[step_name]
        required_deps = dependencies.get("required", [])
        
        # 检查所有必需依赖
        for dep_dir in required_deps:
            dep_path = self.metadata_dir / dep_dir
            if not dep_path.exists():
                logger.error(f"步骤 {step_name} 依赖缺失: {dep_dir}")
                return False
            
            # 检查目录不为空（除了特殊的JSON文件依赖）
            if not dep_dir.endswith('.json'):
                files = list(dep_path.glob('*'))
                if not files:
                    logger.error(f"步骤 {step_name} 依赖目录为空: {dep_dir}")
                    return False
        
        # 特殊检查：JSON文件是否存在且非空
        for dep_file in required_deps:
            if dep_file.endswith('.json'):
                file_path = self.metadata_dir / dep_file
                if file_path.exists() and file_path.stat().st_size == 0:
                    logger.error(f"步骤 {step_name} JSON文件为空: {dep_file}")
                    return False
        
        # 检查前置步骤是否已完成
        if self._has_completed_steps():
            if not self._check_step_order(step_name):
                logger.error(f"步骤 {step_name} 的前置步骤未完成")
                return False
        
        logger.info(f"步骤 {step_name} 的依赖检查通过")
        return True

    def _has_completed_steps(self) -> bool:
        """检查是否有已完成的步骤"""
        return bool(self._manifest.get("steps"))

    def _check_step_order(self, step_name: str) -> bool:
        """检查步骤执行顺序是否正确"""
        steps_order = list(STEPS_DEPENDENCIES.keys())
        current_idx = steps_order.index(step_name)
        
        # 检查所有前置步骤是否已完成
        for i in range(current_idx):
            prev_step = steps_order[i]
            step_status = self._manifest.get("steps", {}).get(prev_step)
            if step_status is None or not step_status.get("completed", False):
                logger.error(f"前置步骤 {prev_step} 未完成或未标记为完成")
                return False
        
        return True

    def get_available_output_files(self, step_name: str) -> List[Path]:
        """获取步骤的可用输出文件"""
        if step_name not in STEPS_DEPENDENCIES:
            return []
        
        outputs = STEPS_DEPENDENCIES[step_name].get("outputs", [])
        available = []
        
        for output in outputs:
            output_path = self.metadata_dir / output
            if output_path.exists():
                available.append(output_path)
        
        return available


class BaseStepValidator(ABC):
    """步骤验证器基类"""
    
    @abstractmethod
    def validate(self, metadata_dir: Path) -> bool:
        pass


class SRTChunksValidator(BaseStepValidator):
    """SRT块验证器"""
    
    def validate(self, metadata_dir: Path) -> bool:
        chunks_dir = metadata_dir / "step1_srt_chunks"
        if not chunks_dir.exists():
            return False
        
        # 检查是否有SRT块文件
        chunk_files = list(chunks_dir.glob("chunk_*.json"))
        if not chunk_files:
            return False
        
        # 验证每个块文件的结构
        for chunk_file in chunk_files:
            try:
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        logger.error(f"SRT块文件格式错误: {chunk_file}")
                        return False
            except json.JSONDecodeError:
                logger.error(f"SRT块文件JSON格式错误: {chunk_file}")
                return False
        
        return True


class TimelineJsonValidator(BaseStepValidator):
    """Timeline JSON验证器"""
    
    def validate(self, metadata_dir: Path) -> bool:
        timeline_path = metadata_dir / "step2_timeline.json"
        if not timeline_path.exists():
            return False
        
        try:
            with open(timeline_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return False
                
                # 验证每个条目的必需字段
                required_fields = {'id', 'outline', 'start_time', 'end_time'}
                for item in data:
                    if not all(field in item for field in required_fields):
                        return False
                return True
        except (json.JSONDecodeError, KeyError):
            return False


class ScoredClipsValidator(BaseStepValidator):
    """评分结果验证器"""
    
    def validate(self, metadata_dir: Path) -> bool:
        scored_path = metadata_dir / "step3_scored_clips.json"
        if not scored_path.exists():
            return False
        
        try:
            with open(scored_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return False
                
                # 验证包含scoring信息
                if "clips" in data:
                    clips = data["clips"]
                    if not isinstance(clips, list):
                        return False
                    
                    # 检查至少有评分字段
                    for clip in clips[:10]:  # 检查前10个
                        if 'score' not in clip and 'final_score' not in clip:
                            return False
                return True
        except (json.JSONDecodeError, KeyError):
            return False
