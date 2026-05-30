"""
Step 1: 大纲提取 - 从转写文本中提取结构性大纲（优化版）

新增功能：
- 热词提取
- 标志性开头识别
- 热词增强的提示词
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

# 导入依赖
from ..utils.text_processor import TextProcessor
from ..core.shared_config import PROMPT_FILES, METADATA_DIR
from ..core.llm_manager import LLMManager
from ..utils.hotword_extractor import HotwordExtractor, SIGNATURE_PATTERNS
from .topic_postprocess import get_max_topics_per_chunk

logger = logging.getLogger(__name__)

class OutlineExtractor:
    """大纲提取器（优化版 - 借鉴 FunClip）"""

    def __init__(self, metadata_dir: Path = None, prompt_files: Dict = None):
        self.llm_manager = LLMManager()
        self.text_processor = TextProcessor()

        # 【新增】热词提取器
        self.hotword_extractor = HotwordExtractor()
        self.hotwords = []

        # 使用传入的metadata_dir或默认值
        if metadata_dir is None:
            metadata_dir = METADATA_DIR
        self.metadata_dir = metadata_dir

        # 使用传入的prompt_files或默认值
        if prompt_files is None:
            prompt_files = PROMPT_FILES

        # 加载提示词
        with open(prompt_files['outline'], 'r', encoding='utf-8') as f:
            self.outline_prompt = f.read()

        # 创建用于存放中间文本块的目录
        self.chunks_dir = self.metadata_dir / "step1_chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        # 创建用于存放中间SRT块的目录
        self.srt_chunks_dir = self.metadata_dir / "step1_srt_chunks"
        self.srt_chunks_dir.mkdir(parents=True, exist_ok=True)

    def extract_outline(self, srt_path: Path) -> List[Dict]:
        """
        从SRT文件提取视频大纲（优化版）

        新增功能：
        - 热词提取
        - 热词增强的提示词

        Args:
            srt_path: SRT文件路径

        Returns:
            视频大纲列表
        """
        logger.info("开始提取视频大纲（优化版）...")

        # 1. 解析SRT文件
        try:
            srt_data = self.text_processor.parse_srt(srt_path)
            if not srt_data:
                logger.warning("SRT文件为空或解析失败")
                return []
        except Exception as e:
            logger.error(f"解析SRT文件失败: {e}")
            return []

        # 【新增】2. 提取热词
        self.hotwords = self.hotword_extractor.extract_from_srt(srt_data)

        # 【新增】3. 保存热词到中间文件
        self._save_hotwords(self.hotwords)

        # 4. 基于时间智能分块
        chunks = self.text_processor.chunk_srt_data(srt_data, interval_minutes=30)

        # 计算总文本量和块数统计
        total_text = " ".join([chunk['text'] for chunk in chunks])
        estimated_tokens = len(total_text) // 2
        if len(chunks) == 1:
            logger.info(f"文本无需切分，单块处理（约 {estimated_tokens} tokens）")
        else:
            logger.info(f"文本已按智能切分，共{len(chunks)}个块（平均约 {estimated_tokens // len(chunks)} tokens/块）")

        # 5. 保存文本块和SRT块到中间文件
        chunk_files = self._save_chunks_to_files(chunks)
        self._save_srt_chunks(chunks)

        all_outlines = []

        # 6. 逐一处理每个文本块文件
        for i, chunk_file in enumerate(chunk_files):
            logger.info(f"处理第{i+1}/{len(chunks)}个文本块: {chunk_file.name}")
            try:
                # 读取文本块内容
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    chunk_text = f.read()

                # 检查是否有可用的LLM提供商
                if not self.llm_manager.current_provider:
                    logger.warning("没有可用的LLM提供商，跳过大纲提取")
                    break

                # 【新增】获取当前块的相关热词
                chunk_hotwords = self._get_chunk_hotwords(i, self.hotwords, chunks)

                # 【新增】增强提示词
                enhanced_prompt = self._enhance_prompt_with_hotwords(
                    self.outline_prompt,
                    chunk_hotwords
                )

                chunk_input_text = self._enhance_chunk_with_precluster(chunk_text, chunks[i])

                # 为每个块调用LLM
                input_data = {"text": chunk_input_text}
                try:
                    response = self.llm_manager.current_provider.call(enhanced_prompt, input_data)
                    llm_content = response.content if response else None
                except Exception as llm_error:
                    logger.warning(f"LLM调用失败，将使用降级模式: {llm_error}")
                    llm_content = None

                if llm_content:
                    # 解析响应并附加块索引
                    parsed_outlines = self._parse_outline_response(
                        llm_content, i, chunk_hotwords
                    )
                    all_outlines.extend(parsed_outlines)
                else:
                    logger.warning(f"处理第{i+1}个文本块时返回空响应")
            except Exception as e:
                logger.error(f"处理第{i+1}个文本块失败: {e}")
                continue

        # 7. 合并和去重
        final_outlines = self._merge_outlines(all_outlines)

        logger.info(f"大纲提取完成，共{len(final_outlines)}个话题")
        return final_outlines

    def _save_chunks_to_files(self, chunks: List[Dict]) -> List[Path]:
        """将文本块保存为单独的 .txt 文件"""
        chunk_files = []
        for chunk in chunks:
            chunk_index = chunk['chunk_index']
            text_content = chunk['text']
            file_path = self.chunks_dir / f"chunk_{chunk_index}.txt"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
            chunk_files.append(file_path)
        
        logger.info(f"所有文本块已保存到: {self.chunks_dir}")
        return chunk_files

    def _save_srt_chunks(self, chunks: List[Dict]):
        """将SRT数据块保存为单独的 .json 文件"""
        for chunk in chunks:
            chunk_index = chunk['chunk_index']
            srt_entries = chunk['srt_entries']
            file_path = self.srt_chunks_dir / f"chunk_{chunk_index}.json"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(srt_entries, f, ensure_ascii=False, indent=2)
        
        logger.info(f"所有SRT块已保存到: {self.srt_chunks_dir}")

    def _merge_outlines(self, outlines: List[Dict], overlap_threshold: float = 0.6) -> List[Dict]:
        """
        合并和去重大纲，支持跨窗口去重

        Args:
            outlines: 所有大纲列表
            overlap_threshold: 时间重叠阈值，超过则认为重复

        Returns:
            去重后的大纲列表
        """
        if not outlines:
            return []

        for outline in outlines:
            outline['start_seconds'] = self._time_to_seconds(outline.get('start_time', '0'))
            outline['end_seconds'] = self._time_to_seconds(outline.get('end_time', '0'))

        outlines.sort(key=lambda x: x['start_seconds'])

        unique_outlines = []
        for outline in outlines:
            is_duplicate = False
            for existing in unique_outlines:
                if self._outlines_are_similar(outline, existing, overlap_threshold):
                    if outline.get('coverage', 0) > existing.get('coverage', 0):
                        unique_outlines.remove(existing)
                        unique_outlines.append(outline)
                        logger.debug(f"替换重复大纲: {existing['title']} -> {outline['title']}")
                    else:
                        logger.debug(f"跳过重复大纲: {outline['title']}")
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_outlines.append(outline)

        for outline in unique_outlines:
            outline.pop('start_seconds', None)
            outline.pop('end_seconds', None)

        return unique_outlines

    def _outlines_are_similar(
        self,
        outline1: Dict,
        outline2: Dict,
        threshold: float = 0.6
    ) -> bool:
        title1 = outline1.get('title', '').lower()
        title2 = outline2.get('title', '').lower()

        if title1 == title2:
            return True

        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, title1, title2).ratio()
        if similarity >= threshold:
            return True

        start1 = outline1.get('start_seconds', 0)
        end1 = outline1.get('end_seconds', 0)
        start2 = outline2.get('start_seconds', 0)
        end2 = outline2.get('end_seconds', 0)

        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        overlap = max(0, overlap_end - overlap_start)

        shorter_duration = min(end1 - start1, end2 - start2) if (end1 > start1 and end2 > start2) else 0
        if shorter_duration > 0:
            overlap_ratio = overlap / shorter_duration
            if overlap_ratio >= 0.5:
                return True

        # 第四层：时间邻接判断 - 首尾相连且标题部分相似
        # 如果两个outline时间首尾相连（间隔 <= 5秒），且标题相似度 >= 0.3，则判定为相似
        gap = max(start1, start2) - min(end1, end2)
        if 0 <= gap <= 5:
            from difflib import SequenceMatcher
            adjacency_similarity = SequenceMatcher(None, title1, title2).ratio()
            if adjacency_similarity >= 0.3:
                logger.debug(f"时间邻接合并: gap={gap:.1f}s, 标题相似度={adjacency_similarity:.2f}, "
                             f'"{title1}" <-> "{title2}"')
                return True

        return False

    @staticmethod
    def _time_to_seconds(time_str: str) -> float:
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
        return 0.0
    
    def save_outline(self, outlines: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        保存大纲到文件
        """
        if output_path is None:
            output_path = self.metadata_dir / "step1_outline.json"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(outlines, f, ensure_ascii=False, indent=2)
        
        logger.info(f"大纲已保存到: {output_path}")
        return output_path

    def load_outline(self, input_path: Path) -> List[Dict]:
        """
        从文件加载大纲
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # 【新增】热词相关辅助方法

    def _save_hotwords(self, hotwords: List[Dict]):
        """保存热词到元数据目录"""
        hotwords_file = self.metadata_dir / "step1_hotwords.json"
        self.hotword_extractor.save_hotwords(hotwords, hotwords_file)

    def _get_chunk_hotwords(
        self,
        chunk_index: int,
        hotwords: List[Dict],
        chunks: List[Dict]
    ) -> List[str]:
        """获取当前块的相关热词"""
        if not hotwords or not chunks:
            return []

        chunk = chunks[chunk_index]
        chunk_start = self._time_to_seconds(
            chunk.get('start_time', '00:00:00,000')
        )
        chunk_end = self._time_to_seconds(
            chunk.get('end_time', '01:00:00,000')
        )

        chunk_hotwords = []
        for hotword in hotwords:
            for pos in hotword.get('positions', []):
                pos_time = self._time_to_seconds(
                    pos.get('start_time', '00:00:00,000')
                )
                if chunk_start <= pos_time <= chunk_end:
                    chunk_hotwords.append(hotword['word'])
                    break

        return list(set(chunk_hotwords))

    def _enhance_prompt_with_hotwords(
        self,
        prompt: str,
        hotwords: List[str]
    ) -> str:
        """用热词增强提示词 - 借鉴 FunClip 的思路"""
        if not hotwords:
            return prompt

        signature_words = [w for w in hotwords if w in SIGNATURE_PATTERNS]
        other_hotwords = [w for w in hotwords if w not in SIGNATURE_PATTERNS]

        enhancement = f"""

