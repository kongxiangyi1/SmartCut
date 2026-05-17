"""
Step 1: 大纲提取 - 从转写文本中提取结构性大纲
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

logger = logging.getLogger(__name__)

class OutlineExtractor:
    """大纲提取器（重构版）"""
    
    def __init__(self, metadata_dir: Path = None, prompt_files: Dict = None):
        self.llm_manager = LLMManager()
        self.text_processor = TextProcessor()
        
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
        从SRT文件提取视频大纲
        
        Args:
            srt_path: SRT文件路径
            
        Returns:
            视频大纲列表
        """
        logger.info("开始提取视频大纲...")
        
        # 1. 解析SRT文件
        try:
            srt_data = self.text_processor.parse_srt(srt_path)
            if not srt_data:
                logger.warning("SRT文件为空或解析失败")
                return []
        except Exception as e:
            logger.error(f"解析SRT文件失败: {e}")
            return []
            
        # 2. 基于时间智能分块
        chunks = self.text_processor.chunk_srt_data(srt_data, interval_minutes=30)
        logger.info(f"文本已按~30分钟/块切分，共{len(chunks)}个块")
        
        # 3. 保存文本块和SRT块到中间文件
        chunk_files = self._save_chunks_to_files(chunks)
        self._save_srt_chunks(chunks)
        
        all_outlines = []
        
        # 4. 逐一处理每个文本块文件
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
                
                # 为每个块调用LLM
                input_data = {"text": chunk_text}
                try:
                    response = self.llm_manager.current_provider.call(self.outline_prompt, input_data)
                    llm_content = response.content if response else None
                except Exception as llm_error:
                    logger.warning(f"LLM调用失败，将使用降级模式: {llm_error}")
                    llm_content = None
                
                if llm_content:
                    # 解析响应并附加块索引
                    # 注意：这里的chunk_index直接用i，与文件名和原始chunk对应
                    parsed_outlines = self._parse_outline_response(llm_content, i)
                    all_outlines.extend(parsed_outlines)
                else:
                    logger.warning(f"处理第{i+1}个文本块时返回空响应")
            except Exception as e:
                logger.error(f"处理第{i+1}个文本块失败: {e}")
                continue
        
        # 5. 合并和去重
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

    def _parse_outline_response(self, response: str, chunk_index: int) -> List[Dict]:
        """
        解析大模型的大纲响应 (与之前版本保持一致，无质量检查)
        
        Args:
            response: 大模型响应
            chunk_index: 当前处理的块索引
            
        Returns:
            解析后的大纲结构
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
                current_outline = {
                    'title': topic_name,
                    'subtopics': [],
                    'chunk_index': chunk_index
                }
            
            elif line.startswith('-') and current_outline:
                subtopic = line[1:].strip()
                if subtopic and len(subtopic) <= 200:
                    current_outline['subtopics'].append(subtopic)
        
        if current_outline:
            outlines.append(current_outline)
        
        return outlines
    
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