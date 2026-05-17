"""
具体处理策略实现
包括：AI智能模式、字幕整理模式、快速预览模式、原始转录模式
"""

import logging
import json
from typing import Set, Dict, Any, Optional, List
from pathlib import Path

from backend.models.enums import ProcessMode
from backend.pipeline.strategies import (
    PipelineStrategy,
    PipelineResult,
    PipelineContext,
)
from backend.utils.local_scorer import LocalScorer, local_score_clips

logger = logging.getLogger(__name__)


class AISmartStrategy(PipelineStrategy):
    """AI智能模式策略 - 完整LLM功能"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    def get_mode(self) -> ProcessMode:
        return ProcessMode.AI_SMART
    
    def get_capabilities(self) -> Set[str]:
        return {"subtitle", "outline", "highlights", "titles", "collections", "semantic"}
    
    def get_quality_level(self) -> int:
        return 5
    
    def requires_llm(self) -> bool:
        return True
    
    def can_execute(self, context: PipelineContext) -> bool:
        return context.llm_available
    
    def _execute_impl(self, context: PipelineContext) -> PipelineResult:
        """执行AI智能模式"""
        logger.info("执行AI智能模式")
        
        outputs = {}
        warnings = []
        
        try:
            # 这里调用原有的流水线处理
            # Step 1-6的完整流程
            if context.srt_path is None or not context.srt_path.exists():
                # 先生成字幕
                logger.info("正在生成字幕")
                subtitle_result = self._generate_subtitle(context)
                if subtitle_result.get("success"):
                    outputs["subtitle"] = subtitle_result.get("path")
                else:
                    warnings.append("字幕生成可能不完整")
            
            # 继续原有的处理流程
            # TODO: 调用原有的step1-step6
            outputs["outline"] = "outline.json"
            outputs["highlights"] = "highlights.json"
            outputs["titles"] = "titles.json"
            outputs["collections"] = "collections.json"
            
            return PipelineResult(
                status="success",
                mode=self.get_mode(),
                outputs=outputs,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"AI智能模式执行异常: {e}", exc_info=True)
            raise
    
    def _generate_subtitle(self, context: PipelineContext) -> Dict[str, Any]:
        """生成字幕的简单实现"""
        # 调用speech_recognizer或其他模块
        return {"success": True, "path": str(context.output_dir / "subtitle.srt")}


class SubtitleOrganizedStrategy(PipelineStrategy):
    """字幕整理模式策略 - 降级但有价值"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    def get_mode(self) -> ProcessMode:
        return ProcessMode.SUBTITLE_ORGANIZED
    
    def get_capabilities(self) -> Set[str]:
        return {"subtitle"}
    
    def get_quality_level(self) -> int:
        return 3
    
    def can_execute(self, context: PipelineContext) -> bool:
        # 字幕整理模式总是可以执行（即使没有LLM）
        return True
    
    def _execute_impl(self, context: PipelineContext) -> PipelineResult:
        """执行字幕整理模式"""
        logger.info("执行字幕整理模式")
        
        outputs = {}
        warnings = []
        
        try:
            if context.srt_path and context.srt_path.exists():
                outputs["subtitle"] = str(context.srt_path)
                outputs["subtitle_organized"] = self._organize_subtitle(context.srt_path, context.output_dir)
            else:
                # 先生成字幕
                logger.info("正在生成字幕")
                subtitle_result = self._generate_subtitle(context)
                if subtitle_result.get("success"):
                    outputs["subtitle"] = subtitle_result.get("path")
                    outputs["subtitle_organized"] = self._organize_subtitle(
                        Path(subtitle_result.get("path")), context.output_dir
                    )
                else:
                    warnings.append("字幕生成可能不完整")
            
            return PipelineResult(
                status="success",
                mode=self.get_mode(),
                outputs=outputs,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"字幕整理模式执行异常: {e}", exc_info=True)
            raise
    
    def _organize_subtitle(self, srt_path: Path, output_dir: Path) -> str:
        """整理字幕（简单实现）"""
        organized_path = output_dir / "subtitle_organized.srt"
        # TODO: 实际的整理逻辑
        return str(organized_path)
    
    def _generate_subtitle(self, context: PipelineContext) -> Dict[str, Any]:
        """生成字幕"""
        return {"success": True, "path": str(context.output_dir / "subtitle.srt")}


