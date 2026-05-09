"""
山东泗水口音处理工具
针对泗水口音特点进行文本处理
"""
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SishuiAccentProcessor:
    """山东泗水口音处理器"""
    
    # 声母替换规则
    INITIAL_CONVERSIONS = {
        # 山东泗水口音特点：r 发 l，sh 发 s，zh 发 z，ch 发 c
        "r": "l",
        "sh": "s",
        "zh": "z",
        "ch": "c",
    }
    
    # 韵母替换规则
    FINAL_CONVERSIONS = {
        "an": "ang",
        "en": "eng",
        "in": "ing",
    }
    
    # 词汇级替换
    WORD_CORRECTIONS = {
        # 常见发音错误修正
        "len": "人",
        "ren": "人",
        "san": "山",
        "shan": "山",
        "sui": "水",
        "shui": "水",
        "zai": "知",
        "zhi": "知",
        "ci": "吃",
        "chi": "吃",
        "ban": "班",
        "bang": "班",
        "gen": "根",
        "geng": "根",
        "jin": "金",
        "jing": "金",
        # 泗水方言词汇
        "俺": "我",
        "俺们": "我们",
        "咋": "怎么",
        "啥": "什么",
        "呗": "吧",
        "咧": "啦",
        "沾": "行",
        "中": "行",
        "得劲": "舒服",
    }
    
    # 声调偏差修正（常见误识别的词）
    TONE_CORRECTIONS = {
        "一": "一",
        "二": "二",
        "三": "三",
        "四": "四",
        "五": "五",
        "六": "六",
        "七": "七",
        "八": "八",
        "九": "九",
        "十": "十",
    }
    
    def __init__(self):
        # 加载更高级的 pypinyin 拼音处理（如果可用）
        self.pypinyin_available = False
        self.pypinyin = None
        self._init_pypinyin()
    
    def _init_pypinyin(self):
        """初始化拼音处理库"""
        try:
            import pypinyin
            self.pypinyin = pypinyin
            self.pypinyin_available = True
            logger.info("✅ pypinyin 加载成功")
        except ImportError:
            logger.warning("pypinyin 未安装，高级拼音处理不可用")
            self.pypinyin_available = False
        except Exception as e:
            logger.warning(f"pypinyin 初始化失败: {e}")
            self.pypinyin_available = False
    
    def process(self, text: str) -> str:
        """
        处理泗水口音文本
        
        Args:
            text: 识别的原始文本
            
        Returns:
            处理后的标准文本
        """
        result = text
        
        # 步骤 1: 词汇级替换（优先，因为最准确）
        result = self._apply_word_corrections(result)
        
        # 步骤 2: 规则级替换
        result = self._apply_rule_corrections(result)
        
        # 步骤 3: 声调修正
        result = self._apply_tone_corrections(result)
        
        return result
    
    def _apply_word_corrections(self, text: str) -> str:
        """应用词汇级替换"""
        result = text
        
        for wrong, right in self.WORD_CORRECTIONS.items():
            # 简单替换
            result = result.replace(wrong, right)
        
        return result
    
    def _apply_rule_corrections(self, text: str) -> str:
        """应用规则级替换"""
        # 简单实现：基于已知模式的替换
        result = text
        
        # TODO: 更智能的替换逻辑，基于上下文判断是否应该替换
        for wrong, right in self.WORD_CORRECTIONS.items():
            if wrong in result:
                result = result.replace(wrong, right)
        
        return result
    
    def _apply_tone_corrections(self, text: str) -> str:
        """应用声调修正"""
        # 泗水口音声调偏平，可能导致词误识别
        # 这是一个占位实现
        return text
    
    def process_srt_content(self, srt_content: str) -> str:
        """处理 SRT 字幕内容"""
        lines = srt_content.splitlines()
        processed_lines = []
        
        for line in lines:
            if line.strip() == "" or "-->" in line or line.strip().isdigit():
                processed_lines.append(line)
                continue
            
            # 只对字幕文本内容处理
            processed_text = self.process(line)
            processed_lines.append(processed_text)
        
        return "\n".join(processed_lines)
    
    def process_srt_file(self, srt_path: Path) -> Optional[Path]:
        """处理 SRT 字幕文件"""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            processed_content = self.process_srt_content(srt_content)
            
            processed_path = srt_path.parent / f"{srt_path.stem}_sishui_processed{srt_path.suffix}"
            with open(processed_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            
            logger.info(f"泗水口音处理完成: {processed_path}")
            return processed_path
            
        except Exception as e:
            logger.error(f"泗水口音处理失败: {e}")
            return None
