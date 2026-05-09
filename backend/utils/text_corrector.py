"""
文本纠错工具
提供多层级的文本纠错功能
"""
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class TextCorrector:
    """文本纠错器，提供三层级纠错功能"""
    
    def __init__(self):
        # 规则级纠错：常见错别字映射
        self.common_corrections = {
            # 的地得
            "地": "的",  # 简单规则，实际应用可能需要更复杂
            "做用": "作用",
            "象形": "像形",
            "座落": "坐落",
            "缘份": "缘分",
            "水份": "水分",
            "份量": "分量",
            "定单": "订单",
            "登陆": "登录",
            "帐户": "账户",
            "帐号": "账号",
            "帐户": "账户",
            # 数字和量词
            "二": "两",  # 在量词前用两，不是二
        }
        
        # 山东口音常见发音错误映射
        self.shandong_corrections = {
            "len": "人",
            "san": "山",
            "sui": "水",
            "zai": "知",
            "zai": "吃",
            "ban": "邦",
            "gen": "跟",
            "jin": "今",
        }
        
        # 尝试导入 pycorrector
        self.pycorrector_available = False
        self.corrector = None
        self._init_pycorrector()
    
    def _init_pycorrector(self):
        """初始化 pycorrector（统计级纠错）"""
        try:
            import pycorrector
            self.corrector = pycorrector.Corrector()
            self.pycorrector_available = True
            logger.info("✅ pycorrector 加载成功")
        except ImportError:
            logger.warning("pycorrector 未安装，统计级纠错不可用")
            self.pycorrector_available = False
        except Exception as e:
            logger.warning(f"pycorrector 初始化失败: {e}")
            self.pycorrector_available = False
    
    def correct(self, text: str, level: int = 2) -> str:
        """
        多层级纠错
        
        Args:
            text: 原始文本
            level: 纠错级别
                0 = 不纠错
                1 = 规则级（快速）
                2 = 规则+统计级（标准）
                3 = 规则+统计+语义级（深度）
            
        Returns:
            纠错后的文本
        """
        if level <= 0:
            return text
        
        # 规则级纠错
        corrected = self._rule_based_correct(text)
        
        if level >= 2:
            # 统计级纠错
            corrected = self._statistical_correct(corrected)
        
        if level >= 3:
            # 语义级纠错（可选）
            corrected = self._semantic_correct(corrected)
        
        return corrected
    
    def _rule_based_correct(self, text: str) -> str:
        """规则级纠错"""
        result = text
        
        # 应用常见错别字纠正
        for wrong, right in self.common_corrections.items():
            result = result.replace(wrong, right)
        
        # 应用山东口音纠正
        for wrong, right in self.shandong_corrections.items():
            result = result.replace(wrong, right)
        
        return result
    
    def _statistical_correct(self, text: str) -> str:
        """统计级纠错（基于 pycorrector）"""
        if not self.pycorrector_available or not self.corrector:
            return text
        
        try:
            corrected_text, _ = self.corrector.correct(text)
            return corrected_text
        except Exception as e:
            logger.warning(f"pycorrector 纠错失败: {e}")
            return text
    
    def _semantic_correct(self, text: str) -> str:
        """语义级纠错（预留，未来可集成 LLM）"""
        # TODO: 未来实现 LLM 语义纠错
        return text
    
    def correct_srt_content(self, srt_content: str, level: int = 2) -> str:
        """
        纠错 SRT 字幕内容
        
        Args:
            srt_content: SRT 字幕文本
            level: 纠错级别
            
        Returns:
            纠错后的 SRT 字幕
        """
        if level <= 0:
            return srt_content
        
        lines = srt_content.splitlines()
        corrected_lines = []
        
        for line in lines:
            # 跳过时间行和空行
            if line.strip() == "" or "-->" in line or line.strip().isdigit():
                corrected_lines.append(line)
                continue
            
            # 只对字幕文本内容纠错
            corrected_text = self.correct(line, level)
            corrected_lines.append(corrected_text)
        
        return "\n".join(corrected_lines)
    
    def correct_srt_file(self, srt_path: Path, level: int = 2) -> Optional[Path]:
        """
        纠错 SRT 字幕文件
        
        Args:
            srt_path: SRT 文件路径
            level: 纠错级别
            
        Returns:
            纠错后的文件路径，失败返回 None
        """
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            corrected_content = self.correct_srt_content(srt_content, level)
            
            # 保存纠错后的文件（覆盖原文件或保存为新文件）
            corrected_path = srt_path.parent / f"{srt_path.stem}_corrected{srt_path.suffix}"
            with open(corrected_path, 'w', encoding='utf-8') as f:
                f.write(corrected_content)
            
            logger.info(f"字幕纠错完成: {corrected_path}")
            return corrected_path
            
        except Exception as e:
            logger.error(f"字幕纠错失败: {e}")
            return None
