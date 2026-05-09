"""
口音检测工具
识别音频中的口音类型
"""
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class AccentType(str, Enum):
    """口音类型枚举"""
    AUTO = "auto"
    MANDARIN = "mandarin"
    SHANDONG = "shandong"
    SICHUAN = "sichuan"
    GUANGDONG = "guangdong"


class AccentDetector:
    """口音检测器"""
    
    # 各口音的发音特征关键词
    ACCENT_FEATURES = {
        AccentType.SHANDONG: {
            "patterns": [
                ("len", "ren"),  # 人发 len
                ("sui", "shui"),  # 水发 sui
                ("san", "shan"),  # 山发 san
                ("ping", "平调"),
            ],
            "keywords": ["俺", "啥", "咋", "咧", "呗", "啦", "哎"],
            "description": "山东口音"
        },
        AccentType.SICHUAN: {
            "patterns": [
                ("lan", "nan"),  # 四川口音 n 和 l 不分
                ("han", "huang"),
            ],
            "keywords": ["要得", "巴适", "安逸", "安逸得板", "扯拐", "扯筋"],
            "description": "四川口音"
        },
        AccentType.GUANGDONG: {
            "patterns": [],
            "keywords": ["嘅", "嘅嘢", "嘅野", "唔该", "唔好意思", "多谢", "系", "唔系"],
            "description": "广东口音"
        },
    }
    
    def __init__(self):
        self.detected_accent = None
        self.confidence = 0.0
    
    def detect(self, audio_path: Optional[Path] = None, text: Optional[str] = None) -> Tuple[AccentType, float]:
        """
        检测口音类型
        
        Args:
            audio_path: 音频文件路径（可选）
            text: 识别的文本内容（可选）
            
        Returns:
            (accent_type, confidence)
        """
        if text:
            # 优先基于文本检测（更简单快速）
            return self.detect_from_text(text)
        
        if audio_path:
            # 基于音频检测（预留接口）
            return self.detect_from_audio(audio_path)
        
        # 没有输入，默认普通话
        return AccentType.MANDARIN, 0.5
    
    def detect_from_text(self, text: str) -> Tuple[AccentType, float]:
        """
        基于文本内容检测口音
        
        Args:
            text: 识别的文本
            
        Returns:
            (accent_type, confidence)
        """
        # 简化实现：基于关键词匹配
        max_confidence = 0.0
        detected_accent = AccentType.MANDARIN
        
        for accent, features in self.ACCENT_FEATURES.items():
            score = 0.0
            max_possible = len(features["keywords"]) + len(features["patterns"]) * 2
            
            # 关键词匹配
            keyword_matches = sum(1 for keyword in features["keywords"] if keyword in text)
            score += keyword_matches / max(len(features["keywords"]), 1) * 0.7
            
            # 发音模式匹配
            pattern_matches = sum(1 for wrong, right in features["patterns"] if wrong in text)
            score += pattern_matches / max(len(features["patterns"]), 1) * 0.3
            
            if score > max_confidence:
                max_confidence = score
                detected_accent = accent
        
        # 阈值判断
        if max_confidence < 0.3:
            # 没有明显特征，默认普通话
            return AccentType.MANDARIN, 0.5
        
        logger.info(f"检测到口音: {detected_accent.value}, 置信度: {max_confidence:.2f}")
        return detected_accent, max_confidence
    
    def detect_from_audio(self, audio_path: Path) -> Tuple[AccentType, float]:
        """
        基于音频特征检测口音（预留接口）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            (accent_type, confidence)
        """
        # TODO: 未来实现基于声学特征的检测
        # 目前简单返回普通话
        logger.info("音频口音检测功能正在开发中，默认返回普通话")
        return AccentType.MANDARIN, 0.5
    
    def get_accent_info(self, accent: AccentType) -> Optional[Dict]:
        """获取口音的详细信息"""
        if accent == AccentType.MANDARIN:
            return {
                "name": "标准普通话",
                "description": "普通话/国语",
                "processor": None,
            }
        
        features = self.ACCENT_FEATURES.get(accent)
        if not features:
            return None
        
        return {
            "name": features["description"],
            "description": features["description"],
            "processor": accent.value,  # 对应的处理器名称
        }
