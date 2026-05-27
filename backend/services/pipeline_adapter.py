"""
流水线基础设施适配器 - 为ProcessingOrchestrator提供文件管理和步骤管理服务
"""
import json
import shutil
import logging
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class PipelineAdapter:
    """流水线基础设施适配器"""
    
    # 步骤输出文件映射
    STEP_OUTPUT_FILES = {
        "step1": "step1_outline.json",
        "step2": "step2_timeline.json",
        "step3": "step3_high_score_clips.json",
        "step4": "step4_titles.json",
        "step5": "step5_clusters.json",
        "step6": "clips_metadata.json",
    }
    
    # 步骤对应的子目录
    STEP_SUBDIRS = {
        "step1": ["step1_chunks", "step1_srt_chunks"],
        "step2": ["debug_responses"],
        "step3": [],
        "step4": [],
        "step5": [],
        "step6": [],
    }
    
    def __init__(self, db, task_id: str, project_id: str):
        self.db = db
        self.task_id = task_id
        self.project_id = project_id
        self.data_dir = Path("data")
        self.project_dir = self.data_dir / "projects" / project_id
        self.metadata_dir = self.project_dir / "temp"
    
    def prepare_step_environment(self, step_name: str) -> None:
        """准备步骤执行环境（创建必要的目录）"""
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建步骤对应的子目录
        subdirs = self.STEP_SUBDIRS.get(step_name, [])
        for subdir in subdirs:
            subdir_path = self.metadata_dir / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)
        
        # Step6 需要 clips 和 collections 输出目录
        if step_name == "step6":
            (self.project_dir / "clips").mkdir(parents=True, exist_ok=True)
            (self.project_dir / "collections").mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"步骤 {step_name} 环境准备完成: {self.metadata_dir}")
    
    def validate_pipeline_prerequisites(self) -> List[str]:
        """验证流水线前置条件，返回错误列表（空列表表示全部通过）"""
        errors = []
        
        # 检查项目目录是否存在
        if not self.project_dir.exists():
            errors.append(f"项目目录不存在: {self.project_dir}")
            return errors  # 目录都不存在，后续检查无意义
        
        # 检查是否有视频文件
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm']
        has_video = any(
            f.suffix.lower() in video_extensions 
            for f in self.project_dir.iterdir() 
            if f.is_file()
        )
        if not has_video:
            # 也检查子目录
            has_video = any(
                f.suffix.lower() in video_extensions
                for f in self.project_dir.rglob('*')
                if f.is_file()
            )
        if not has_video:
            errors.append(f"项目目录中未找到视频文件: {self.project_dir}")
        
        # 检查是否有SRT字幕文件
        has_srt = any(
            f.suffix.lower() == '.srt'
            for f in self.project_dir.rglob('*')
            if f.is_file()
        )
        if not has_srt:
            errors.append(f"项目目录中未找到SRT字幕文件: {self.project_dir}")
        
        return errors
    
    def get_step_output_path(self, step_name: str) -> Path:
        """获取步骤输出文件的路径"""
        filename = self.STEP_OUTPUT_FILES.get(step_name, f"{step_name}_output.json")
        return self.metadata_dir / filename
    
    def get_step_result(self, step_name: str) -> Optional[Any]:
        """读取步骤执行结果，不存在时返回None"""
        output_path = self.get_step_output_path(step_name)
        if output_path.exists():
            try:
                return json.loads(output_path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"读取步骤 {step_name} 结果失败: {e}")
                return None
        return None
    
    def cleanup_intermediate_files(self, step_name: str) -> None:
        """清理步骤的中间文件（用于重试前的清理）"""
        # 删除输出文件
        output_path = self.get_step_output_path(step_name)
        if output_path.exists():
            output_path.unlink()
            logger.debug(f"已删除步骤 {step_name} 输出文件: {output_path}")
        
        # 删除步骤对应的子目录
        subdirs = self.STEP_SUBDIRS.get(step_name, [])
        for subdir in subdirs:
            subdir_path = self.metadata_dir / subdir
            if subdir_path.exists():
                shutil.rmtree(subdir_path, ignore_errors=True)
                logger.debug(f"已清理步骤 {step_name} 子目录: {subdir_path}")
        
        # Step6 特殊处理：清理输出视频文件
        if step_name == "step6":
            for dir_name in ["clips", "collections"]:
                dir_path = self.project_dir / dir_name
                if dir_path.exists():
                    shutil.rmtree(dir_path, ignore_errors=True)
                    logger.debug(f"已清理步骤 {step_name} 输出目录: {dir_path}")
        
        logger.info(f"步骤 {step_name} 中间文件已清理完成")
    
    def step_output_exists(self, step_name: str) -> bool:
        """检查步骤输出是否已存在（用于跳过已完成的步骤）"""
        output_path = self.get_step_output_path(step_name)
        return output_path.exists()
