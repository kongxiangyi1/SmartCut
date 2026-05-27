"""
Step 1 优化版：智能内容分析器
一次性完成大纲提取、时间定位、内容评分、标题生成
"""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict

from ..utils.text_processor import TextProcessor
from ..utils.llm_client import LLMClient
from ..core.shared_config import METADATA_DIR, MIN_SCORE_THRESHOLD

logger = logging.getLogger(__name__)

# 统一提示词
UNIFIED_ANALYSIS_PROMPT = """你是一位专业的视频内容分析师，需要一次性完成以下任务：

## 任务
1. 从SRT字幕中提取话题大纲
2. 为每个话题定位精确的时间区间
3. 评估每个话题的质量并给出评分和推荐理由
4. 为每个话题生成一个吸引人的标题

## 评分标准（final_score: 0.0-1.0）
- 信息价值：是否有独特的见解或知识
- 情感共鸣：是否能引发观众情绪
- 传播潜力：是否包含金句或易于传播的内容
- 结构完整性：是否逻辑清晰、有始有终

## 标题生成原则
- 忠于原文，不夸大
- 突出亮点，有冲击力
- 简洁有力，15-30字

## 时间定位规则
- start_time: 话题讨论的第一句开始时间
- end_time: 话题讨论的最后一句结束时间
- 最小时长: 90秒
- 最佳时长: 3-6分钟

## 输出格式（必须严格遵循JSON数组）
[
  {
    "id": 1,
    "outline": "话题标题",
    "subtopics": ["子话题1", "子话题2"],
    "start_time": "00:01:23,456",
    "end_time": "00:05:30,123",
    "content": ["核心要点1", "核心要点2"],
    "final_score": 0.85,
    "recommend_reason": "推荐理由，15-30字",
    "generated_title": "吸引人的标题"
  }
]

请严格只输出JSON数组，不要添加任何其他文字。"""