【重要提示 - 借鉴 FunClip】
以下是本视频中的重要关键词，它们很可能是话题的标志性开头：

标志性开头词：
{', '.join(signature_words) if signature_words else '无'}

其他热词：
{', '.join(other_hotwords) if other_hotwords else '无'}

请特别注意：
1. 如果某个话题以标志性开头词开始，请确保将其作为独立话题的起点
2. 话题标题应该尽量包含这些标志性词汇
3. 不要把完整的话题切分成多个部分
4. 标题要具体，不要用"地域文化分析"这种笼统的说法
"""

        return prompt + enhancement

    def _build_chunk_srt_text(self, chunk: Dict) -> str:
        lines = []
        for index, entry in enumerate(chunk.get('srt_entries', []), 1):
            start = entry.get('start_time', '00:00:00,000')
            end = entry.get('end_time', '00:00:01,000')
            lines.extend([
                str(index),
                f"{start} --> {end}",
                entry.get('text', ''),
                '',
            ])
        return '\n'.join(lines)

    def _enhance_chunk_with_precluster(self, chunk_text: str, chunk: Dict) -> str:
        chunk_srt = self._build_chunk_srt_text(chunk)
        if not chunk_srt.strip():
            return chunk_text

        try:
            from backend.pipeline.topic_precluster import TopicPreCluster, load_precluster_config
            from backend.pipeline.topic_postprocess import extract_precluster_report_text

            report = TopicPreCluster(load_precluster_config()).process(chunk_srt)
            if not report.clusters:
                return chunk_text

            report_text = extract_precluster_report_text(report.enhanced_text)
            logger.info(
                "块%s 预聚类完成: clusters=%s, coverage=%.0f%%",
                chunk.get('chunk_index', 0),
                report.stats.get('total_clusters', 0),
                report.stats.get('coverage_ratio', 0) * 100,
            )
            return f"{report_text}\n\n---\n\n{chunk_text}"
        except Exception as exc:
            logger.warning(f"块{chunk.get('chunk_index', 0)} 预聚类失败: {exc}")
            return chunk_text

    def _parse_outline_response(
        self,
        response: str,
        chunk_index: int,
        hotwords: List[str] = None
    ) -> List[Dict]:
        """
        解析大模型的大纲响应（优化版）

        新增：支持热词优化标题
        """
        outlines = []
        lines = response.split('\n')
        current_outline = None

        for line in lines:
            line = line.strip()

            if re.match(r'^\d+\.\s*\*\*', line):
                if current_outline:
                    outlines.append(current_outline)

                topic_name = line.split('**')[1] if '**' in line else line.split('.', 1)[1].strip()

                # 【新增】检查标题是否包含热词，如果没有尝试优化
                topic_name = self._optimize_topic_title(topic_name, hotwords)

                current_outline = {
                    'title': topic_name,
                    'subtopics': [],
                    'chunk_index': chunk_index,
                    'has_signature': any(w in topic_name for w in SIGNATURE_PATTERNS) if hotwords else False
                }

            elif line.startswith('-') and current_outline:
                subtopic = line[1:].strip()
                if subtopic and len(subtopic) <= 200:
                    current_outline['subtopics'].append(subtopic)

        if current_outline:
            outlines.append(current_outline)

        max_topics = get_max_topics_per_chunk()
        if len(outlines) > max_topics:
            from backend.pipeline.topic_postprocess import (
                rank_and_truncate_topics,
                score_outline_quality,
            )
            outlines = rank_and_truncate_topics(
                outlines,
                max_topics,
                score_fn=score_outline_quality,
            )

        return outlines

    def _optimize_topic_title(self, title: str, hotwords: List[str]) -> str:
        """
        优化话题标题 - 如果标题中没有热词，考虑重命名

        借鉴 FunClip 的热词定制化思路
        """
        if not hotwords:
            return title

        # 如果标题中已经包含标志性词，直接返回
        for hotword in hotwords:
            if hotword in title:
                return title

        # 标题中没有热词，看看是否应该添加标志性开头
        for signature in SIGNATURE_PATTERNS:
            if signature in hotwords:
                return f"{signature}：{title}"

        return title

def run_step1_outline(srt_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None, prompt_files: Dict = None) -> List[Dict]:
    """
    运行Step 1: 大纲提取
    """
    if metadata_dir is None:
        metadata_dir = METADATA_DIR
        
    extractor = OutlineExtractor(metadata_dir, prompt_files)
    outlines = extractor.extract_outline(srt_path)
    
    if output_path is None:
        output_path = metadata_dir / "step1_outline.json"
        
    extractor.save_outline(outlines, output_path)
    
    return outlines