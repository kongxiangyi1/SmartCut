"""
枚举定义模块
定义LLM配置状态、处理模式、项目状态等核心枚举
与其他模块共享枚举定义
"""

import enum
from typing import List, Set
from dataclasses import dataclass
from datetime import datetime


class LLMConfigStatus(str, enum.Enum):
    """
    LLM配置状态枚举
    用于描述LLM配置的当前状态
    """
    NOT_CONFIGURED = "not_configured"           # 完全未配置
    INVALID_KEY = "invalid_key"                 # API Key无效
    SERVICE_UNAVAILABLE = "service_unavailable"  # 服务不可用
    RATE_LIMITED = "rate_limited"               # 配额用完
    CONNECTION_FAILED = "connection_failed"     # 连接失败
    TIMEOUT = "timeout"                        # 超时
    CONFIGURED = "configured"                  # 正常可用

    @classmethod
    def is_available(cls, status: "LLMConfigStatus") -> bool:
        """判断当前状态是否表示LLM可用"""
        return status == cls.CONFIGURED

    @classmethod
    def is_error(cls, status: "LLMConfigStatus") -> bool:
        """判断当前状态是否表示错误"""
        return status in {
            cls.INVALID_KEY,
            cls.SERVICE_UNAVAILABLE,
            cls.RATE_LIMITED,
            cls.CONNECTION_FAILED,
            cls.TIMEOUT
        }

    @classmethod
    def get_user_message(cls, status: "LLMConfigStatus") -> str:
        """获取用户友好的状态描述"""
        messages = {
            cls.NOT_CONFIGURED: "AI模型未配置，请先在设置中添加API密钥",
            cls.INVALID_KEY: "AI模型API密钥无效，请检查并重新配置",
            cls.SERVICE_UNAVAILABLE: "AI模型服务暂时不可用，请稍后再试",
            cls.RATE_LIMITED: "AI模型配额已用完，请明天再试或升级套餐",
            cls.CONNECTION_FAILED: "无法连接到AI模型服务，请检查网络连接",
            cls.TIMEOUT: "AI模型响应超时，请稍后重试",
            cls.CONFIGURED: "AI模型已配置并可用"
        }
        return messages.get(status, "未知状态")


class ProcessMode(str, enum.Enum):
    """
    处理模式枚举
    定义视频处理的不同模式
    """
    # 正式生产模式
    AI_SMART = "ai_smart"                     # AI智能模式（最佳体验）
    SUBTITLE_ORGANIZED = "subtitle_organized"  # 字幕整理模式（降级可用）

    # 演示预览模式
    QUICK_PREVIEW = "quick_preview"           # 快速预览（仅演示）
    RAW_TRANSCRIPT = "raw_transcript"         # 原始转写（仅文本）

    @classmethod
    def is_production_mode(cls, mode: "ProcessMode") -> bool:
        """是否为正式生产模式"""
        return mode in {cls.AI_SMART, cls.SUBTITLE_ORGANIZED}

    @classmethod
    def is_demo_mode(cls, mode: "ProcessMode") -> bool:
        """是否为演示模式"""
        return mode in {cls.QUICK_PREVIEW, cls.RAW_TRANSCRIPT}

    @classmethod
    def requires_llm(cls, mode: "ProcessMode") -> bool:
        """是否依赖LLM"""
        return mode == cls.AI_SMART

    @classmethod
    def get_quality_level(cls, mode: "ProcessMode") -> int:
        """获取模式的质量等级（1-5）"""
        levels = {
            cls.AI_SMART: 5,
            cls.SUBTITLE_ORGANIZED: 3,
            cls.QUICK_PREVIEW: 1,
            cls.RAW_TRANSCRIPT: 2,
        }
        return levels.get(mode, 0)

    @classmethod
    def get_capabilities(cls, mode: "ProcessMode") -> Set[str]:
        """获取模式支持的能力"""
        capabilities_map = {
            cls.AI_SMART: {
                "subtitle", "outline", "highlights",
                "titles", "collections", "semantic"
            },
            cls.SUBTITLE_ORGANIZED: {"subtitle"},
            cls.QUICK_PREVIEW: {"subtitle", "basic_segments"},
            cls.RAW_TRANSCRIPT: {"subtitle"},
        }
        return capabilities_map.get(mode, set())

    @classmethod
    def get_display_name(cls, mode: "ProcessMode") -> str:
        """获取用户可见的显示名称"""
        names = {
            cls.AI_SMART: "AI智能模式",
            cls.SUBTITLE_ORGANIZED: "字幕整理模式",
            cls.QUICK_PREVIEW: "快速预览",
            cls.RAW_TRANSCRIPT: "原始转写",
        }
        return names.get(mode, mode.value)

    @classmethod
    def get_short_name(cls, mode: "ProcessMode") -> str:
        """获取简短名称"""
        names = {
            cls.AI_SMART: "AI智能",
            cls.SUBTITLE_ORGANIZED: "字幕整理",
            cls.QUICK_PREVIEW: "预览",
            cls.RAW_TRANSCRIPT: "原始",
        }
        return names.get(mode, mode.value)


