"""
基于FunClip风格的单步LLM处理方案
"""
import logging
import re
from pathlib import Path
from typing import List, Dict, Any
import json
from backend.pipeline.step6_video import VideoGenerator

logger = logging.getLogger(__name__)

# 第一阶段Prompt：仅识别片段边界，不生成标题
FUNCLIP_CLIP_ONLY_PROMPT = """你是一个视频srt字幕分析剪辑器，输入视频的srt字幕，
分析其中的精彩且尽可能连续的片段并裁剪出来，输出四条以内的片段，
将片段中在时间上连续的多个句子及它们的时间戳合并为一条，
注意确保文字与时间戳的正确匹配。

同时为每个片段添加：
- 评分 (0.0-1.0)
- 推荐理由
- 话题概述（用一句话概括该片段的主要内容）

注意：请勿生成标题，后续会为每个片段单独生成标题。

最终JSON格式输出示例：
[
  {
    "id": "1",
    "outline": "话题概述",
    "start": "00:00:00,500",
    "end": "00:05:30,123",
    "final_score": 0.85,
    "recommend_reason": "推荐理由"
  }
]
"""

# 第二阶段Prompt：为每个片段独立生成标题（仅基于该片段自己的字幕文本）
FUNCLIP_TITLE_PROMPT = """你是一个短视频标题策划专家。下面是一段视频切片自己的字幕文本，请为这段内容生成1个吸引人的标题。

## 核心原则
1. **忠于原文**: 标题必须严格基于下方提供的字幕文本内容，严禁无中生有。
2. **拒绝夸张**: 禁止使用"震惊"、"惊呆了"、"看哭了"、"千万别"等过度营销词汇。
3. **突出亮点**: 标题需精准捕捉片段最核心的观点、最激烈的情绪或最有价值的信息。
4. **精炼有力**: 标题必须简洁、有冲击力，能迅速抓住用户眼球。

## 片段信息
话题：{outline}
推荐理由：{recommend_reason}

## 该片段的字幕文本（仅基于此文本生成标题）
{clip_srt_text}

## 输出
只输出标题文本，不要添加任何其他内容。
"""

# ============================================================
# 合并方案 Prompt：单次LLM调用完成话题切分 + 多段合并 + 标题生成
# ============================================================
FUNCLIP_MERGED_PROMPT = """你是一个直播SRT字幕智能剪辑师。你的任务是从完整的直播字幕中提取精彩片段。

## 输入数据格式
SRT字幕包含序号、时间范围和文本三部分：
```
1
00:00:00,000 --> 00:00:05,000
大家好欢迎来到直播间

2
00:00:10,000 --> 00:00:15,000
今天我们聊一个有趣的话题
```
**时间戳间隙代表静音**：条目1结束于00:00:05, 条目2开始于00:00:10, 中间5秒即为静音。

## 处理步骤（必须按此顺序执行）

### 第1步：扫描全文字幕，列出所有话题
通读整个字幕，识别出所有独立的话题。每个话题必须有明确的语义差异。

### 第2步：对每个话题，找出它在时间线上的所有片段
同一个话题可能被多次讨论（中间穿插了其他内容），必须搜索全文字幕找到每一个出现位置。例如：
```
时间线: [话题A 00:00-00:10] [话题B 00:10-00:15] [话题A 00:20-00:30]
话题A出现在两处: 00:00-00:10 和 00:20-00:30
话题B出现在一处: 00:10-00:15
```

**注意**：
- 话题切换通常有标志性语言（如"那我们来聊聊..."、"接下来说到..."、"换个话题..."）
- 话题回归通常有标志性语言（如"刚才说到..."、"回到刚才的话题..."）
- 不要因为主播停顿了几秒就认为是新话题

### 第3步：精确对齐片段边界到最近的SRT时间戳
每个片段的start和end必须严格对齐到某条SRT条目的时间戳，不能落在时间间隙中。

### 第4步：标记静音段到removed_sections
对于每个片段的时间范围，检查其内部和边缘是否存在SRT时间戳间隙：
- **边缘静音**：如果片段start处有SRT前导静音，将start推进到第一条SRT的开始时间
- **内部静音**：片段内部的SRT间隙 > 2秒的，标记到removed_sections
- **尾部静音**：如果片段end处有尾部静音，将end回退到最后一条SRT的结束时间

### 第5步：生成标题
每个片段生成1个吸引人的标题，必须基于该片段segments范围内的字幕文本。

## 输出格式

严格按以下JSON格式输出，不要添加任何额外内容：

```json
[
  {
    "id": "1",
    "title": "标题文本",
    "outline": "话题概述（一句话）",
    "segments": [
      {"start": "00:01:00,000", "end": "00:05:30,000"},
      {"start": "00:08:00,000", "end": "00:09:00,000"}
    ],
    "final_score": 0.85,
    "recommend_reason": "推荐理由",
    "removed_sections": [
      {"start": "00:05:30,000", "end": "00:05:45,000", "reason": "SRT时间戳间隙5秒"},
      {"start": "00:05:50,000", "end": "00:06:00,000", "reason": "与话题无关的闲聊"}
    ]
  }
]
```

## 重要约束
- 输出最多4个片段，最少1个
- 每个segments的start/end必须严格对齐到SRT条目的时间戳
- removed_sections中的时间区间必须精确对应SRT的时间戳间隙
- 时间格式: hh:mm:ss,fff（逗号分隔毫秒）
- segments和removed_sections中的时间区间不能重叠
- **标题只能基于该片段自己的segments范围内的文本**
- 不要遗漏任何字幕文本——每条SRT条目都必须归属于某个segment或removed_section
"""

