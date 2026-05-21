"""
流水线选择器
支持在原流水线和FunClip风格流水线之间切换
使用配置文件持久化模式设置
"""

import logging
import json
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_FILE = Path(__file__).parent / "pipeline_mode.json"


class PipelineSelector:
    """
    流水线选择器

    支持以下模式：
    - legacy: 使用原6步流水线
    - funclip: 使用FunClip风格的单步LLM流水线
    - ab_test: 同时运行两种流水线，用于对比

    funclip 子模式（由 funclip_sub_mode 控制）：
    - two_stage: 两阶段方案（默认，先识别边界再生成标题）
    - merged: 合并方案（单次LLM调用完成所有任务）
    """

    def __init__(self):
        self.mode = self._load_mode()  # 从配置文件加载模式
        self.funclip_sub_mode = 'two_stage'  # funclip 子模式
        self.ab_test_ratio = 0.1  # 10%流量用于A/B测试
    
    def _load_mode(self) -> str:
        """从配置文件加载模式"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.funclip_sub_mode = config.get('funclip_sub_mode', 'two_stage')
                    return config.get('mode', 'legacy')
        except Exception as e:
            logger.warning(f"加载流水线模式失败: {e}")
        return 'legacy'
    
    def _save_mode(self):
        """保存模式到配置文件"""
        try:
            config = {
                'mode': self.mode,
                'funclip_sub_mode': self.funclip_sub_mode,
                'ab_test_ratio': self.ab_test_ratio
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f"流水线模式已保存: mode={self.mode}, sub_mode={self.funclip_sub_mode}")
        except Exception as e:
            logger.error(f"保存流水线模式失败: {e}")
    
    def set_mode(self, mode: str, ab_test_ratio: float = None, funclip_sub_mode: str = None):
        """设置流水线模式"""
        self.mode = mode
        if ab_test_ratio is not None:
            self.ab_test_ratio = ab_test_ratio
        if funclip_sub_mode is not None:
            self.funclip_sub_mode = funclip_sub_mode
        self._save_mode()
        logger.info(f"流水线模式已切换为: mode={mode}, sub_mode={self.funclip_sub_mode}")
    
    def select_pipeline(self, project_id: str) -> str:
        """
        选择要使用的流水线

        Args:
            project_id: 项目ID

        Returns:
            "legacy", "funclip", 或 "ab_test"
        """
        if self.mode == "legacy":
            return "legacy"

        if self.mode == "funclip":
            return "funclip"

        if self.mode == "ab_test":
            # 基于项目ID哈希分配
            hash_val = hash(project_id) % 100
            if hash_val < self.ab_test_ratio * 100:
                return "funclip"
            else:
                return "legacy"

        return "legacy"

    def run_pipeline(self, pipeline_type: str, **kwargs):
        """
        运行选定的流水线

        Args:
            pipeline_type: "legacy" 或 "funclip"
            **kwargs: 流水线参数

        Returns:
            流水线执行结果
        """
        if pipeline_type == "legacy":
            return self._run_legacy_pipeline(**kwargs)
        elif pipeline_type == "funclip":
            return self._run_funclip_pipeline(**kwargs)
        else:
            raise ValueError(f"不支持的流水线类型: {pipeline_type}")

    def _run_legacy_pipeline(self, **kwargs):
        """运行原6步流水线"""
        logger.info("使用原6步流水线...")

        from ..services.simple_pipeline_adapter import SimplePipelineAdapter
        
        adapter = SimplePipelineAdapter(
            project_id=kwargs.get('project_id'),
            task_id=kwargs.get('task_id')
        )
        
        return adapter.process_project_sync(
            kwargs.get('video_path'),
            kwargs.get('srt_path')
        )

    def _run_funclip_pipeline(self, **kwargs):
        """运行FunClip风格的单步流水线"""
        logger.info("使用FunClip风格单步LLM流水线...")
        
        try:
            from .funclip_style import run_funclip_pipeline
            
            return run_funclip_pipeline(
                srt_path=kwargs.get('srt_path'),
                video_path=kwargs.get('video_path'),
                metadata_dir=kwargs.get('metadata_dir'),
                clips_output_dir=kwargs.get('clips_output_dir'),
                collections_output_dir=kwargs.get('collections_output_dir')
            )
        except Exception as e:
            logger.warning(f"FunClip方案执行失败: {e}，回退到legacy方案")
            return self._run_legacy_pipeline(**kwargs)

    def compare_results(self, legacy_result: Dict, 
                      funclip_result: Dict) -> Dict[str, Any]:
        """
        对比两种流水线的结果

        Args:
            legacy_result: 原流水线结果
            funclip_result: FunClip方案结果

        Returns:
            对比报告
        """
        comparison = {
            'llm_calls_estimated': {
                'legacy': '10-15次',
                'funclip': '1次',
                'savings': '90%'
            },
            'clips_count': {
                'legacy': len(legacy_result.get('clips', []) if isinstance(legacy_result, dict) else 0),
                'funclip': len(funclip_result.get('clips', []) if isinstance(funclip_result, dict) else 0)
            },
            'collections_count': {
                'legacy': len(legacy_result.get('collections', []) if isinstance(legacy_result, dict) else 0),
                'funclip': len(funclip_result.get('collections', []) if isinstance(funclip_result, dict) else 0)
            }
        }

        return comparison


# 全局选择器实例
pipeline_selector = PipelineSelector()


def get_pipeline_selector() -> PipelineSelector:
    """获取流水线选择器"""
    return pipeline_selector