class DegradationLevel(int, enum.Enum):
    """
    降级层级枚举
    数值越大，降级程度越深
    """
    LEVEL_1_AI_SMART = 1        # AI智能模式（最高质量）
    LEVEL_2_SUBTITLE = 2        # 字幕整理模式
    LEVEL_3_RAW = 3            # 原始转写模式
    LEVEL_4_ERROR = 4           # 友好错误提示（最低）


class PipelineError(str, enum.Enum):
    """流水线错误枚举"""
    # LLM相关错误
    LLM_NOT_CONFIGURED = "llm_not_configured"
    LLM_INVALID_KEY = "llm_invalid_key"
    LLM_RATE_LIMITED = "llm_rate_limited"
    LLM_SERVICE_UNAVAILABLE = "llm_service_unavailable"
    LLM_CONNECTION_FAILED = "llm_connection_failed"
    LLM_TIMEOUT = "llm_timeout"
    LLM_RESPONSE_PARSE_ERROR = "llm_response_parse_error"

    # 处理错误
    SUBTITLE_GENERATION_FAILED = "subtitle_generation_failed"
    VIDEO_NOT_FOUND = "video_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    INSUFFICIENT_STORAGE = "insufficient_storage"
    PROCESSING_TIMEOUT = "processing_timeout"

    # 降级失败
    DEGRADATION_FAILED = "degradation_failed"
    ALL_STRATEGIES_FAILED = "all_strategies_failed"

    @classmethod
    def is_llm_error(cls, error: "PipelineError") -> bool:
        """是否为LLM相关错误"""
        return error in {
            cls.LLM_NOT_CONFIGURED, cls.LLM_INVALID_KEY,
            cls.LLM_RATE_LIMITED, cls.LLM_SERVICE_UNAVAILABLE,
            cls.LLM_CONNECTION_FAILED, cls.LLM_TIMEOUT,
            cls.LLM_RESPONSE_PARSE_ERROR
        }

    @classmethod
    def is_recoverable(cls, error: "PipelineError") -> bool:
        """是否可恢复（可降级）"""
        return error in {
            cls.LLM_NOT_CONFIGURED, cls.LLM_INVALID_KEY,
            cls.LLM_RATE_LIMITED, cls.LLM_SERVICE_UNAVAILABLE,
            cls.LLM_CONNECTION_FAILED, cls.LLM_TIMEOUT,
            cls.LLM_RESPONSE_PARSE_ERROR, cls.SUBTITLE_GENERATION_FAILED
        }

    @classmethod
    def get_suggestion(cls, error: "PipelineError") -> str:
        """获取错误解决建议"""
        suggestions = {
            cls.LLM_NOT_CONFIGURED: "请在设置中配置AI模型的API密钥",
            cls.LLM_INVALID_KEY: "请检查API密钥是否正确，可尝试重新获取",
            cls.LLM_RATE_LIMITED: "AI模型配额已用完，请明天再试或升级套餐",
            cls.LLM_SERVICE_UNAVAILABLE: "AI模型服务暂时不可用，请稍后重试",
            cls.LLM_CONNECTION_FAILED: "无法连接到AI模型服务，请检查网络连接",
            cls.LLM_TIMEOUT: "AI模型响应超时，请稍后重试",
            cls.SUBTITLE_GENERATION_FAILED: "语音识别失败，请检查视频是否有音频",
            cls.VIDEO_NOT_FOUND: "视频文件未找到，请重新上传",
            cls.UNSUPPORTED_FORMAT: "不支持的视频格式，请使用MP4、AVI等常见格式",
        }
        return suggestions.get(error, "请稍后重试，如问题持续请联系技术支持")


