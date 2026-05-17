"""
处理策略基类
定义所有处理模式的通用接口和数据结构
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from backend.models.enums import ProcessMode

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """
    流水线执行结果
    所有策略的统一返回格式
    """
    status: str  # "success", "partial", "failed"
    mode: ProcessMode
    outputs: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    quality_level: int = 0
    is_demo: bool = False
    degradation_history: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.completed_at is None:
            self.completed_at = datetime.now()
        if self.quality_level == 0:
            self.quality_level = ProcessMode.get_quality_level(self.mode)
        if self.is_demo is False:
            self.is_demo = ProcessMode.is_demo_mode(self.mode)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于API响应）"""
        return {
            "status": self.status,
            "mode": self.mode.value,
            "outputs": self.outputs,
            "warnings": self.warnings,
            "errors": self.errors,
            "quality_level": self.quality_level,
            "is_demo": self.is_demo,
            "degradation_history": self.degradation_history,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": (self.completed_at - self.started_at).total_seconds()
        }

    @property
    def is_successful(self) -> bool:
        """是否执行成功"""
        return self.status == "success" or self.status == "partial"

    @property
    def has_outputs(self) -> bool:
        """是否有有效输出"""
        return len(self.outputs) > 0


@dataclass
class PipelineContext:
    """
    流水线执行上下文
    传递给策略的所有必要信息
    """
    project_id: str
    video_path: Path
    srt_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    output_dir: Optional[Path] = None
    config: Dict[str, Any] = field(default_factory=dict)
    requested_mode: Optional[ProcessMode] = None
    llm_available: bool = True
    llm_config_snapshot: Optional[Dict[str, Any]] = None
    progress_callback: Optional[callable] = None

    def __post_init__(self):
        if self.output_dir is None:
            self.output_dir = self.video_path.parent


class PipelineStrategy(ABC):
    """
    处理策略基类
    所有具体策略都必须实现这个接口
    """

    @abstractmethod
    def get_mode(self) -> ProcessMode:
        """获取策略对应的处理模式"""
        pass

    @abstractmethod
    def get_capabilities(self) -> Set[str]:
        """获取策略支持的能力列表"""
        pass

    @abstractmethod
    def get_quality_level(self) -> int:
        """获取策略的质量等级（1-5）"""
        pass

    def is_demo_mode(self) -> bool:
        """是否为演示模式"""
        return ProcessMode.is_demo_mode(self.get_mode())

    def requires_llm(self) -> bool:
        """是否依赖LLM"""
        return ProcessMode.requires_llm(self.get_mode())

    @abstractmethod
    def can_execute(self, context: PipelineContext) -> bool:
        """
        判断该策略是否可以在给定上下文中执行
        用于降级决策
        """
        pass

    @abstractmethod
    def _execute_impl(self, context: PipelineContext) -> PipelineResult:
        """
        策略的具体实现
        子类必须重写这个方法
        """
        pass

    def execute(self, context: PipelineContext) -> PipelineResult:
        """
        执行策略（包装方法，包含通用逻辑）
        """
        mode_name = ProcessMode.get_display_name(self.get_mode())
        logger.info(f"开始执行策略: {mode_name}")
        
        try:
            # 检查是否可以执行
            if not self.can_execute(context):
                return PipelineResult(
                    status="failed",
                    mode=self.get_mode(),
                    errors=[f"策略 {mode_name} 无法在当前环境执行"]
                )
            
            # 执行具体实现
            result = self._execute_impl(context)
            
            # 确保结果模式正确
            result.mode = self.get_mode()
            result.is_demo = self.is_demo_mode()
            result.quality_level = self.get_quality_level()
            
            logger.info(f"策略执行完成: {mode_name} → {result.status}")
            return result
            
        except Exception as e:
            logger.error(f"策略执行异常: {mode_name}", exc_info=True)
            return PipelineResult(
                status="failed",
                mode=self.get_mode(),
                errors=[f"执行异常: {str(e)}"]
            )