class IntelligentAnalyzer:
    """
    智能内容分析器 - 优化版
    
    一次LLM调用完成4个任务：
    1. 提取话题大纲
    2. 定位时间区间
    3. 内容评分
    4. 生成标题
    
    相比原6步流程，LLM调用次数减少75%
    """
    
    def __init__(self, metadata_dir: Path = None):
        self.llm_client = LLMClient()
        self.text_processor = TextProcessor()
        
        if metadata_dir is None:
            metadata_dir = METADATA_DIR
        self.metadata_dir = Path(metadata_dir)
        
        # 中间文件目录
        self.chunks_dir = self.metadata_dir / "analyzer_chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        
        # 最终输出文件
        self.output_file = self.metadata_dir / "step1_unified_analysis.json"
    
    def analyze(self, srt_path: Path) -> List[Dict]:
        """
        执行智能内容分析
        
        Args:
            srt_path: SRT字幕文件路径
            
        Returns:
            分析结果列表
        """
        logger.info("开始智能内容分析（优化版：单次LLM调用）...")
        
        # 1. 解析SRT
        try:
            srt_data = self.text_processor.parse_srt(srt_path)
            if not srt_data:
                logger.warning("SRT文件为空或解析失败")
                return []
        except Exception as e:
            logger.error(f"解析SRT文件失败: {e}")
            return []
        
        # 2. 智能分块（按30分钟 + 重叠）
        chunks = self.text_processor.chunk_srt_data(srt_data, interval_minutes=30)
        logger.info(f"SRT已切分为 {len(chunks)} 个块")
        
        # 3. 保存块信息
        chunk_files = self._save_chunks(chunks)
        
        # 4. 逐块处理（每块一次LLM调用）
        all_clips = []
        for i, chunk_file in enumerate(chunk_files):
            logger.info(f"处理块 {i+1}/{len(chunks)}...")
            
            try:
                # 读取块内容
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    chunk_text = f.read()
                
                # 调用LLM（单次）
                clip_batch = self._analyze_chunk(chunk_text, i)
                if clip_batch:
                    all_clips.extend(clip_batch)
                    
            except Exception as e:
                logger.error(f"处理块 {i} 失败: {e}")
                continue
        
        # 5. 后处理
        if all_clips:
            # 按开始时间排序
            all_clips.sort(key=lambda x: self._time_to_seconds(x.get('start_time', '00:00:00,000')))
            
            # 分配固定ID
            for i, clip in enumerate(all_clips):
                clip['id'] = str(i + 1)
            
            # 修复重叠时间
            all_clips = self._fix_overlapping_times(all_clips)
            
            # 评分排序
            all_clips.sort(key=lambda x: x.get('final_score', 0), reverse=True)
        
        # 6. 保存结果
        self._save_results(all_clips)
        
        logger.info(f"智能分析完成，共 {len(all_clips)} 个切片")
        return all_clips
    
    def _analyze_chunk(self, chunk_text: str, chunk_index: int) -> List[Dict]:
        """
        分析单个SRT块
        
        Args:
            chunk_text: SRT块文本
            chunk_index: 块索引
            
        Returns:
            切片列表
        """
        # 准备输入
        input_data = {
            "srt_text": chunk_text
        }
        
        # 调用LLM（单次调用，完成4个任务）
        try:
            response = self.llm_client.call_with_retry(
                UNIFIED_ANALYSIS_PROMPT,
                input_data
            )
            
            if not response:
                logger.warning(f"块 {chunk_index} LLM响应为空")
                return []
            
            # 解析JSON响应
            clips = self.llm_client.parse_json_response(response)
            
            if not isinstance(clips, list):
                logger.warning(f"块 {chunk_index} 响应格式错误")
                return []
            
            # 添加chunk_index用于后续处理
            for clip in clips:
                clip['chunk_index'] = chunk_index
            
            logger.info(f"块 {chunk_index} 分析完成，获得 {len(clips)} 个切片")
            return clips
            
        except Exception as e:
            logger.error(f"块 {chunk_index} LLM调用失败: {e}")
            return []
    
    def _save_chunks(self, chunks: List[Dict]) -> List[Path]:
        """保存SRT块到文件"""
        chunk_files = []
        for chunk in chunks:
            chunk_index = chunk.get('chunk_index', 0)
            file_path = self.chunks_dir / f"chunk_{chunk_index}.txt"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(chunk.get('text', ''))
            
            chunk_files.append(file_path)
        
        return chunk_files
    
    def _fix_overlapping_times(self, clips: List[Dict]) -> List[Dict]:
        """修复重叠的时间区间"""
        if not clips or len(clips) < 2:
            return clips
        
        fixed = []
        for i in range(len(clips) - 1):
            current = clips[i].copy()
            next_clip = clips[i + 1]
            
            current_end = self._time_to_seconds(current.get('end_time', '00:00:00,000'))
            next_start = self._time_to_seconds(next_clip.get('start_time', '00:00:00,000'))
            
            # 如果重叠
            if next_start < current_end:
                mid_point = (current_end + next_start) / 2
                current['end_time'] = self._seconds_to_time(mid_point - 0.1)
                next_clip['start_time'] = self._seconds_to_time(mid_point + 0.1)
                logger.debug(f"修复重叠: {current['outline'][:20]}...")
            
            fixed.append(current)
        
        fixed.append(clips[-1])
        return fixed
    
    def _time_to_seconds(self, time_str: str) -> float:
        """时间字符串转秒数"""
        if not time_str:
            return 0.0
        
        # 处理SRT格式 (00:01:23,456)
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        
        try:
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
            elif len(parts) == 2:
                minutes, seconds = parts
                return float(minutes) * 60 + float(seconds)
        except:
            pass
        
        return 0.0
    
    def _seconds_to_time(self, seconds: float) -> str:
        """秒数转时间字符串"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')
    
    def _save_results(self, clips: List[Dict]):
        """保存分析结果"""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(clips, f, ensure_ascii=False, indent=2)
        logger.info(f"分析结果已保存: {self.output_file}")


def run_unified_analysis(srt_path: Path, metadata_dir: Path = None) -> List[Dict]:
    """
    运行统一内容分析
    
    Args:
        srt_path: SRT字幕文件路径
        metadata_dir: 元数据目录
        
    Returns:
        切片列表
    """
    analyzer = IntelligentAnalyzer(metadata_dir)
    return analyzer.analyze(srt_path)