@dataclass
class LLMStatusInfo:
    """
    LLM状态详细信息
    用于API响应和内部状态传递
    """
    status: LLMConfigStatus
    message: str
    provider: str = ""
    model: str = ""
    available_modes: List[str] = None
    retry_after: int = 0  # 配额重置时间（秒）
    last_check: datetime = None

    def __post_init__(self):
        if self.available_modes is None:
            self.available_modes = []
        if self.last_check is None:
            self.last_check = datetime.now()

    def to_dict(self) -> dict:
        """转换为字典（用于JSON序列化）"""
        return {
            "status": self.status.value,
            "message": self.message,
            "provider": self.provider,
            "model": self.model,
            "available_modes": self.available_modes,
            "retry_after": self.retry_after,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "is_available": self.is_available
        }

    @property
    def is_available(self) -> bool:
        """LLM是否可用"""
        return self.status == LLMConfigStatus.CONFIGURED

    @property
    def is_rate_limited(self) -> bool:
        """是否配额用完"""
        return self.status == LLMConfigStatus.RATE_LIMITED


@dataclass
class ModeSelectionInfo:
    """
    模式选择信息
    用于前端展示模式选项
    """
    mode: ProcessMode
    name: str
    short_name: str
    description: str
    badge: str = ""
    badge_color: str = ""
    icon: str = ""
    recommended: bool = False
    requires_llm: bool = False
    is_demo: bool = False
    capabilities: List[str] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "mode": self.mode.value,
            "name": self.name,
            "shortName": self.short_name,
            "description": self.description,
            "badge": self.badge,
            "badgeColor": self.badge_color,
            "icon": self.icon,
            "recommended": self.recommended,
            "requiresLLM": self.requires_llm,
            "isDemo": self.is_demo,
            "capabilities": self.capabilities,
        }

    @classmethod
    def get_all_modes_info(cls) -> List["ModeSelectionInfo"]:
        """获取所有模式的选择信息"""
        return [
            ModeSelectionInfo(
                mode=ProcessMode.AI_SMART,
                name="AI智能模式",
                short_name="AI智能",
                description="使用AI深度理解视频内容，生成精彩片段、智能标题和主题合集",
                badge="推荐",
                badge_color="green",
                icon="[AI]",
                recommended=True,
                requires_llm=True,
                is_demo=False,
                capabilities=["字幕生成", "大纲提取", "精彩片段", "智能标题", "主题聚类"]
            ),
            ModeSelectionInfo(
                mode=ProcessMode.SUBTITLE_ORGANIZED,
                name="字幕整理模式",
                short_name="字幕整理",
                description="将字幕标准化整理，包括说话人标注和标点恢复，无AI分析",
                badge="免费",
                badge_color="blue",
                icon="[NOTE]",
                recommended=False,
                requires_llm=False,
                is_demo=False,
                capabilities=["字幕生成", "说话人标注", "标点恢复"]
            ),
            ModeSelectionInfo(
                mode=ProcessMode.QUICK_PREVIEW,
                name="快速预览",
                short_name="预览",
                description="仅供效果预览，使用基础算法模拟切片，不可用于正式业务",
                badge="演示",
                badge_color="orange",
                icon="[EYE]",
                recommended=False,
                requires_llm=False,
                is_demo=True,
                capabilities=["字幕生成", "基础分段"]
            ),
            ModeSelectionInfo(
                mode=ProcessMode.RAW_TRANSCRIPT,
                name="原始转写",
                short_name="原始",
                description="仅输出语音转写的原始文本，无任何处理",
                badge="基础",
                badge_color="gray",
                icon="📄",
                recommended=False,
                requires_llm=False,
                is_demo=False,
                capabilities=["字幕生成"]
            ),
        ]


# 导出所有枚举和数据类
__all__ = [
    "LLMConfigStatus",
    "ProcessMode",
    "DegradationLevel",
    "PipelineError",
    "LLMStatusInfo",
    "ModeSelectionInfo",
]

