"""
处理编排器（支持降级）
负责策略选择、降级决策和执行
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from backend.models.enums import (
    LLMConfigStatus,
    ProcessMode,
    DegradationLevel,
    PipelineError,
    LLMStatusInfo,
)
from backend.pipeline.strategies import (
    PipelineStrategy,
    PipelineResult,
    PipelineContext,
)
from backend.services.config_snapshot_manager import (
    ConfigSnapshotManager,
    get_snapshot_manager,
)

logger = logging.getLogger(__name__)


class LLMStateMonitor:
    """
    LLM状态监控器
    实时检测LLM可用性，为降级决策提供依据
    """
    
    def __init__(self, cache_ttl_seconds: int = 60):
        self.cache_ttl_seconds = cache_ttl_seconds
        self._last_check_time: Optional[datetime] = None
        self._cached_status: Optional[LLMStatusInfo] = None
        
    def get_current_status(self) -> LLMStatusInfo:
        """获取当前LLM状态（带缓存）"""
        now = datetime.now()
        
        # 检查缓存是否有效
        if (
            self._cached_status is not None and 
            self._last_check_time is not None and
            (now - self._last_check_time).total_seconds() < self.cache_ttl_seconds
        ):
            return self._cached_status
        
        # 重新获取状态
        status = self._check_llm_status()
        self._cached_status = status
        self._last_check_time = now
        
        return status
    
    def _check_llm_status(self) -> LLMStatusInfo:
        """检查LLM配置状态"""
        try:
            # 检查API Key是否配置
            from backend.core.config import get_settings
            settings = get_settings()
            
            if not settings.api_dashscope_api_key:
                return LLMStatusInfo(
                    status=LLMConfigStatus.NOT_CONFIGURED,
                    message="LLM未配置，请在设置中添加API Key"
                )
            
            # 简单的连接测试
            from backend.utils.llm_client import LLMClient
            test_client = LLMClient()
            
            try:
                test_client.ping()  # 假设LLMClient有ping方法
                return LLMStatusInfo(
                    status=LLMConfigStatus.CONFIGURED,
                    message="LLM正常可用",
                    provider="dashscope",
                    model=settings.api_model_name
                )
            except Exception as e:
                logger.warning(f"LLM连接测试失败: {e}")
                return LLMStatusInfo(
                    status=LLMConfigStatus.CONNECTION_FAILED,
                    message="无法连接到LLM服务"
                )
                
        except Exception as e:
            logger.error(f"检查LLM状态时出错: {e}")
            return LLMStatusInfo(
                status=LLMConfigStatus.SERVICE_UNAVAILABLE,
                message="检查LLM状态时出错"
            )
    
    def is_llm_available(self) -> bool:
        """检查LLM是否可用"""
        status = self.get_current_status()
        return LLMConfigStatus.is_available(status.status)


class StrategyRegistry:
    """
    策略注册表
    管理所有可用的处理策略
    """
    
    def __init__(self):
        self._strategies: Dict[ProcessMode, PipelineStrategy] = {}
        self._mode_order: List[ProcessMode] = []  # 降级顺序
        
    def register(self, strategy: PipelineStrategy, mode_order: int = None):
        """注册策略"""
        mode = strategy.get_mode()
        self._strategies[mode] = strategy
        
        if mode_order is not None:
            if mode_order >= len(self._mode_order):
                self._mode_order.append(mode)
            else:
                self._mode_order.insert(mode_order, mode)
        else:
            self._mode_order.append(mode)
    
    def get_strategy(self, mode: ProcessMode) -> Optional[PipelineStrategy]:
        """获取指定模式的策略"""
        return self._strategies.get(mode)
    
    def get_available_strategies(self, llm_available: bool = True) -> List[PipelineStrategy]:
        """获取可用的策略列表"""
        strategies = []
        for mode, strategy in self._strategies.items():
            if not llm_available and strategy.requires_llm():
                continue
            strategies.append(strategy)
        return strategies
    
    def get_degradation_chain(
        self,
        start_mode: ProcessMode,
        llm_available: bool = True
    ) -> List[PipelineStrategy]:
        """获取降级链"""
        # 从起始模式开始，找到在模式顺序中的位置
        try:
            start_idx = self._mode_order.index(start_mode)
        except ValueError:
            start_idx = 0
        
        # 获取从起始位置开始的所有后续策略
        chain = []
        for i in range(start_idx, len(self._mode_order)):
            mode = self._mode_order[i]
            strategy = self._strategies.get(mode)
            if strategy and (llm_available or not strategy.requires_llm()):
                chain.append(strategy)
        
        return chain


class PipelineDirector:
    """
    流水线导演
    负责任务调度、降级决策和执行
    """
    
    def __init__(
        self,
        config: Dict[str, Any] = None,
        strategy_registry: StrategyRegistry = None,
        llm_monitor: LLMStateMonitor = None,
        snapshot_manager: ConfigSnapshotManager = None
    ):
        self.config = config or {}
        self.strategy_registry = strategy_registry or StrategyRegistry()
        self.llm_monitor = llm_monitor or LLMStateMonitor()
        self.snapshot_manager = snapshot_manager or get_snapshot_manager()
        
        # 注册默认策略
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """注册默认策略"""
        # 导入具体策略类（需要先创建）
        try:
            # 这里需要实现具体的策略类
            # 先注册简单策略作为占位符
            logger.info("策略注册表初始化完成")
        except Exception as e:
            logger.warning(f"注册策略时出错: {e}")
    
    def _decide_mode(
        self,
        project_id: str,
        requested_mode: Optional[ProcessMode]
    ) -> ProcessMode:
        """
        决定实际使用的处理模式
        
        决策逻辑：
        1. 如果项目有快照，优先使用快照中的模式
        2. 如果LLM可用，使用请求的模式或默认AI模式
        3. 如果LLM不可用，降级到字幕模式
        """
        # 检查是否有快照
        snapshot = self.snapshot_manager.get_snapshot(project_id)
        if snapshot and snapshot.is_locked:
            logger.info(f"使用配置快照中的模式: {snapshot.mode.value}")
            return snapshot.mode
        
        # 获取当前LLM状态
        llm_status = self.llm_monitor.get_current_status()
        llm_available = llm_status.is_available
        
        # 决定模式
        if requested_mode:
            # 用户指定了模式，检查是否可用
            if requested_mode.requires_llm and not llm_available:
                logger.warning(f"请求的模式 {requested_mode.value} 需要LLM，但LLM不可用，降级到字幕模式")
                return ProcessMode.SUBTITLE_ORGANIZED
            return requested_mode
        
        # 没有指定模式，使用默认逻辑
        if llm_available:
            return ProcessMode.AI_SMART
        else:
            return ProcessMode.SUBTITLE_ORGANIZED
    
    def process(
        self,
        project_id: str,
        video_path: Path,
        srt_path: Optional[Path] = None,
        audio_path: Optional[Path] = None,
        requested_mode: Optional[ProcessMode] = None,
        output_dir: Optional[Path] = None
    ) -> PipelineResult:
        """
        执行流水线处理（完整流程）
        
        Args:
            project_id: 项目ID
            video_path: 视频文件路径
            srt_path: 字幕文件路径
            audio_path: 音频文件路径
            requested_mode: 请求的处理模式
            output_dir: 输出目录
        
        Returns:
            PipelineResult - 处理结果
        """
        logger.info(f"开始处理项目: {project_id}")
        
        # 获取LLM状态
        llm_status = self.llm_monitor.get_current_status()
        llm_available = llm_status.is_available
        
        # 决定使用的模式
        mode = self._decide_mode(project_id, requested_mode)
        
        # 创建上下文
        context = PipelineContext(
            project_id=project_id,
            video_path=video_path,
            srt_path=srt_path,
            audio_path=audio_path,
            output_dir=output_dir,
            requested_mode=requested_mode,
            llm_available=llm_available
        )
        
        # 检查是否需要创建快照
        if not self.snapshot_manager.has_snapshot(project_id):
            self.snapshot_manager.create_snapshot(
                project_id=project_id,
                mode=mode,
                llm_status=llm_status
            )
        
        # 执行策略
        result = self._execute_with_degradation(context, mode)
        
        # 记录结果
        logger.info(f"项目处理完成: {project_id}, 模式: {result.mode.value}, 状态: {result.status}")
        return result
    
    def _execute_with_degradation(
        self,
        context: PipelineContext,
        start_mode: ProcessMode
    ) -> PipelineResult:
        """
        执行并在失败时降级
        
        降级链：
        AI_SMART → SUBTITLE_ORGANIZED → RAW_TRANSCRIPT → FRIENDLY_ERROR
        """
        # 获取降级链
        degradation_chain = self.strategy_registry.get_degradation_chain(
            start_mode, context.llm_available
        )
        
        # 如果降级链为空，确保至少有一个备选
        if not degradation_chain:
            logger.warning("策略链为空，使用最低级别的策略")
            from backend.pipeline.concrete_strategies import RawTranscriptStrategy  # 占位
            degradation_chain = [RawTranscriptStrategy()]
        
        degradation_history = []
        
        # 尝试策略链
        for strategy in degradation_chain:
            mode_name = strategy.get_mode().value
            logger.info(f"尝试策略: {mode_name}")
            
            try:
                result = strategy.execute(context)
                
                if result.is_successful:
                    result.degradation_history = degradation_history
                    return result
                else:
                    # 策略执行失败但没有异常，继续降级
                    warning = f"策略 {mode_name} 执行失败，状态: {result.status}"
                    degradation_history.append(warning)
                    logger.warning(warning)
                    
            except Exception as e:
                # 策略执行异常，继续降级
                error_msg = f"策略 {mode_name} 执行异常: {str(e)}"
                degradation_history.append(error_msg)
                logger.error(error_msg, exc_info=True)
        
        # 所有策略都失败，返回友好错误
        logger.error("所有策略都执行失败")
        return PipelineResult(
            status="failed",
            mode=ProcessMode.RAW_TRANSCRIPT,
            errors=["所有处理策略都失败了，请稍后重试或联系支持"],
            warnings=degradation_history
        )
    
    def retry_with_different_mode(
        self,
        project_id: str,
        new_mode: ProcessMode
    ) -> Optional[PipelineResult]:
        """
        使用不同模式重试已有的项目
        
        Args:
            project_id: 项目ID
            new_mode: 新模式
        
        Returns:
            重试结果
        """
        logger.info(f"项目 {project_id} 重试，新模式: {new_mode.value}")
        
        # 获取快照
        snapshot = self.snapshot_manager.get_snapshot(project_id)
        if not snapshot:
            logger.error(f"项目 {project_id} 没有找到配置快照")
            return None
        
        # TODO: 这里需要重新执行处理，需要项目的路径信息
        # 暂时返回None，表示需要重新上传
        return None


# 全局导演实例
_director: Optional[PipelineDirector] = None


def get_pipeline_director() -> PipelineDirector:
    """获取全局流水线导演"""
    global _director
    if _director is None:
        _director = PipelineDirector()
    return _director

