"""
文本处理工具
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

# 修复导入问题
try:
    from ..core.shared_config import CHUNK_SIZE
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from core.shared_config import CHUNK_SIZE

import pysrt

logger = logging.getLogger(__name__)

class TextProcessor:
    """文本处理工具类"""
    
    @staticmethod
    def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap_minutes: int = 0) -> List[str]:
        """
        将长文本按指定大小分块（支持滑动窗口重叠）

        Args:
            text: 输入文本
            chunk_size: 分块大小（字符数）
            overlap_minutes: 重叠时长（分钟），用于边界话题处理

        Returns:
            文本块列表
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # 按段落分割
        paragraphs = text.split('\n')
        
        for paragraph in paragraphs:
            # 如果当前块加上新段落不超过限制，则添加
            if len(current_chunk) + len(paragraph) + 1 <= chunk_size:
                current_chunk += paragraph + '\n'
            else:
                # 如果当前块不为空，保存它
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                
                # 如果单个段落就超过限制，需要进一步分割
                if len(paragraph) > chunk_size:
                    # 按句子分割
                    sentences = re.split(r'[。！？]', paragraph)
                    temp_chunk = ""
                    for sentence in sentences:
                        if len(temp_chunk) + len(sentence) + 1 <= chunk_size:
                            temp_chunk += sentence + "。"
                        else:
                            if temp_chunk:
                                chunks.append(temp_chunk.strip())
                            temp_chunk = sentence + "。"
                    current_chunk = temp_chunk
                else:
                    current_chunk = paragraph + '\n'
        
        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def chunk_srt_data(self, srt_data: List[Dict], interval_minutes: int = 30, pause_threshold_ms: int = 1000, overlap_minutes: int = 2, max_tokens_per_chunk: int = 4000) -> List[Dict]:
        """
        根据停顿时间和语义相似性，将SRT数据切分为智能的、主题连贯的块。
        支持Token感知切分和多粒度重叠策略。
        包含容错回退机制：如果智能切分失败，会回退到简单切分。
        
        Args:
            srt_data: SRT数据列表
            interval_minutes: 每个块的目标时间长度（分钟）
            pause_threshold_ms: 识别为停顿的最小毫秒数
            overlap_minutes: 块间重叠时长（分钟），为每个块提供相邻块的上下文
            max_tokens_per_chunk: 每个块的最大token数（用于LLM上下文窗口限制）
            
        Returns:
            结构化的块列表，其中的 srt_entries 不包含临时处理字段。
            块可包含 overlap_prefix（前一个块末尾的重叠数据）和
            overlap_suffix（后一个块开头的重叠数据）作为额外上下文。
        """
        try:
            return self._chunk_srt_data_smart(srt_data, interval_minutes, 
                                            pause_threshold_ms, overlap_minutes, max_tokens_per_chunk)
        except Exception as e:
            logger.error(f"智能切分失败，回退到简单切分: {e}")
            logger.info("使用简单切分方案")
            return self._chunk_srt_data_simple(srt_data, interval_minutes, pause_threshold_ms, overlap_minutes)
    
    def _chunk_srt_data_smart(self, srt_data: List[Dict], interval_minutes: int, pause_threshold_ms: int, overlap_minutes: int, max_tokens_per_chunk: int) -> List[Dict]:
        if not srt_data:
            return []

        # 1. 智能停顿分析 - 识别所有可能的切分点
        pause_points = self._analyze_pause_points(srt_data, pause_threshold_ms)
        
        # 2. Token 感知动态调整 - 根据 LLM 上下文窗口限制
        total_text = " ".join([sub['text'] for sub in srt_data])
        estimated_tokens = len(total_text) // 2  # 粗略估计：中文每字约 2 tokens
        
        # 根据 token 数量动态调整块数量
        if estimated_tokens > max_tokens_per_chunk * 3:
            # 超长文本：使用更小的块
            interval_minutes = min(interval_minutes, 15)
            logger.info(f"超长文本检测（~{estimated_tokens} tokens），调整为 {interval_minutes} 分钟/块")
        elif estimated_tokens < max_tokens_per_chunk:
            # 短文本：可以合并为一个块
            if len(srt_data) < 100:  # 少于100条字幕
                logger.info(f"短文本检测（~{estimated_tokens} tokens），尝试合并为单个块")
                interval_minutes = 999  # 尽量不切分
        
        # 3. 语义相关性分析 - 在停顿点基础上，检查前后内容的语义连贯性
        semantic_boundaries = self._analyze_semantic_boundaries(srt_data, pause_points)
        
        # 创建一个带有秒数的新列表
        srt_data_with_seconds = []
        for sub in srt_data:
            entry = sub.copy()
            entry['start_seconds'] = self.time_to_seconds(sub['start_time'])
            entry['end_seconds'] = self.time_to_seconds(sub['end_time'])
            srt_data_with_seconds.append(entry)

        interval_seconds = interval_minutes * 60
        chunks = []
        current_chunk_start_index = 0
        chunk_index = 0
        
        last_cut_time = 0
        
        while current_chunk_start_index < len(srt_data_with_seconds):
            target_cut_time = last_cut_time + interval_seconds
            
            # 寻找接近目标时间的最佳切分点
            best_cut_index = -1
            
            # 查找从当前块开始后的 90% 到 110% 目标时间内的一个停顿
            search_start_index = current_chunk_start_index
            while search_start_index < len(srt_data_with_seconds) and srt_data_with_seconds[search_start_index]['start_seconds'] < target_cut_time * 0.9:
                search_start_index += 1

            # 从搜索起点开始寻找超过阈值的停顿，并优先选择语义边界
            for i in range(search_start_index, len(srt_data_with_seconds) - 1):
                current_sub = srt_data_with_seconds[i]
                next_sub = srt_data_with_seconds[i+1]
                
                # 如果我们已经超出了目标时间的110%，就停止搜索
                if current_sub['start_seconds'] > target_cut_time * 1.1:
                    break
                
                # 计算两个字幕条目之间的停顿时间
                pause = next_sub['start_seconds'] - current_sub['end_seconds']
                if pause * 1000 >= pause_threshold_ms:
                    # 检查是否是语义边界
                    is_semantic_boundary = any(
                        abs(i - bp['index']) <= 2 for bp in semantic_boundaries
                    )
                    
                    if is_semantic_boundary or best_cut_index == -1:
                        best_cut_index = i + 1  # 在停顿后切分
                        if is_semantic_boundary:
                            logger.debug(f"在语义边界处切分: {current_sub['start_seconds']:.1f}s")
                            break
                    elif best_cut_index == -1:
                        best_cut_index = i + 1
            
            # 如果没有找到合适的停顿点，就在目标时间点强制切分
            if best_cut_index == -1:
                # 寻找最接近目标时间的字幕条目
                i = current_chunk_start_index
                while i < len(srt_data_with_seconds) and srt_data_with_seconds[i]['start_seconds'] < target_cut_time:
                    i += 1
                best_cut_index = i if i < len(srt_data_with_seconds) else len(srt_data_with_seconds)

            # 如果切分点无效或过小，则将所有剩余部分作为一个块
            if best_cut_index <= current_chunk_start_index:
                 best_cut_index = len(srt_data_with_seconds)

            # 创建块
            chunk_entries_with_seconds = srt_data_with_seconds[current_chunk_start_index:best_cut_index]
            if not chunk_entries_with_seconds:
                break

            # 移除临时字段，得到干净的srt_entries
            chunk_entries = []
            for entry in chunk_entries_with_seconds:
                clean_entry = entry.copy()
                del clean_entry['start_seconds']
                del clean_entry['end_seconds']
                chunk_entries.append(clean_entry)
            
            start_time = chunk_entries[0]['start_time']
            end_time = chunk_entries[-1]['end_time']
            text = " ".join([entry['text'] for entry in chunk_entries])
            
            chunks.append({
                "chunk_index": chunk_index,
                "text": text,
                "start_time": start_time,
                "end_time": end_time,
                "srt_entries": chunk_entries
            })
            
            chunk_index += 1
            last_cut_time = chunk_entries_with_seconds[-1]['end_seconds']
            current_chunk_start_index = best_cut_index

        # 块间重叠：为每个块添加相邻块的上下文信息，防止话题在边界处被切断
        overlap_seconds = overlap_minutes * 60
        if overlap_seconds > 0 and len(chunks) > 1:
            for i, chunk in enumerate(chunks):
                chunk_start_sec = self.time_to_seconds(chunk['start_time'])
                chunk_end_sec = self.time_to_seconds(chunk['end_time'])

                # 为非首块添加 overlap_prefix（前一个块末尾的重叠数据）
                if i > 0:
                    prefix_start = max(0, chunk_start_sec - overlap_seconds)
                    prefix_entries = self._get_srt_in_range(srt_data_with_seconds, prefix_start, chunk_start_sec)
                    chunk['overlap_prefix'] = prefix_entries

                # 为非末块添加 overlap_suffix（后一个块开头的重叠数据）
                if i < len(chunks) - 1:
                    suffix_end = chunk_end_sec + overlap_seconds
                    suffix_entries = self._get_srt_in_range(srt_data_with_seconds, chunk_end_sec, suffix_end)
                    chunk['overlap_suffix'] = suffix_entries

        return chunks

    @staticmethod
    def parse_srt(srt_path: Path) -> List[Dict]:
        """
        解析SRT字幕文件
        
        Args:
            srt_path: SRT文件路径
            
        Returns:
            字幕数据列表，每个元素包含时间戳和文本
        """
        if not srt_path.exists():
            logger.error(f"SRT文件不存在: {srt_path}")
            return []
        
        if srt_path.stat().st_size == 0:
            logger.warning(f"SRT文件为空: {srt_path}")
            return []

        try:
            try:
                subs = pysrt.open(str(srt_path), encoding='utf-8')
            except UnicodeDecodeError:
                logger.warning("UTF-8解码失败，尝试使用 utf-8-sig...")
                subs = pysrt.open(str(srt_path), encoding='utf-8-sig')

            subtitles = []
            for sub in subs:
                subtitles.append({
                    'start_time': str(sub.start),
                    'end_time': str(sub.end),
                    'text': sub.text.strip(),
                    'index': sub.index
                })

            if not subtitles:
                logger.warning(f"成功打开SRT文件但未能解析出任何字幕内容: {srt_path}")
            
            return subtitles
        except Exception as e:
            logger.error(f"使用pysrt解析SRT文件'{srt_path}'时发生未知错误: {e}", exc_info=True)
            return []
    
    @staticmethod
    def extract_text_by_time_range(text: str, srt_data: List[Dict], 
                                  start_time: str, end_time: str) -> str:
        """
        根据时间范围从文本中提取对应内容
        
        Args:
            text: 完整文本
            srt_data: SRT字幕数据
            start_time: 开始时间 (格式: "00:01:25")
            end_time: 结束时间 (格式: "00:02:53")
            
        Returns:
            对应时间范围的文本内容
        """
        # 找到时间范围内的字幕
        target_subtitles = []
        
        for sub in srt_data:
            sub_start = sub['start_time']
            sub_end = sub['end_time']
            
            # 检查时间重叠
            if (sub_start <= end_time and sub_end >= start_time):
                target_subtitles.append(sub)
        
        # 提取对应的文本
        extracted_text = ""
        for sub in target_subtitles:
            extracted_text += sub['text'] + " "
        
        return extracted_text.strip()
    
    @staticmethod
    def _get_srt_in_range(srt_data_with_seconds: List[Dict], start_seconds: float, end_seconds: float) -> List[Dict]:
        """
        获取指定时间范围内的字幕数据（不含临时秒数字段）

        Args:
            srt_data_with_seconds: 带有 start_seconds/end_seconds 字段的字幕数据
            start_seconds: 起始时间（秒）
            end_seconds: 结束时间（秒）

        Returns:
            该时间范围内的字幕条目列表（已移除临时字段）
        """
        result = []
        for entry in srt_data_with_seconds:
            if entry['start_seconds'] >= end_seconds:
                break
            if entry['end_seconds'] > start_seconds and entry['start_seconds'] < end_seconds:
                clean = {k: v for k, v in entry.items() if k not in ('start_seconds', 'end_seconds')}
                result.append(clean)
        return result

    @staticmethod
    def time_to_seconds(time_str: str) -> float:
        """
        将SRT时间字符串（HH:MM:SS,mmm）转换为秒数
        
        Args:
            time_str: 时间字符串
            
        Returns:
            秒数
        """
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        
        if len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            s_parts = parts[2].split('.')
            s = int(s_parts[0])
            ms = int(s_parts[1]) if len(s_parts) > 1 else 0
            return h * 3600 + m * 60 + s + ms / 1000.0
        
        raise ValueError(f"无效的时间格式: {time_str}")
    
    @staticmethod
    def seconds_to_time(seconds: float) -> str:
        """
        将秒数转换为时间字符串
        
        Args:
            seconds: 秒数
            
        Returns:
            时间字符串 (格式: "00:01:25")
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _analyze_pause_points(self, srt_data: List[Dict], pause_threshold_ms: int) -> List[Dict]:
        """
        分析所有可能的停顿点，识别自然的切分边界
        
        Args:
            srt_data: SRT数据列表
            pause_threshold_ms: 停顿阈值（毫秒）
            
        Returns:
            停顿点列表，每个包含位置、时长和上下文
        """
        pause_points = []
        
        for i in range(len(srt_data) - 1):
            current = srt_data[i]
            next_sub = srt_data[i + 1]
            
            # 计算停顿时长
            try:
                current_end = self.time_to_seconds(current['end_time'])
                next_start = self.time_to_seconds(next_sub['start_time'])
                pause_duration = next_start - current_end
                
                if pause_duration * 1000 >= pause_threshold_ms:
                    pause_points.append({
                        'index': i,
                        'start_time': current['end_time'],
                        'end_time': next_sub['start_time'],
                        'duration': pause_duration,
                        'text_before': current['text'][-50:] if current['text'] else '',  # 停顿前50字
                        'text_after': next_sub['text'][:50] if next_sub['text'] else ''     # 停顿后50字
                    })
            except Exception as e:
                logger.warning(f"计算停顿时长失败: {e}")
                continue
        
        return pause_points
    
    def _analyze_semantic_boundaries(self, srt_data: List[Dict], pause_points: List[Dict]) -> List[Dict]:
        """
        分析语义边界 - 识别主题切换的自然边界
        
        基于启发式规则：
        1. 较长的停顿（>5秒）通常表示主题切换
        2. 停顿前后文本相似度低也可能表示主题切换
        
        Args:
            srt_data: SRT数据列表
            pause_points: 停顿点列表
            
        Returns:
            语义边界点列表
        """
        semantic_boundaries = []
        
        for pause in pause_points:
            is_boundary = False
            reason = ""
            
            # 策略1：超长停顿（>5秒）= 高置信度边界
            if pause['duration'] > 5:
                is_boundary = True
                reason = f"长停顿{pause['duration']:.1f}秒"
                logger.debug(f"发现语义边界（{reason}）")
            
            # 策略2：中等停顿（2-5秒）+ 文本相似度低 = 可能的边界
            elif pause['duration'] > 2:
                text_before = pause['text_before']
                text_after = pause['text_after']
                
                # 计算多级相似度
                similarity = self._calculate_semantic_similarity(text_before, text_after)
                
                # 如果相似度<40%，认为是语义边界
                if similarity < 0.4:
                    is_boundary = True
                    reason = f"相似度{similarity:.2f}"
                    logger.debug(f"发现语义边界（{reason}）")
            
            if is_boundary:
                pause['boundary_reason'] = reason
                semantic_boundaries.append(pause)
        
        return semantic_boundaries
    
    @staticmethod
    def _calculate_semantic_similarity(text1: str, text2: str) -> float:
        """
        改进的语义相似度计算（P0级别改进）
        
        多级策略：
        1. 关键词重叠（40%）
        2. 字符相似度（30%）
        3. 长度差异惩罚（30%）
        
        Args:
            text1: 第一段文本
            text2: 第二段文本
            
        Returns:
            相似度分数（0-1）
        """
        if not text1 or not text2:
            return 0.0
        
        score = 0.0
        
        # 1. 关键词重叠（基础分，权重40%）
        keywords1 = set(TextProcessor._extract_keywords(text1))
        keywords2 = set(TextProcessor._extract_keywords(text2))
        
        if keywords1 and keywords2:
            overlap = len(keywords1 & keywords2) / len(keywords1 | keywords2)
            score += overlap * 0.4
        else:
            score += 0.2  # 如果没有关键词，给基础分
        
        # 2. 字符相似度（权重30%）
        from difflib import SequenceMatcher
        char_sim = SequenceMatcher(None, text1, text2).ratio()
        score += char_sim * 0.3
        
        # 3. 长度差异惩罚（权重30%）
        len1, len2 = len(text1), len(text2)
        min_len = min(len1, len2)
        max_len = max(len1, len2)
        
        if max_len > 0:
            len_ratio = min_len / max_len
            score += len_ratio * 0.3
        
        return score
    
    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """
        改进的关键词提取（P0级别改进）
        
        特点：
        1. 使用简单但有效的中文分词策略
        2. 过滤停用词
        3. 避免重复关键词
        
        Args:
            text: 输入文本
            
        Returns:
            关键词列表
        """
        # 移除标点符号
        import re
        text = re.sub(r'[，。！？、：；""''（）【】《》,.!?]', '', text)
        
        # 中文停用词表（常见高频词）
        stop_words = {
            "的", "了", "是", "在", "有", "和", "就", "都", "而", "及", "与", 
            "着", "或", "一个", "没有", "我们", "你们", "他们", "这个", "那个",
            "可以", "这个", "然后", "所以", "因为", "但是", "然后", "就是",
            "那么", "这样", "那样", "一些", "很多", "非常", "比较", "更加",
            "还是", "还是", "还是", "还是", "还是", "还是", "还是", "还是",
            "不过", "只是", "只是", "只是", "只是", "只是", "只是", "只是",
            "其实", "其实", "其实", "其实", "其实", "其实", "其实", "其实"
        }
        
        # 简单中文分词策略
        words = []
        
        # 策略1：按常见分隔符切分（空格、逗号）
        segments = re.split(r'[\s,，]', text)
        
        for seg in segments:
            seg = seg.strip()
            if len(seg) < 2:
                continue
                
            # 策略2：对于长段文本，尝试多种切分方式
            if len(seg) > 6:
                # 尝试按2字、3字切分
                for i in range(len(seg) - 1):
                    if i + 2 <= len(seg):
                        words.append(seg[i:i+2])
                    if i + 3 <= len(seg):
                        words.append(seg[i:i+3])
            else:
                # 短段直接保留
                words.append(seg)
        
        # 策略3：过滤停用词和短词
        keywords = []
        seen = set()
        for word in words:
            if (len(word) >= 2 and 
                word not in stop_words and 
                word not in seen):
                keywords.append(word)
                seen.add(word)
        
        # 最多返回20个关键词，避免过多噪音
        return keywords[:20] 
    
    def _chunk_srt_data_simple(self, srt_data: List[Dict], interval_minutes: int, pause_threshold_ms: int, overlap_minutes: int) -> List[Dict]:
        """
        简单的备用切分方法（P0级别改进）
        
        不依赖复杂的语义分析，只按时间和停顿切分。
        用于智能切分失败时的回退方案。
        
        Args:
            srt_data: SRT数据列表
            interval_minutes: 每个块的目标时间长度（分钟）
            pause_threshold_ms: 识别为停顿的最小毫秒数
            overlap_minutes: 块间重叠时长（分钟）
            
        Returns:
            结构化的块列表
        """
        logger.info("使用简单切分方案")
        
        if not srt_data:
            return []
        
        # 创建带有秒数的新列表
        srt_data_with_seconds = []
        for sub in srt_data:
            entry = sub.copy()
            entry['start_seconds'] = self.time_to_seconds(sub['start_time'])
            entry['end_seconds'] = self.time_to_seconds(sub['end_time'])
            srt_data_with_seconds.append(entry)
        
        interval_seconds = interval_minutes * 60
        chunks = []
        current_chunk_start_index = 0
        chunk_index = 0
        
        last_cut_time = 0
        
        while current_chunk_start_index < len(srt_data_with_seconds):
            target_cut_time = last_cut_time + interval_seconds
            
            # 寻找接近目标时间的最佳切分点
            best_cut_index = -1
            
            # 查找从当前块开始后的 90% 到 110% 目标时间内的一个停顿
            search_start_index = current_chunk_start_index
            while search_start_index < len(srt_data_with_seconds) and srt_data_with_seconds[search_start_index]['start_seconds'] < target_cut_time * 0.9:
                search_start_index += 1
            
            # 从搜索起点开始寻找超过阈值的停顿
            for i in range(search_start_index, len(srt_data_with_seconds) - 1):
                current_sub = srt_data_with_seconds[i]
                next_sub = srt_data_with_seconds[i + 1]
                
                # 如果我们已经超出了目标时间的110%，就停止搜索
                if current_sub['start_seconds'] > target_cut_time * 1.1:
                    break
                
                # 计算两个字幕条目之间的停顿时间
                pause = next_sub['start_seconds'] - current_sub['end_seconds']
                if pause * 1000 >= pause_threshold_ms:
                    best_cut_index = i + 1  # 在停顿后切分
                    break
            
            # 如果没有找到合适的停顿点，就在目标时间点强制切分
            if best_cut_index == -1:
                # 寻找最接近目标时间的字幕条目
                i = current_chunk_start_index
                while i < len(srt_data_with_seconds) and srt_data_with_seconds[i]['start_seconds'] < target_cut_time:
                    i += 1
                best_cut_index = i if i < len(srt_data_with_seconds) else len(srt_data_with_seconds)
            
            # 如果切分点无效或过小，则将所有剩余部分作为一个块
            if best_cut_index <= current_chunk_start_index:
                best_cut_index = len(srt_data_with_seconds)
            
            # 创建块
            chunk_entries_with_seconds = srt_data_with_seconds[current_chunk_start_index:best_cut_index]
            if not chunk_entries_with_seconds:
                break
            
            # 移除临时字段，得到干净的srt_entries
            chunk_entries = []
            for entry in chunk_entries_with_seconds:
                clean_entry = entry.copy()
                del clean_entry['start_seconds']
                del clean_entry['end_seconds']
                chunk_entries.append(clean_entry)
            
            start_time = chunk_entries[0]['start_time']
            end_time = chunk_entries[-1]['end_time']
            text = " ".join([entry['text'] for entry in chunk_entries])
            
            chunks.append({
                "chunk_index": chunk_index,
                "text": text,
                "start_time": start_time,
                "end_time": end_time,
                "srt_entries": chunk_entries
            })
            
            chunk_index += 1
            last_cut_time = chunk_entries_with_seconds[-1]['end_seconds']
            current_chunk_start_index = best_cut_index
        
        # 块间重叠：为每个块添加相邻块的上下文信息，防止话题在边界处被切断
        overlap_seconds = overlap_minutes * 60
        if overlap_seconds > 0 and len(chunks) > 1:
            for i, chunk in enumerate(chunks):
                chunk_start_sec = self.time_to_seconds(chunk['start_time'])
                chunk_end_sec = self.time_to_seconds(chunk['end_time'])
                
                # 为非首块添加 overlap_prefix（前一个块末尾的重叠数据）
                if i > 0:
                    prefix_start = max(0, chunk_start_sec - overlap_seconds)
                    prefix_entries = self._get_srt_in_range(srt_data_with_seconds, prefix_start, chunk_start_sec)
                    chunk['overlap_prefix'] = prefix_entries
                
                # 为非末块添加 overlap_suffix（后一个块开头的重叠数据）
                if i < len(chunks) - 1:
                    suffix_end = chunk_end_sec + overlap_seconds
                    suffix_entries = self._get_srt_in_range(srt_data_with_seconds, chunk_end_sec, suffix_end)
                    chunk['overlap_suffix'] = suffix_entries
        
        logger.info(f"简单切分完成，共{len(chunks)}个块")
        return chunks 