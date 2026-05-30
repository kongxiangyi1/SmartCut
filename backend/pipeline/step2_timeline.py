"""
Step 2: 时间线提取 - 为大纲中的每个话题定位具体时间区间（优化版-方案A）

新增功能：
- 轻量化说话人识别（基于文本特征，不依赖 ModelScope）
- 双重提示词策略（借鉴 FunClip）
- 说话人信息标注
- 说话人统计
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict

# 导入依赖
from ..utils.text_processor import TextProcessor
from ..core.shared_config import PROMPT_FILES
from ..core.llm_manager import LLMManager
from ..utils.simple_speaker_recognizer import (
    SimpleSpeakerRecognizer,
    get_speaker_for_topic,
    get_speaker_statistics
)

logger = logging.getLogger(__name__)

class TimelineExtractor:
    """从大纲和SRT字幕中提取精确时间线（方案A-轻量化）"""

    def __init__(self, metadata_dir: Path = None, prompt_files: Dict = None, video_path: Path = None):
        self.llm_manager = LLMManager()
        self.text_processor = TextProcessor()
        self.video_path = video_path

        # 使用传入的metadata_dir或默认值
        if metadata_dir is None:
            from ..core.shared_config import METADATA_DIR
            metadata_dir = METADATA_DIR
        self.metadata_dir = metadata_dir

        # 加载提示词
        prompt_files_to_use = prompt_files if prompt_files is not None else PROMPT_FILES
        with open(prompt_files_to_use['timeline'], 'r', encoding='utf-8') as f:
            self.timeline_prompt = f.read()

        # 【方案A新增】加载内容理解提示词（双重提示词第一阶段）
        content_prompt_path = Path(__file__).parent.parent / "prompt" / "content_understanding.txt"
        if content_prompt_path.exists():
            with open(content_prompt_path, 'r', encoding='utf-8') as f:
                self.content_understanding_prompt = f.read()
        else:
            self.content_understanding_prompt = None
            logger.warning("内容理解提示词文件不存在，将使用单阶段提示词")

        # SRT块的目录
        self.srt_chunks_dir = self.metadata_dir / "step1_srt_chunks"
        self.timeline_chunks_dir = self.metadata_dir / "step2_timeline_chunks"
        self.llm_raw_output_dir = self.metadata_dir / "step2_llm_raw_output"

        # 【方案A】使用轻量化说话人识别器
        self.speaker_recognizer = SimpleSpeakerRecognizer(n_clusters=2)
        self.srt_with_speakers = None
        
        # 【新增】初始化关键帧对齐器（懒加载）
        self.keyframe_analyzer = None
        if self.video_path and self.video_path.exists():
            try:
                from ..utils.keyframe_aligner import KeyframeAligner
                self.keyframe_analyzer = KeyframeAligner(
                    self.video_path,
                    cache_dir=self.metadata_dir / "keyframe_cache",
                    lazy_load=True  # 懒加载
                )
                logger.info(f"关键帧对齐器已初始化（懒加载模式）: {self.video_path.name}")
            except Exception as e:
                logger.warning(f"关键帧对齐器初始化失败: {e}")
                self.keyframe_analyzer = None

    def extract_timeline(self, outlines: List[Dict]) -> List[Dict]:
        """
        提取话题时间区间（方案A-优化版）

        新增特性：
        - 双重提示词策略（借鉴 FunClip）
        - 轻量化说话人识别（基于文本特征）
        - 优化的集成顺序
        """
        logger.info("开始提取话题时间区间（方案A-双重提示词+轻量化说话人识别）...")
        
        if not outlines:
            logger.warning("大纲数据为空，无法提取时间线。")
            return []

        if not self.srt_chunks_dir.exists():
            logger.error(f"SRT块目录不存在: {self.srt_chunks_dir}。请先运行Step 1。")
            return []

        # 0. 【方案A前置】先加载所有SRT并做说话人识别
        logger.info("【前置】先进行说话人识别...")
        all_srt_data = self._load_all_srt_data()
        if all_srt_data:
            speaker_cache_path = self.metadata_dir / "step2_speakers.json"
            self.srt_with_speakers = self.speaker_recognizer.recognize_srt_segments(
                all_srt_data,
                cache_path=speaker_cache_path
            )
            logger.info("【前置】说话人识别完成！")

        # 1. 创建本步骤需要的目录
        self.timeline_chunks_dir.mkdir(parents=True, exist_ok=True)
        self.llm_raw_output_dir.mkdir(parents=True, exist_ok=True)

        # 2. 按 chunk_index 对所有大纲进行分组
        outlines_by_chunk = defaultdict(list)
        for outline in outlines:
            chunk_index = outline.get('chunk_index')
            if chunk_index is not None:
                outlines_by_chunk[chunk_index].append(outline)
            else:
                logger.warning(f"  > 话题 '{outline.get('title', '未知')}' 缺少 chunk_index，将被跳过。")

        all_timeline_data = []
        # 3. 遍历每个块，批量处理（方案A：双重提示词）
        for chunk_index, chunk_outlines in outlines_by_chunk.items():
            logger.info(f"处理块 {chunk_index}，其中包含 {len(chunk_outlines)} 个话题...")
            
            # 每次都重新处理，不使用缓存
            chunk_output_path = self.timeline_chunks_dir / f"chunk_{chunk_index}.json"

            try:
                # 首先加载对应的SRT块文件
                srt_chunk_path = self.srt_chunks_dir / f"chunk_{chunk_index}.json"
                if not srt_chunk_path.exists():
                    logger.warning(f"  > 找不到对应的SRT块文件: {srt_chunk_path}，跳过整个块。")
                    continue
                
                with open(srt_chunk_path, 'r', encoding='utf-8') as f:
                    srt_chunk_data = json.load(f)

                if not srt_chunk_data:
                    logger.warning(f"  > SRT块文件为空: {srt_chunk_path}，跳过整个块。")
                    continue

                # 获取时间范围信息
                chunk_start_time = srt_chunk_data[0]['start_time']
                chunk_end_time = srt_chunk_data[-1]['end_time']

                raw_response = ""
                llm_cache_path = self.llm_raw_output_dir / f"chunk_{chunk_index}.txt"
                content_analysis = None

                # 【方案A：双重提示词 - 阶段1】先做内容理解
                if llm_cache_path.exists():
                    logger.info(f"  > 找到块 {chunk_index} 的LLM原始响应缓存，直接读取。")
                    with open(llm_cache_path, 'r', encoding='utf-8') as f:
                        raw_response = f.read()
                else:
                    logger.info(f"  > 未找到LLM缓存，开始调用API...")
                    
                    # 构建用于LLM的SRT文本
                    srt_text_for_prompt = ""
                    for sub in srt_chunk_data:
                        srt_text_for_prompt += f"{sub['index']}\\n{sub['start_time']} --> {sub['end_time']}\\n{sub['text']}\\n\\n"
                    
                    # 【方案A新增：双重提示词 - 阶段1】内容理解
                    if self.content_understanding_prompt:
                        logger.info(f"  > [双重提示词] 阶段1: 内容理解...")
                        content_analysis = self._do_content_understanding(
                            srt_text_for_prompt,
                            chunk_index
                        )
                        if content_analysis:
                            logger.info(f"  > [双重提示词] 内容理解完成！")

                    # 为LLM准备一个"干净"的输入
                    llm_input_outlines = [
                        {"title": o.get("title"), "subtopics": o.get("subtopics")}
                        for o in chunk_outlines
                    ]

                    input_data = {
                        "outline": llm_input_outlines,  # 使用干净的数据
                        "srt_text": srt_text_for_prompt
                    }
                    
                    # 【方案A增强】增强提示词（如果有内容分析）
                    current_prompt = self.timeline_prompt
                    if content_analysis:
                        current_prompt = self._build_enhanced_timeline_prompt(
                            current_prompt,
                            content_analysis
                        )
                    
                    # 调用LLM获取原始响应
                    parsed_items = None
                    max_parse_retries = 2
                    
                    if not self.llm_manager.current_provider:
                        logger.warning(f"  > 块 {chunk_index} 没有可用的LLM提供商，跳过")
                        break
                    
                    for retry_count in range(1, max_parse_retries + 2):
                        try:
                            llm_response = self.llm_manager.current_provider.call(current_prompt, input_data)
                            raw_response = llm_response.content if llm_response else None
                            
                            if not raw_response:
                                logger.warning(f"  > 块 {chunk_index} LLM响应为空，跳过")
                                break
                            
                            # 保存原始响应到缓存
                            cache_file = self.llm_raw_output_dir / f"chunk_{chunk_index}_attempt_{retry_count}.txt"
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                f.write(raw_response)
                            
                            # 解析LLM的原始响应
                            parsed_items = self._parse_and_validate_response(
                                raw_response, 
                                chunk_start_time, 
                                chunk_end_time,
                                chunk_index
                            )
                            
                            if parsed_items:
                                # 保存解析后的结果
                                with open(chunk_output_path, 'w', encoding='utf-8') as f:
                                    json.dump(parsed_items, f, ensure_ascii=False, indent=2)
                                
                                logger.info(f"  > 块 {chunk_index} 成功解析 {len(parsed_items)} 个时间段")
                                break  # 成功解析，跳出重试循环
                            else:
                                if retry_count < max_parse_retries:
                                    logger.warning(f"  > 块 {chunk_index} 解析失败，尝试重试 ({retry_count + 1}/{max_parse_retries + 1})")
                                    # 在重试时强化提示词，强调JSON格式
                                    input_data['additional_instruction'] = "\n\n【重要】输出要求：\n1. 必须以[开始，以]结束\n2. 使用英文双引号，不要使用中文引号\n3. 字符串中的引号必须转义为\\\"\n4. 不要添加任何解释文字或代码块标记\n5. 确保JSON格式完全正确"
                                else:
                                    logger.error(f"  > 块 {chunk_index} 经过 {max_parse_retries + 1} 次尝试仍然解析失败")
                                    # 保存最后一次的原始响应以便调试
                                    self._save_debug_response(raw_response, chunk_index, "final_parse_failure")
                                    
                        except Exception as parse_error:
                            logger.error(f"  > 块 {chunk_index} 第 {retry_count + 1} 次尝试解析过程中发生异常: {parse_error}")
                            if retry_count == max_parse_retries:
                                # 保存原始响应以便调试
                                self._save_debug_response(raw_response if 'raw_response' in locals() else "No response", chunk_index, "parse_exception")
                            continue
                    
                    if not parsed_items:
                         logger.warning(f"  > 块 {chunk_index} 最终解析失败，跳过")
                         continue

            except Exception as e:
                logger.error(f"  > 处理块 {chunk_index} 时出错: {str(e)}")
                continue
        
        # 4. 从所有中间文件中拼接最终结果
        logger.info("所有块处理完毕，开始从中间文件拼接最终结果...")
        all_timeline_data = []
        chunk_files = sorted(self.timeline_chunks_dir.glob("*.json"))
        for chunk_file in chunk_files:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                chunk_data = json.load(f)
                all_timeline_data.extend(chunk_data)

        logger.info(f"成功从 {len(chunk_files)} 个块文件中加载了 {len(all_timeline_data)} 个话题。")
        
        # 最终排序：在返回所有结果前，按开始时间进行全局排序
        if all_timeline_data:
            logger.info("按开始时间对所有话题进行最终排序...")
            try:
                # 使用 text_processor 将时间字符串转换为秒数以便正确排序
                all_timeline_data.sort(key=lambda x: self.text_processor.time_to_seconds(x['start_time']))
                logger.info("排序完成。")
                
                # 为所有片段按时间顺序分配固定的ID
                logger.info("为所有片段按时间顺序分配固定ID...")
                for i, timeline_item in enumerate(all_timeline_data):
                    timeline_item['id'] = str(i + 1)
                logger.info(f"已为 {len(all_timeline_data)} 个片段分配了固定ID（1-{len(all_timeline_data)}）")
                
            except Exception as e:
                logger.error(f"对最终结果排序时出错: {e}。返回未排序的结果。")

        # 5. 修复重叠时间
        if all_timeline_data:
            logger.info("开始修复重叠时间...")
            from backend.pipeline.topic_postprocess import postprocess_timeline
            all_timeline_data = postprocess_timeline(all_timeline_data)
            logger.info("话题后处理完成（重叠修复/跨块合并/时长校验）。")

        # 7. 【新增】验证话题完整性
        if all_timeline_data:
            logger.info("开始验证话题完整性...")
            all_timeline_data = self._validate_topic_completeness(all_timeline_data)
            logger.info("话题完整性验证完成。")

        # 8. 【方案A】添加说话人信息（前置已识别过，这里仅用于填充）
        if all_timeline_data and self.srt_with_speakers:
            logger.info("为话题添加主导说话人信息...")
            for item in all_timeline_data:
                speaker_id = get_speaker_for_topic(item, self.srt_with_speakers)
                if speaker_id:
                    item['speaker_id'] = speaker_id
                    logger.debug(f"  > 话题 '{item.get('outline', '')[:30]}...' -> 说话人: {speaker_id}")

            # 输出说话人统计
            speaker_stats = get_speaker_statistics(all_timeline_data)
            logger.info(f"说话人统计: {speaker_stats}")

        # 9. 【新增】关键帧辅助验证（提供对齐建议但不修改原始边界）
        if all_timeline_data and self.keyframe_analyzer:
            logger.info("使用关键帧信息验证话题边界...")
            all_timeline_data = self._validate_with_keyframes(all_timeline_data)
            logger.info("关键帧边界验证完成。")

        return all_timeline_data
        
    def _parse_and_validate_response(self, response: str, chunk_start: str, chunk_end: str, chunk_index: int) -> List[Dict]:
        """增强的解析LLM的批量响应、验证并调整时间"""
        validated_items = []
        
        # 保存原始响应用于调试
        self._save_debug_response(response, chunk_index, "original_response")
        
        try:
            # 尝试解析JSON
            parsed_response = self._parse_json_response(response)
            
            # 验证JSON结构
            if not self._validate_json_structure(parsed_response):
                logger.error(f"  > 块 {chunk_index} JSON结构验证失败")
                self._save_debug_response(str(parsed_response), chunk_index, "invalid_structure")
                return []
            
            if not isinstance(parsed_response, list):
                logger.warning(f"  > 块 {chunk_index} LLM返回的不是一个列表")
                self._save_debug_response(f"类型: {type(parsed_response)}, 内容: {parsed_response}", chunk_index, "not_list")
                return []
            
            for timeline_item in parsed_response:
                if 'outline' not in timeline_item or 'start_time' not in timeline_item or 'end_time' not in timeline_item:
                    logger.warning(f"  > 从LLM返回的某个JSON对象格式不正确: {timeline_item}")
                    continue
                
                # 将 chunk_index 添加回对象中，以便后续步骤使用
                timeline_item['chunk_index'] = chunk_index
                
                # 验证和调整时间范围
                try:
                    # 验证时间格式
                    if not self._validate_time_format(timeline_item['start_time']):
                        logger.warning(f"  > 话题 '{timeline_item['outline']}' 开始时间格式不正确: {timeline_item['start_time']}")
                        continue
                    
                    if not self._validate_time_format(timeline_item['end_time']):
                        logger.warning(f"  > 话题 '{timeline_item['outline']}' 结束时间格式不正确: {timeline_item['end_time']}")
                        continue
                    
                    start_time = self._convert_time_format(timeline_item['start_time'])
                    end_time = self._convert_time_format(timeline_item['end_time'])
                    
                    start_sec = self.text_processor.time_to_seconds(start_time)
                    end_sec = self.text_processor.time_to_seconds(end_time)
                    chunk_start_sec = self.text_processor.time_to_seconds(chunk_start)
                    chunk_end_sec = self.text_processor.time_to_seconds(chunk_end)
                    
                    # 记录原始时间戳，用于后续合并跨边界话题
                    timeline_item['original_start_time'] = timeline_item['start_time']
                    timeline_item['original_end_time'] = timeline_item['end_time']
                    timeline_item['strict_chunk_start'] = chunk_start
                    timeline_item['strict_chunk_end'] = chunk_end
                    
                    # 【修复】放宽边界限制：不再强制截断到块边界
                    # 如果话题延伸到重叠区域（±5秒内），保留延伸部分
                    if start_sec < chunk_start_sec:
                        # 检查是否在合理的重叠区域内
                        if start_sec >= chunk_start_sec - 5:  # 允许5秒误差
                            logger.info(f"  > 保留话题 '{timeline_item['outline']}' 在重叠区域的开始时间 {start_time}")
                        else:
                            logger.warning(f"  > 调整话题 '{timeline_item['outline']}' 的开始时间从 {start_time} 到 {chunk_start}")
                            timeline_item['start_time'] = chunk_start
                    
                    if end_sec > chunk_end_sec:
                        # 检查是否在合理的重叠区域内
                        if end_sec <= chunk_end_sec + 5:  # 允许5秒误差
                            logger.info(f"  > 保留话题 '{timeline_item['outline']}' 在重叠区域的结束时间 {end_time}")
                        else:
                            logger.warning(f"  > 调整话题 '{timeline_item['outline']}' 的结束时间从 {end_time} 到 {chunk_end}")
                            timeline_item['end_time'] = chunk_end
                    
                    logger.info(f"  > 定位成功: {timeline_item['outline']} ({timeline_item['start_time']} -> {timeline_item['end_time']})")
                    validated_items.append(timeline_item)
                except Exception as e:
                    logger.error(f"  > 验证单个时间戳时出错: {e} - 项目: {timeline_item}")
                    continue
            
            return validated_items

        except Exception as e:
            logger.error(f"  > 块 {chunk_index} 解析LLM响应时出错: {e}")
            # 保存详细的错误信息
            error_info = {
                "error": str(e),
                "error_type": type(e).__name__,
                "response_length": len(response),
                "response_preview": response[:200],
                "chunk_index": chunk_index,
                "chunk_start": chunk_start,
                "chunk_end": chunk_end
            }
            import json
            self._save_debug_response(json.dumps(error_info, indent=2, ensure_ascii=False), chunk_index, "parse_error")
            return []

    def _validate_time_format(self, time_str: str) -> bool:
        """
        验证时间格式是否正确 (HH:MM:SS,mmm)
        """
        pattern = r'^\d{2}:\d{2}:\d{2},\d{3}$'
        return bool(re.match(pattern, time_str))
    
    def _convert_time_format(self, time_str: str) -> str:
        """
        转换时间格式：SRT格式 -> FFmpeg格式
        """
        if not time_str or time_str == "end":
            return time_str
        return time_str.replace(',', '.')

    def _save_debug_response(self, response: str, chunk_index: int, error_type: str) -> None:
        """保存调试响应到文件"""
        try:
            debug_dir = self.metadata_dir / "debug_responses"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"chunk_{chunk_index}_{error_type}.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response)
            logger.info(f"调试响应已保存到: {debug_file}")
        except Exception as e:
            logger.error(f"保存调试响应失败: {e}")
    
    def _parse_json_response(self, response: str) -> Any:
        """解析JSON响应，支持多种格式"""
        import json
        import re
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        
        try:
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        
        items = self._parse_markdown_table(response)
        if items:
            return items
        
        return None
    
    def _parse_markdown_table(self, response: str) -> List[Dict]:
        """从markdown表格中提取时间线数据"""
        lines = response.split('\n')
        results = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('|') is False:
                continue
            if '---' in line or '主题' in line.lower() or '话题' in line.lower() or '时间' in line.lower():
                continue
            
            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) < 2:
                continue
            
            outline = parts[0]
            outline = re.sub(r'\*\*', '', outline)
            outline = re.sub(r'[#*`]', '', outline)
            outline = outline.strip()
            
            time_str = parts[1]
            time_str = re.sub(r'[`*#]', '', time_str)
            
            time_match = re.findall(r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})', time_str)
            if time_match:
                start_time = time_match[0][0].replace('.', ',')
                end_time = time_match[0][1].replace('.', ',')
                
                if outline and start_time and end_time:
                    results.append({
                        "outline": outline,
                        "start_time": start_time,
                        "end_time": end_time
                    })
        
        return results if results else None
    
    def _validate_json_structure(self, parsed_response: Any) -> bool:
        """验证JSON结构"""
        if parsed_response is None:
            return False
        if not isinstance(parsed_response, (list, dict)):
            return False
        return True

    def _fix_overlapping_times(self, timeline_data: List[Dict]) -> List[Dict]:
        from backend.pipeline.topic_postprocess import fix_overlapping_timeline
        return fix_overlapping_timeline(timeline_data)

    def _merge_cross_boundary_topics(self, timeline_data: List[Dict]) -> List[Dict]:
        from backend.pipeline.topic_postprocess import merge_cross_boundary_topics
        return merge_cross_boundary_topics(timeline_data)
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """
        计算两个标题的相似度 - 优化版本，更适合中文
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
            
        Returns:
            相似度分数 (0-1)
        """
        if not title1 or not title2:
            return 0.0
        
        # 完全相同 → 1.0
        if title1 == title2:
            return 1.0
        
        # 包含关系 → 0.85
        if title1 in title2 or title2 in title1:
            return 0.85
        
        # 提取关键词比较
        keywords1 = set(self._extract_keywords(title1))
        keywords2 = set(self._extract_keywords(title2))
        
        if not keywords1 or not keywords2:
            return 0.0
        
        # Jaccard相似度
        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)
        
        if union == 0:
            return 0.0
        
        jaccard = intersection / union
        
        # 长度相似度
        len_ratio = min(len(title1), len(title2)) / max(len(title1), len(title2))
        
        # 字符重叠率（连续相同的字符序列）
        char_overlap = self._calculate_char_overlap(title1, title2)
        
        # 综合评分：Jaccard + 长度 + 字符重叠
        return jaccard * 0.5 + len_ratio * 0.2 + char_overlap * 0.3
    
    def _calculate_char_overlap(self, text1: str, text2: str) -> float:
        """
        计算两个文本的字符重叠率
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            重叠率 (0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        # 计算最长公共子序列的简单版本
        # 检查是否有连续的相同字符序列
        max_common_len = 0
        # 检查长度从min(3, len(text1), len(text2)) 到1
        min_len = min(3, len(text1), len(text2))
        for check_len in range(min_len, 0, -1):
            for i in range(len(text1) - check_len + 1):
                substr = text1[i:i+check_len]
                if substr in text2:
                    max_common_len = check_len
                    break
            if max_common_len > 0:
                break
        
        # 归一化到 0-1
        if max_common_len == 0:
            return 0.0
        
        return min(1.0, max_common_len / 3.0)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        从文本中提取关键词（简单的中文分词改进版）
        
        Args:
            text: 输入文本
            
        Returns:
            关键词列表
        """
        # 简单的关键词提取：移除标点，按常用分隔符拆分
        # 移除标点符号
        text = re.sub(r'[^\w\s]', '', text)
        
        # 常用分隔符（空格、逗号、顿号等）
        separators = [' ', '，', '、', ',', '；', ';', '。', '.', '：', ':']
        words = []
        current_word = ''
        
        for char in text:
            if char in separators:
                if current_word:
                    words.append(current_word)
                    current_word = ''
            else:
                current_word += char
        
        if current_word:
            words.append(current_word)
        
        # 过滤掉太短的词
        stopwords = {'的', '是', '在', '了', '和', '与', '或', '以及', '等', '之', '于', '这', '那', '有', '我', '你', '他', '我们', '你们', '他们'}
        keywords = [w for w in words if len(w) >= 2 and w not in stopwords]
        
        # 如果没有关键词，尝试 n-gram
        if not keywords and len(text) >= 2:
            # 尝试双字切分
            for i in range(len(text) - 1):
                bigram = text[i:i+2]
                keywords.append(bigram)
        
        return keywords
    
    def _validate_topic_completeness(self, timeline_data: List[Dict]) -> List[Dict]:
        """
        【新增】验证话题完整性，检测可能被截断的话题
        
        检测规则：
        1. 检查话题开始时间是否紧邻前一个话题的结束时间（可能被截断）
        2. 检查话题时长是否异常短（可能内容不完整）
        3. 检查话题标题是否过于笼统（可能需要细分）
        
        Args:
            timeline_data: 时间线数据
            
        Returns:
            验证后的话题列表（添加完整性标记）
        """
        if len(timeline_data) < 2:
            return timeline_data
        
        logger.info(f"开始验证 {len(timeline_data)} 个话题的完整性...")
        
        for i, topic in enumerate(timeline_data):
            start_sec = self.text_processor.time_to_seconds(topic.get('start_time', '00:00:00,000'))
            end_sec = self.text_processor.time_to_seconds(topic.get('end_time', '00:00:00,000'))
            duration = end_sec - start_sec
            outline = topic.get('outline', '')
            
            # 检测异常短的话题
            if duration < 30:
                topic['completeness_warning'] = 'short_duration'
                logger.warning(f"  > 话题 '{outline[:30]}...' 时长较短({duration:.1f}秒)，可能内容不完整")
            
            # 检测话题标题是否过于笼统
            generic_titles = [
                '分析', '介绍', '概述', '总结', '讨论', '讲解',
                '内容', '部分', '话题', '问题', '方面'
            ]
            
            outline_lower = outline.lower()
            is_generic = any(g in outline_lower for g in generic_titles) and len(outline) < 10
            
            if is_generic:
                topic['completeness_warning'] = 'generic_title'
                logger.warning(f"  > 话题 '{outline}' 标题过于笼统，可能需要更具体的描述")
            
            # 检测与前一个话题的时间关系
            if i > 0:
                prev_topic = timeline_data[i - 1]
                prev_end_sec = self.text_processor.time_to_seconds(prev_topic.get('end_time', '00:00:00,000'))
                time_gap = start_sec - prev_end_sec
                
                # 如果时间间隔为负或非常小，说明可能被截断
                if time_gap < 0:
                    topic['completeness_warning'] = 'overlapping'
                    logger.warning(f"  > 话题 '{outline[:30]}...' 与前一个话题时间重叠，可能需要合并")
                elif time_gap < 2:
                    topic['completeness_warning'] = 'tight_boundary'
                    logger.info(f"  > 话题 '{outline[:30]}...' 与前一个话题紧密相邻，边界可能需要调整")
        
        return timeline_data

    def _seconds_to_time(self, seconds: float) -> str:
        """将秒数转换为 HH:MM:SS,mmm 格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')

    def save_timeline(self, timeline_data: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        保存时间区间数据
        """
        if output_path is None:
            output_path = self.metadata_dir / "step2_timeline.json"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"时间数据已保存到: {output_path}")
        return output_path

    def load_timeline(self, input_path: Path) -> List[Dict]:
        """
        从文件加载时间数据
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_all_srt_data(self) -> List[Dict]:
        """
        加载所有 SRT 块并合并为一个列表

        Returns:
            合并后的完整 SRT 数据
        """
        if not self.srt_chunks_dir.exists():
            logger.warning("SRT 块目录不存在，无法加载完整 SRT 数据")
            return []

        all_srt_data = []

        # 按顺序加载所有 SRT 块
        chunk_files = sorted(self.srt_chunks_dir.glob("chunk_*.json"))
        logger.info(f"找到 {len(chunk_files)} 个 SRT 块文件")

        for chunk_file in chunk_files:
            try:
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    chunk_data = json.load(f)
                all_srt_data.extend(chunk_data)
                logger.debug(f"加载 SRT 块 {chunk_file.name}，共 {len(chunk_data)} 条")
            except Exception as e:
                logger.warning(f"加载 SRT 块 {chunk_file} 失败: {e}")

        logger.info(f"共加载 {len(all_srt_data)} 条 SRT 数据")
        return all_srt_data

    # ========================================
    # 【方案A新增】双重提示词策略辅助方法
    # ========================================
    def _do_content_understanding(self, srt_text: str, chunk_index: int) -> Optional[Dict]:
        """
        【方案A】双重提示词 - 阶段1: 内容理解

        借鉴 FunClip 的策略，先让 LLM 理解 SRT 的内容结构，
        再进行时间线定位。

        Args:
            srt_text: SRT 文本内容
            chunk_index: 块索引，用于日志和缓存

        Returns:
            内容分析结果 (Dict) 或 None (失败)
        """
        try:
            # 检查是否有内容理解提示词
            if not self.content_understanding_prompt:
                return None

            # 检查是否有 LLM 提供商
            if not self.llm_manager.current_provider:
                logger.warning("  > [双重提示词] 没有可用的LLM提供商，跳过内容理解")
                return None

            # 构建输入数据
            input_data = {"srt_text": srt_text}

            # 调用 LLM
            llm_response = self.llm_manager.current_provider.call(
                self.content_understanding_prompt,
                input_data
            )

            if not llm_response or not llm_response.content:
                logger.warning("  > [双重提示词] LLM响应为空")
                return None

            content_text = llm_response.content.strip()

            # 尝试解析 JSON
            if content_text.startswith('```json'):
                content_text = content_text[7:]
            if content_text.endswith('```'):
                content_text = content_text[:-3]

            content_analysis = json.loads(content_text.strip())

            # 保存内容分析结果到缓存（可选）
            analysis_cache_path = self.metadata_dir / f"step2_content_analysis_{chunk_index}.json"
            with open(analysis_cache_path, 'w', encoding='utf-8') as f:
                json.dump(content_analysis, f, ensure_ascii=False, indent=2)

            return content_analysis

        except json.JSONDecodeError as e:
            logger.warning(f"  > [双重提示词] JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.warning(f"  > [双重提示词] 内容理解阶段失败: {e}")
            return None

    def _build_enhanced_timeline_prompt(self, original_prompt: str, content_analysis: Dict) -> str:
        """
        【方案A】用内容分析结果增强时间线提示词

        借鉴 FunClip 的策略，将阶段1的分析结果注入到阶段2的提示词中。

        Args:
            original_prompt: 原始的时间线提示词
            content_analysis: 阶段1的内容分析结果

        Returns:
            增强后的提示词
        """
        try:
            # 构建增强部分
            enhancement = "\n\n【重要补充】基于内容分析的洞察：\n"

            # 1. 添加主要话题的标志性开头
            if 'main_topics' in content_analysis and isinstance(content_analysis['main_topics'], list):
                enhancement += "话题的标志性开头：\n"
                for i, topic in enumerate(content_analysis['main_topics'][:3]):  # 只取前3个
                    title = topic.get('topic_title', '')
                    signature = topic.get('signature_opening', '')
                    if signature:
                        enhancement += f"  - 话题 '{title}': 标志性开头是 '{signature}'\n"

            # 2. 添加整体亮点
            if 'key_insights' in content_analysis:
                enhancement += f"\n视频亮点总结：{content_analysis['key_insights']}\n"

            enhancement += """
请特别注意：
- 如果话题有标志性开头，必须从标志性开头的时间点开始截取
- 保持话题的完整性，不要截断重要内容
"""

            # 返回增强后的提示词
            return original_prompt + enhancement

        except Exception as e:
            logger.warning(f"  > [双重提示词] 增强提示词构建失败: {e}")
            return original_prompt
    
    def _validate_with_keyframes(self, timeline_data: List[Dict]) -> List[Dict]:
        """
        【新增】使用关键帧信息验证和微调时间线
        
        此方法仅提供对齐建议，不修改原始边界。
        实际的对齐在 Step6 视频生成时执行。
        
        Args:
            timeline_data: 时间线数据
            
        Returns:
            添加了关键帧分析信息的原始时间线
        """
        try:
            if not self.keyframe_analyzer:
                return timeline_data
            
            self.keyframe_analyzer.ensure_initialized()
            
            for topic in timeline_data:
                start_sec = self.text_processor.time_to_seconds(topic.get('start_time', '00:00:00,000'))
                end_sec = self.text_processor.time_to_seconds(topic.get('end_time', '00:00:00,000'))
                
                # 执行关键帧对齐（使用balanced策略）
                aligned = self.keyframe_analyzer.align_boundary(
                    start_sec, end_sec, 
                    strategy="balanced"
                )
                
                # 添加建议信息（不修改原始边界）
                topic['keyframe_analysis_available'] = True
                topic['keyframe_suggestion'] = {
                    'suggested_start': self._seconds_to_time(aligned.aligned_start),
                    'suggested_end': self._seconds_to_time(aligned.aligned_end),
                    'start_expansion': round(aligned.start_expansion, 3),
                    'end_expansion': round(aligned.end_expansion, 3),
                    'alignment_strategy': 'balanced'
                }
                
                # 如果扩展量较大，添加警告
                if aligned.start_expansion > 2.5 or aligned.end_expansion > 2.5:
                    topic['keyframe_warning'] = 'large_expansion'
                    logger.debug(
                        f"  > 话题 '{topic.get('outline', '')[:30]}...' "
                        f"关键帧对齐扩展较大: +{aligned.start_expansion:.3f}s / +{aligned.end_expansion:.3f}s"
                    )
            
            # 输出关键帧统计信息
            stats = self.keyframe_analyzer.get_keyframe_statistics()
            logger.info(
                f"关键帧统计: {stats['count']} 个I帧, "
                f"平均间隔 {stats.get('avg_interval', 0):.2f}s, "
                f"视频时长 {stats.get('duration', 0):.2f}s"
            )
            
            return timeline_data
            
        except Exception as e:
            logger.warning(f"关键帧验证失败: {e}")
            return timeline_data

def run_step2_timeline(outline_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None, prompt_files: Dict = None, video_path: Path = None) -> List[Dict]:
    """
    运行Step 2: 时间点提取
    
    Args:
        outline_path: 大纲文件路径
        metadata_dir: 元数据目录
        output_path: 输出文件路径
        prompt_files: 提示词文件字典
        video_path: 视频文件路径（用于关键帧对齐）
    
    Returns:
        时间线数据列表
    """
    if metadata_dir is None:
        from ..core.shared_config import METADATA_DIR
        metadata_dir = METADATA_DIR
        
    extractor = TimelineExtractor(metadata_dir, prompt_files, video_path)
    
    # 加载大纲
    with open(outline_path, 'r', encoding='utf-8') as f:
        outlines = json.load(f)
        
    timeline_data = extractor.extract_timeline(outlines)
    
    # 保存结果
    if output_path is None:
        output_path = metadata_dir / "step2_timeline.json"
        
    extractor.save_timeline(timeline_data, output_path)
    
    return timeline_data