# 填充词列表（预处理时剔除）
FILLER_WORDS = {
    '嗯', '呃', '哦', '哈', '嘿', '哎', '唉',
    '嗯嗯', '呃呃', '哈哈', '嘿嘿',
    '那个', '那个啥',
    '这个',
    '就是', '就是说', '也就是说',
    '然后', '然后呢',
    '对吧', '是吧', '对不对', '是不是',
    '所以说', '所以说呢',
    '的话', '的话呢',
    '好的', '好吧', '好呢',
    '一个', '一种',
    '我们可以看到', '大家可以看到',
    '总的来说', '总的来说呢',
}


def _clean_filler_words(text: str) -> str:
    """从文本中剔除填充词"""
    import re
    for word in sorted(FILLER_WORDS, key=len, reverse=True):
        text = re.sub(re.escape(word), '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _merge_srt_segments(srt_path: Path, merged_clips: List[Dict]) -> List[Dict]:
    """
    将合并方案的输出（含多段segments）转换为标准格式
    每个多段clip被拆分为多个独立clip（后续由视频拼接实现合并）
    """
    video_clips = []
    for i, clip in enumerate(merged_clips):
        segments = clip.get('segments', [])
        if not segments:
            continue
        first_seg = segments[0]
        video_clips.append({
            'id': clip.get('id', str(i + 1)),
            'outline': clip.get('outline', ''),
            'generated_title': clip.get('title', f"片段_{i+1}"),
            'start_time': first_seg.get('start', '00:00:00,000'),
            'end_time': first_seg.get('end', '00:05:00,000'),
            'final_score': clip.get('final_score', 0.5),
            'recommend_reason': clip.get('recommend_reason', ''),
            'content': [],
            '_segments': segments,
            '_removed_sections': clip.get('removed_sections', [])
        })
    return video_clips


def _srt_time_to_seconds(time_str: str) -> float:
    """将SRT时间格式(hh:mm:ss,fff)转换为秒数"""
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def _seconds_to_srt_time(seconds: float) -> str:
    """将秒数转换为SRT时间格式(hh:mm:ss,fff)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')


def _parse_srt_timeline(srt_text: str) -> List[Dict]:
    """解析SRT文本，返回按时间排序的条目列表"""
    entries = []
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        time_line = lines[1]
        time_match = re.match(r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})', time_line)
        if not time_match:
            continue
        
        start = _srt_time_to_seconds(time_match.group(1))
        end = _srt_time_to_seconds(time_match.group(2))
        text = ' '.join(lines[2:]).strip()
        
        entries.append({
            'start': start,
            'end': end,
            'start_str': time_match.group(1).replace('.', ','),
            'end_str': time_match.group(2).replace('.', ','),
            'text': text,
            'duration': end - start
        })
    
    entries.sort(key=lambda e: e['start'])
    return entries


def _validate_segments_with_srt(merged_clips: List[Dict], srt_text: str, 
                                  silence_threshold: float = 2.0) -> List[Dict]:
    """
    用SRT时间戳验证和修正LLM返回的片段边界

    Args:
        merged_clips: LLM返回的片段列表
        srt_text: 原始SRT文本
        silence_threshold: 静音阈值（秒），SRT间隙超过此值标记为静音

    Returns:
        修正后的片段列表
    """
    entries = _parse_srt_timeline(srt_text)
    if not entries:
        logger.warning("无法解析SRT时间线，跳过验证")
        return merged_clips

    logger.info(f"SRT时间线解析完成: {len(entries)} 条字幕条目")
    
    for clip in merged_clips:
        segments = clip.get('segments', [])
        if not segments:
            continue
        
        validated_segments = []
        all_removed = clip.get('removed_sections', [])
        
        for seg in segments:
            seg_start = _srt_time_to_seconds(seg.get('start', '00:00:00,000'))
            seg_end = _srt_time_to_seconds(seg.get('end', '00:00:00,000'))
            
            # 找到落在该范围内的SRT条目
            contained = [e for e in entries if e['start'] >= seg_start and e['end'] <= seg_end]
            
            if not contained:
                # 该segment内没有任何SRT条目 -> 全是静音，剔除
                all_removed.append({
                    'start': seg['start'],
                    'end': seg['end'],
                    'reason': f"该时间范围内无字幕（纯静音）"
                })
                logger.info(f"  剔除无字幕段: {seg['start']} -> {seg['end']}")
                continue
            
            # 对齐边界到第一条和最后一条SRT的时间
            validated_start = contained[0]['start']
            validated_end = contained[-1]['end']
            
            # 检查内部间隙
            for i in range(len(contained) - 1):
                gap = contained[i + 1]['start'] - contained[i]['end']
                if gap > silence_threshold:
                    all_removed.append({
                        'start': _seconds_to_srt_time(contained[i]['end']),
                        'end': _seconds_to_srt_time(contained[i + 1]['start']),
                        'reason': f"SRT时间戳间隙{gap:.1f}秒（静音）"
                    })
                    logger.info(f"  内部静音: {_seconds_to_srt_time(contained[i]['end'])} -> "
                                f"{_seconds_to_srt_time(contained[i + 1]['start'])} ({gap:.1f}秒)")
            
            validated_segments.append({
                'start': _seconds_to_srt_time(validated_start),
                'end': _seconds_to_srt_time(validated_end)
            })
            
            # 记录边界修正量
            start_diff = validated_start - seg_start
            end_diff = seg_end - validated_end
            if abs(start_diff) > 0.1 or abs(end_diff) > 0.1:
                logger.info(f"  边界修正: [{seg['start']}->{seg['end']}] -> "
                            f"[{_seconds_to_srt_time(validated_start)}->{_seconds_to_srt_time(validated_end)}] "
                            f"(前修{start_diff:.1f}s, 后修{-end_diff:.1f}s)")
        
        clip['segments'] = validated_segments if validated_segments else segments
        
        # 合并去重removed_sections
        existing_starts = {(r['start'], r['end']) for r in clip.get('removed_sections', [])}
        for r in all_removed:
            key = (r['start'], r['end'])
            if key not in existing_starts:
                clip.setdefault('removed_sections', []).append(r)
                existing_starts.add(key)
    
    return merged_clips


def parse_funclip_timestamps(input_text):
    """解析FunClip风格的时间戳提取"""
    timestamps = re.findall(r'\[(\d{2}:\d{2}:\d{2},?\d{0,3})\s*-\s*(\d{2}:\d{2}:\d{2},?\d{0,3})\]', input_text)
    times_list = []
    
    for start_time, end_time in timestamps:
        start_millis = _convert_time_to_millis(start_time)
        end_millis = _convert_time_to_millis(end_time)
        times_list.append([start_millis, end_millis])
    
    return times_list

def _convert_time_to_millis(time_str):
    """将时间字符串转换为毫秒"""
    try:
        hours, minutes, seconds, milliseconds = map(int, re.split('[:,]', time_str))
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
    except Exception as e:
        logger.warning(f"时间转换失败: {time_str}, 使用默认值: {e}")
        return 0


class FunClipStyleProcessor:
    """基于FunClip风格的单步LLM处理方案"""
    
    def __init__(self, metadata_dir: Path = None):
        from backend.core.llm_manager import LLMManager
        self.llm_manager = LLMManager()
        self.metadata_dir = metadata_dir or Path('.')
        self.chunks_dir = self.metadata_dir / "funclip_chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
    
    def process(self, srt_path: Path, processing_mode: str = "two_stage"):
        """完整的单步处理流程

        Args:
            srt_path: SRT文件路径
            processing_mode: 处理模式
                - "two_stage": 两阶段方案（默认，先识别边界再生成标题）
                - "merged": 合并方案（单次LLM调用完成所有任务）
        """
        logger.info("="*60)
        logger.info(f"使用FunClip风格处理开始 [模式: {processing_mode}]")
        logger.info("="*60)
        
        # 1. 读取和解析SRT
        srt_text = self._read_srt(srt_path)
        
        # 2. 单步LLM处理（根据模式选择）
        clips, collections = self._single_step_llm_process(srt_text, processing_mode)
        
        # 3. 保存结果
        self._save_results(clips, collections)
        
        return clips, collections
    
    def _read_srt(self, srt_path: Path):
        """读取SRT文件"""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"读取SRT失败: {e}")
            return ""
    
    def _single_step_llm_process(self, srt_text: str, processing_mode: str = "two_stage"):
        """单步LLM处理，根据模式选择不同方案"""
        if not self.llm_manager.current_provider:
            logger.warning("没有可用的LLM提供商，使用降级方案")
            return self._fallback_process(srt_text)
        
        if processing_mode == "merged":
            return self._llm_process_merged(srt_text)
        else:
            return self._llm_process_with_llm(srt_text)
    
    def _llm_process_with_llm(self, srt_text: str):
        """两阶段LLM处理：1.识别片段 2.每段独立生成标题"""
        try:
            # ===== 第一阶段：仅识别片段边界 =====
            logger.info("开始第一阶段LLM调用（识别片段边界）...")
            logger.info(f"输入SRT文本长度: {len(srt_text)} 字符")
            
            response = self.llm_manager.current_provider.call(
                FUNCLIP_CLIP_ONLY_PROMPT,
                {"text": "这是待裁剪的视频srt字幕：\n" + srt_text}
            )
            
            if not response or not response.content:
                logger.warning("第一阶段LLM返回空响应，使用降级方案")
                return self._fallback_process(srt_text)
            
            logger.info(f"第一阶段LLM响应成功，长度: {len(response.content)} 字符")
            
            clips = self._parse_clips_only(response.content)
            
            if not clips:
                logger.warning("第一阶段未能解析出片段，使用降级方案")
                return self._fallback_process(srt_text)
            
            logger.info(f"第一阶段识别到 {len(clips)} 个片段")
            for clip in clips:
                logger.info(f"  片段{clip.get('id')}: {clip.get('outline', 'N/A')}, "
                          f"时间: {clip.get('start', 'N/A')} -> {clip.get('end', 'N/A')}, "
                          f"评分: {clip.get('final_score', 0)}")
            
            # ===== 第二阶段：为每个片段独立生成标题 =====
            logger.info("=" * 40)
            logger.info("开始第二阶段：为每个片段独立生成标题")
            logger.info("=" * 40)
            
            for clip in clips:
                clip_id = clip.get('id', '')
                start_time = clip.get('start', '')
                end_time = clip.get('end', '')
                outline = clip.get('outline', '')
                recommend_reason = clip.get('recommend_reason', '')
                
                # 提取该片段自己的SRT文本
                clip_srt = self._extract_srt_segment(srt_text, start_time, end_time)
                
                if not clip_srt:
                    logger.warning(f"片段{clip_id}无法提取字幕文本，使用outline作为标题")
                    clip['generated_title'] = outline
                    continue
                
                logger.info(f"为片段{clip_id}生成标题，SRT长度: {len(clip_srt)} 字符")
                logger.debug(f"片段{clip_id}的SRT文本: {clip_srt[:200]}...")
                
                title_response = self.llm_manager.current_provider.call(
                    FUNCLIP_TITLE_PROMPT.format(
                        outline=outline,
                        recommend_reason=recommend_reason,
                        clip_srt_text=clip_srt
                    ),
                    {"text": ""}
                )
                
                if title_response and title_response.content:
                    title = title_response.content.strip()
                    # 清理可能的引号和多余字符
                    title = title.strip('"').strip("'").strip()
                    clip['generated_title'] = title
                    logger.info(f"  片段{clip_id}标题: {title}")
                else:
                    logger.warning(f"片段{clip_id}标题生成失败，使用outline")
                    clip['generated_title'] = outline
            
            # 生成合集
            collections = self._generate_collections(clips)
            
            logger.info(f"两阶段处理完成，共 {len(clips)} 个片段")
            return clips, collections
            
        except Exception as e:
            logger.warning(f"LLM处理失败: {e}，使用降级方案")
            return self._fallback_process(srt_text)
    
    def _llm_process_merged(self, srt_text: str):
        """合并方案：单次LLM调用完成话题切分 + 多段合并 + 标题生成 + 静音剔除"""
        try:
            # ===== 预处理：剔除填充词 =====
            logger.info("开始预处理SRT文本（剔除填充词）...")
            original_len = len(srt_text)
            cleaned_srt = _clean_filler_words(srt_text)
            logger.info(f"预处理完成: {original_len} -> {len(cleaned_srt)} 字符 (剔除 {original_len - len(cleaned_srt)} 字符)")

            enhanced_text = None
            try:
                from backend.pipeline.topic_precluster import TopicPreCluster
                precluster = TopicPreCluster()
                report = precluster.process(srt_text)
                if report.clusters:
                    logger.info(f"预聚类完成: {report.stats}")
                    enhanced_text = report.enhanced_text
                else:
                    logger.info(f"预聚类: 未发现有效聚类 ({report.stats['total_entries']}条, {report.stats.get('coverage_ratio', 0):.0%}覆盖)")
                    enhanced_text = cleaned_srt
            except Exception as e:
                logger.warning(f"预聚类失败，回退到清理后SRT: {e}")
                enhanced_text = cleaned_srt

            logger.info("开始合并方案LLM调用（话题切分 + 标题生成 + 静音剔除）...")
            logger.info(f"输入SRT文本长度: {len(enhanced_text)} 字符")

            response = self.llm_manager.current_provider.call(
                FUNCLIP_MERGED_PROMPT,
                {"text": "这是待分析剪辑的直播srt字幕：\n" + enhanced_text}
            )

            if not response or not response.content:
                logger.warning("合并方案LLM返回空响应，使用降级方案")
                return self._fallback_process(srt_text)

            logger.info(f"合并方案LLM响应成功，长度: {len(response.content)} 字符")

            merged_clips = self._parse_merged_response(response.content)

            if not merged_clips:
                logger.warning("合并方案未能解析出片段，使用降级方案")
                return self._fallback_process(srt_text)

            # SRT时间戳验证：修正边界 + 标记内部静音
            logger.info("开始SRT时间戳验证（修正LLM边界 + 剔除静音）...")
            merged_clips = _validate_segments_with_srt(merged_clips, srt_text)
            logger.info(f"SRT验证完成")

            logger.info(f"合并方案识别到 {len(merged_clips)} 个片段")
            for clip in merged_clips:
                seg_count = len(clip.get('segments', []))
                removed_count = len(clip.get('removed_sections', []))
                logger.info(
                    f"  片段{clip.get('id')}: {clip.get('title', 'N/A')}, "
                    f"{seg_count}个时间段, "
                    f"评分: {clip.get('final_score', 0)}, "
                    f"剔除{removed_count}段无关内容"
                )

            # 转换格式以匹配下游视频生成
            clips = _merge_srt_segments(None, merged_clips)
            collections = self._generate_collections(clips)

            logger.info(f"合并方案处理完成，共 {len(clips)} 个片段")
            return clips, collections

        except Exception as e:
            logger.warning(f"合并方案LLM处理失败: {e}，使用降级方案")
            return self._fallback_process(srt_text)
    
    def _parse_merged_response(self, response_text: str) -> List[Dict]:
        """解析合并方案LLM返回的数据"""
        merged_clips = []

        # 尝试直接解析JSON
        try:
            data = json.loads(response_text)
            if isinstance(data, list):
                for i, item in enumerate(data):
                    if 'segments' in item and isinstance(item['segments'], list) and len(item['segments']) > 0:
                        item['id'] = str(item.get('id', i + 1))
                        merged_clips.append(item)
                if merged_clips:
                    logger.info(f"JSON解析成功，共 {len(merged_clips)} 个片段")
                    return merged_clips
        except json.JSONDecodeError:
            pass

        # 尝试从文本块中提取JSON
        json_match = re.search(r'```(?:json)?\s*\n?(\[.*?\])\s*\n?```', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, list):
                    for i, item in enumerate(data):
                        if 'segments' in item and isinstance(item['segments'], list) and len(item['segments']) > 0:
                            item['id'] = str(item.get('id', i + 1))
                            merged_clips.append(item)
                    if merged_clips:
                        logger.info(f"从代码块解析JSON成功，共 {len(merged_clips)} 个片段")
                        return merged_clips
            except json.JSONDecodeError:
                pass

        logger.warning(f"无法解析合并方案响应，原始响应长度: {len(response_text)}")
        return merged_clips
    
    def _parse_clips_only(self, response: str) -> List[Dict]:
        """解析第一阶段LLM返回的片段数据（不含标题）"""
        clips = []
        
        # 直接解析JSON
        try:
            data = json.loads(response)
            if isinstance(data, list):
                clips = data
                for i, clip in enumerate(clips):
                    if 'id' not in clip or not clip['id']:
                        clip['id'] = str(i + 1)
                logger.info(f"JSON解析成功，共 {len(clips)} 个片段")
                return clips
        except json.JSONDecodeError:
            pass
        
        # 从文本中提取
        clips = self._extract_clips_from_text(response)
        return clips
    
    def _extract_srt_segment(self, full_srt: str, start_time: str, end_time: str) -> str:
        """从完整SRT中提取指定时间范围内的字幕文本"""
        lines = []
        in_range = False
        
        for line in full_srt.split('\n'):
            # 匹配时间行: 00:00:00,000 --> 00:00:05,000
            time_match = re.match(
                r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})',
                line
            )
            if time_match:
                seg_start = time_match.group(1)
                seg_end = time_match.group(2)
                # 检查是否与目标时间范围有重叠
                if (self._time_to_seconds(seg_start) <= self._time_to_seconds(end_time) and
                    self._time_to_seconds(seg_end) >= self._time_to_seconds(start_time)):
                    in_range = True
                else:
                    in_range = False
            
            if in_range:
                lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def _time_to_seconds(time_str: str) -> float:
        """将SRT时间格式转换为秒数"""
        try:
            time_str = time_str.replace(',', '.')
            parts = time_str.split(':')
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            return h * 3600 + m * 60 + s
        except Exception:
            return 0
    
    def _extract_clips_from_text(self, text: str):
        """从LLM响应中提取片段"""
        clips = []
        
        # 清理文本
        text = text.strip()
        
        # 尝试多种正则表达式模式
        patterns = [
            # 模式1: JSON格式中的outline字段
            r'\{\s*"outline"\s*:\s*"([^"]+)"[^}]*"start"\s*:\s*"([^"]+)"[^}]*"end"\s*:\s*"([^"]+)"[^}]*\}',
            # 模式2: Markdown格式
            r'\d+\.\s*\[(\d{2}:\d{2}:\d{2},?\d{0,3})\s*-\s*(\d{2}:\d{2}:\d{2},?\d{0,3})\]\s*([^\n]+)',
            # 模式3: 纯时间戳格式
            r'\[(\d{2}:\d{2}:\d{2},?\d{0,3})\s*-\s*(\d{2}:\d{2}:\d{2},?\d{0,3})\]\s*([^\n\[\]]+)',
        ]
        
        for i, pattern in enumerate(patterns):
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                logger.info(f"使用模式{i+1}成功匹配到 {len(matches)} 个片段")
                for j, match in enumerate(matches[:4]):  # 最多4个片段
                    if len(match) >= 3:
                        start_time, end_time, content = match[0], match[1], match[2]
                        clip = {
                            'id': str(j + 1),
                            'outline': content.strip(),
                            'start': start_time,
                            'end': end_time,
                            'content': [content.strip()],
                            'final_score': 0.7 + (j * 0.05),
                            'recommend_reason': '精彩片段',
                            'generated_title': f'精彩片段{str(j+1)}'
                        }
                        clips.append(clip)
                break
        
        return clips
    
    def _generate_collections(self, clips):
        """基于clips生成简单的合集"""
        if not clips:
            return []
        
        collections = [{
            'id': '1',
            'collection_title': '全部内容',
            'collection_summary': f'包含{len(clips)}个片段',
            'clip_ids': [clip['id'] for clip in clips]
        }]
                
        return collections
    
    def _fallback_process(self, srt_text: str):
        """降级方案，无LLM时使用简单处理"""
        logger.info("使用降级方案：按时间分段")
        clips = []
        
        # 解析SRT获取实际时长
        srt_entries = self._parse_srt_simple(srt_text)
        if srt_entries:
            # 根据实际内容分段
            total_duration = srt_entries[-1].get('end_seconds', 1200) if srt_entries else 1200
            interval = min(total_duration / 4, 300)  # 最多5分钟一段
        else:
            interval = 300
        
        time_intervals = []
        current_time = 0
        while current_time < (srt_entries[-1].get('end_seconds', 1200) if srt_entries else 1200):
            end_time = min(current_time + interval, 
                         (srt_entries[-1].get('end_seconds', 1200) if srt_entries else 1200))
            time_intervals.append((
                self._seconds_to_srt_time(current_time),
                self._seconds_to_srt_time(end_time)
            ))
            current_time = end_time
            if len(time_intervals) >= 4:
                break
        
        for i, (start, end) in enumerate(time_intervals):
            clips.append({
                'id': str(i + 1),
                'outline': f'片段{i+1}',
                'start': start,
                'end': end,
                'final_score': 0.5,
                'recommend_reason': '自动分段',
                'generated_title': f'精彩片段{i+1}'
            })
        
        collections = [{
            'id': '1',
            'collection_title': '自动合集',
            'collection_summary': '全部内容',
            'clip_ids': [clip['id'] for clip in clips]
        }]
            
        return clips, collections
    
    def _parse_srt_simple(self, srt_text: str) -> List[Dict]:
        """解析SRT文本获取时间信息"""
        entries = []
        pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})'
        matches = re.findall(pattern, srt_text)
        
        for match in matches:
            start_seconds = int(match[0])*3600 + int(match[1])*60 + int(match[2]) + int(match[3])/1000
            end_seconds = int(match[4])*3600 + int(match[5])*60 + int(match[6]) + int(match[7])/1000
            entries.append({
                'start_seconds': start_seconds,
                'end_seconds': end_seconds
            })
        
        return entries
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _save_results(self, clips: List[Dict], collections: List[Dict]):
        """保存处理结果"""
        try:
            clips_path = self.metadata_dir / "funclip_clips.json"
            with open(clips_path, 'w', encoding='utf-8') as f:
                json.dump(clips, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(clips)} 个切片到 {clips_path}")
            
            collections_path = self.metadata_dir / "funclip_collections.json"
            with open(collections_path, 'w', encoding='utf-8') as f:
                json.dump(collections, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(collections)} 个合集到 {collections_path}")
        except Exception as e:
            logger.warning(f"保存结果失败: {e}")


def _extract_multi_segment_clip(input_video: Path, output_path: Path,
                                 segments: List[Dict], temp_dir: Path) -> bool:
    """
    提取多段不连续的视频片段，将多个段拼接为一个视频

    Args:
        input_video: 输入视频路径
        output_path: 输出视频路径
        segments: 时间段列表，每个元素含 start 和 end
        temp_dir: 临时文件目录

    Returns:
        是否成功
    """
    from backend.utils.video_processor import VideoProcessor
    import subprocess

    temp_dir.mkdir(parents=True, exist_ok=True)

    temp_files = []
    try:
        for i, seg in enumerate(segments):
            temp_path = temp_dir / f"seg_{i}_{output_path.stem}.mp4"
            start = seg.get('start', '00:00:00,000')
            end = seg.get('end', '00:00:00,000')

            success = VideoProcessor.extract_clip(input_video, temp_path, start, end)
            if not success or not temp_path.exists():
                logger.warning(f"多段提取失败: 第{i+1}段 ({start} -> {end})")
                continue
            temp_files.append(temp_path)

        if not temp_files:
            logger.error("多段提取：没有任何段提取成功")
            return False

        if len(temp_files) == 1:
            import shutil
            shutil.copy2(str(temp_files[0]), str(output_path))
            logger.info(f"单段片段已复制: {output_path}")
            return True

        # 多段拼接：使用 concat 协议
        concat_file = temp_dir / f"concat_{output_path.stem}.txt"
        with open(concat_file, 'w', encoding='utf-8') as f:
            for tf in temp_files:
                abs_path = tf.absolute()
                escaped_path = str(abs_path).replace("'", "'\"'\"'")
                f.write(f"file '{escaped_path}'\n")

        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '28',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, encoding='utf-8', timeout=600)
        if result.returncode != 0:
            logger.error(f"多段拼接失败: {result.stderr}")
            return False

        logger.info(f"多段拼接成功: {len(segments)}段 -> {output_path}")
        return True

    except Exception as e:
        logger.error(f"多段提取异常: {e}")
        return False
    finally:
        for tf in temp_files:
            try:
                tf.unlink(missing_ok=True)
            except Exception:
                pass
        concat_file = temp_dir / f"concat_{output_path.stem}.txt"
        try:
            concat_file.unlink(missing_ok=True)
        except Exception:
            pass


def run_funclip_pipeline(srt_path: Path,
                         video_path: Path,
                         metadata_dir: Path,
                         clips_output_dir: Path,
                         collections_output_dir: Path,
                         processing_mode: str = "two_stage"):
    """运行FunClip风格的完整流水线

    Args:
        srt_path: SRT字幕文件路径
        video_path: 输入视频路径
        metadata_dir: 元数据目录
        clips_output_dir: 切片输出目录
        collections_output_dir: 合集输出目录
        processing_mode: 处理模式
            - "two_stage": 两阶段方案（默认）
            - "merged": 合并方案（单次LLM调用）
    """
    processor = FunClipStyleProcessor(metadata_dir)
    clips, collections = processor.process(srt_path, processing_mode)

    logger.info("=" * 60)
    logger.info(f"处理完成，共生成 {len(clips)} 个切片 [模式: {processing_mode}]")
    for i, clip in enumerate(clips):
        has_multi = " [多段]" if clip.get('_segments') and len(clip['_segments']) > 1 else ""
        logger.info(f"  切片{clip.get('id', i+1)}: {clip.get('generated_title', 'N/A')}{has_multi}")
        logger.info(f"    时间: {clip.get('start', 'N/A')} -> {clip.get('end', 'N/A')}")
        logger.info(f"    评分: {clip.get('final_score', 0)}")
    logger.info("=" * 60)

    # 转换格式以匹配 video_generator 的期望
    clips_for_video = []
    for clip in clips:
        video_clip = {
            'id': clip.get('id', ''),
            'outline': clip.get('outline', ''),
            'generated_title': clip.get('generated_title', f"片段_{clip.get('id', '')}"),
            'start_time': clip.get('start', '00:00:00,000'),
            'end_time': clip.get('end', '00:05:00,000'),
            'final_score': clip.get('final_score', 0.5),
            'recommend_reason': clip.get('recommend_reason', ''),
            'content': clip.get('content', [])
        }
        if clip.get('_segments'):
            video_clip['_segments'] = clip['_segments']
        if clip.get('_removed_sections'):
            video_clip['_removed_sections'] = clip['_removed_sections']
        clips_for_video.append(video_clip)

    from backend.utils.video_processor import VideoProcessor as VP
    # 视频生成
    video_generator = VideoGenerator(
        clips_dir=clips_output_dir,
        collections_dir=collections_output_dir,
        metadata_dir=metadata_dir
    )

    # 处理多段不连续切片
    temp_dir = metadata_dir / "temp_segments"
    successful_clips = []
    processed_clips_data = []

    for video_clip in clips_for_video:
        segments = video_clip.get('_segments', None)
        clip_id = video_clip['id']
        title = video_clip.get('generated_title', f"片段_{clip_id}")

        safe_title = VP.sanitize_filename(title)
        output_path = clips_output_dir / f"{clip_id}_{safe_title}.mp4"

        if segments and len(segments) > 1:
            # 多段不连续：提取每段再拼接
            logger.info(f"多段切片 {clip_id}: {len(segments)} 个时间段，正在提取拼接...")
            success = _extract_multi_segment_clip(
                video_path, output_path, segments, temp_dir
            )
            if success:
                successful_clips.append(output_path)
                processed_clips_data.append({
                    'id': clip_id,
                    'title': title,
                    'start_time': segments[0].get('start', ''),
                    'end_time': segments[-1].get('end', ''),
                    'output_path': str(output_path),
                    'keyframe_aligned': False,
                    'multi_segment': True,
                    'segment_count': len(segments)
                })
                logger.info(f"  多段切片 {clip_id} 提取成功 ({len(segments)}段合并)")
            else:
                logger.error(f"  多段切片 {clip_id} 提取失败")
        else:
            # 单段：使用原有方式
            logger.info(f"单段切片 {clip_id}: 常规切割...")
            start_time = video_clip.get('start_time', '00:00:00,000')
            end_time = video_clip.get('end_time', '00:05:00,000')

            if VP.extract_clip(video_path, output_path, start_time, end_time):
                successful_clips.append(output_path)
                processed_clips_data.append({
                    'id': clip_id,
                    'title': title,
                    'start_time': start_time,
                    'end_time': end_time,
                    'output_path': str(output_path),
                    'keyframe_aligned': False,
                    'multi_segment': False
                })
                logger.info(f"  单段切片 {clip_id} 提取成功")
            else:
                logger.error(f"  单段切片 {clip_id} 提取失败")

    # 生成合集
    successful_collections = video_generator.generate_collections(collections)

    # 更新元数据
    for clip in clips_for_video:
        for processed in processed_clips_data:
            if processed['id'] == clip['id']:
                clip['start_time'] = processed.get('start_time', clip['start_time'])
                clip['end_time'] = processed.get('end_time', clip['end_time'])
                break

    # 保存元数据
    video_generator.save_clip_metadata(clips_for_video, metadata_dir / "clips_metadata.json")
    video_generator.save_collection_metadata(collections, metadata_dir / "collections_metadata.json")

    # 同时保存到项目根目录
    project_dir = metadata_dir.parent
    try:
        video_generator.save_clip_metadata(clips_for_video, project_dir / "clips_metadata.json")
        video_generator.save_collection_metadata(collections, project_dir / "collections_metadata.json")
        logger.info(f"元数据已保存到项目根目录: {project_dir}")
    except Exception as e:
        logger.warning(f"保存备用元数据失败: {e}")

    logger.info(f"FunClip方案处理完成 [模式: {processing_mode}]")
    logger.info(f"  成功: {len(successful_clips)}/{len(clips_for_video)} 个切片")
    logger.info(f"  合集: {len(successful_collections)} 个")

    return clips, collections