class QuickPreviewStrategy(PipelineStrategy):
    """快速预览模式策略 - 仅演示"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    def get_mode(self) -> ProcessMode:
        return ProcessMode.QUICK_PREVIEW
    
    def get_capabilities(self) -> Set[str]:
        return {"subtitle", "basic_segments"}
    
    def get_quality_level(self) -> int:
        return 1
    
    def is_demo_mode(self) -> bool:
        return True
    
    def can_execute(self, context: PipelineContext) -> bool:
        # 预览模式总是可以执行
        return True
    
    def _execute_impl(self, context: PipelineContext) -> PipelineResult:
        """执行快速预览模式"""
        logger.info("执行快速预览模式")
        
        outputs = {}
        warnings = []
        
        try:
            # 生成或使用已有字幕
            if context.srt_path and context.srt_path.exists():
                srt_path = context.srt_path
            else:
                logger.info("正在生成字幕")
                subtitle_result = self._generate_subtitle(context)
                if subtitle_result.get("success"):
                    srt_path = Path(subtitle_result.get("path"))
                    outputs["subtitle"] = str(srt_path)
                else:
                    return PipelineResult(
                        status="failed",
                        mode=self.get_mode(),
                        errors=["无法生成字幕用于预览"]
                    )
            
            # 解析字幕
            srt_data = self._parse_srt(srt_path)
            
            # 本地评分
            scorer = LocalScorer(audio_path=context.audio_path)
            scored_clips = scorer.score_clips(srt_data, context.audio_path)
            
            # 保存结果
            preview_output = context.output_dir / "preview_highlights.json"
            with open(preview_output, 'w', encoding='utf-8') as f:
                json.dump({
                    "clips": [s.to_dict() for s in scored_clips],
                    "method": "local_preview",
                    "quality_note": "[WARN] 仅供预览，非AI智能识别"
                }, f, ensure_ascii=False, indent=2)
            
            outputs["preview_highlights"] = str(preview_output)
            
            warnings.append("[WARN] 快速预览仅供演示，不代表正式AI智能识别效果")
            
            return PipelineResult(
                status="success",
                mode=self.get_mode(),
                outputs=outputs,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"快速预览模式执行异常: {e}", exc_info=True)
            raise
    
    def _generate_subtitle(self, context: PipelineContext) -> Dict[str, Any]:
        """生成字幕"""
        return {"success": True, "path": str(context.output_dir / "subtitle.srt")}
    
    def _parse_srt(self, srt_path: Path) -> List[Dict[str, Any]]:
        """简单解析SRT"""
        segments = []
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 简单的SRT解析
            blocks = content.strip().split('\n\n')
            for i, block in enumerate(blocks):
                lines = block.split('\n')
                if len(lines) >= 3:
                    # 跳过序号
                    time_line = lines[1]
                    content_line = ' '.join(lines[2:])
                    
                    # 解析时间
                    start_time = time_line.split(' --> ')[0]
                    end_time = time_line.split(' --> ')[1]
                    
                    segments.append({
                        "id": i,
                        "start_time": start_time,
                        "end_time": end_time,
                        "content": content_line
                    })
        except Exception as e:
            logger.warning(f"解析SRT失败: {e}")
        
        return segments


class RawTranscriptStrategy(PipelineStrategy):
    """原始转录模式策略 - 最基础"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    def get_mode(self) -> ProcessMode:
        return ProcessMode.RAW_TRANSCRIPT
    
    def get_capabilities(self) -> Set[str]:
        return {"subtitle"}
    
    def get_quality_level(self) -> int:
        return 2
    
    def can_execute(self, context: PipelineContext) -> bool:
        return True
    
    def _execute_impl(self, context: PipelineContext) -> PipelineResult:
        """执行原始转录模式"""
        logger.info("执行原始转录模式")
        
        outputs = {}
        warnings = []
        
        try:
            if context.srt_path and context.srt_path.exists():
                outputs["subtitle_raw"] = str(context.srt_path)
            else:
                logger.info("正在生成字幕")
                subtitle_result = self._generate_subtitle(context)
                if subtitle_result.get("success"):
                    outputs["subtitle_raw"] = subtitle_result.get("path")
                else:
                    warnings.append("字幕生成可能不完整")
            
            warnings.append("[WARN] 原始转录模式仅提供基本字幕")
            
            return PipelineResult(
                status="success",
                mode=self.get_mode(),
                outputs=outputs,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"原始转录模式执行异常: {e}", exc_info=True)
            raise
    
    def _generate_subtitle(self, context: PipelineContext) -> Dict[str, Any]:
        """生成字幕"""
        return {"success": True, "path": str(context.output_dir / "subtitle_raw.srt")}


# 注册所有策略
def register_all_strategies(registry):
    """向策略注册表注册所有策略"""
    registry.register(AISmartStrategy(), mode_order=0)
    registry.register(SubtitleOrganizedStrategy(), mode_order=1)
    registry.register(QuickPreviewStrategy(), mode_order=2)
    registry.register(RawTranscriptStrategy(), mode_order=3)
    logger.info("所有策略已注册")

