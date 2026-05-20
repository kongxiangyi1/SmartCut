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

# 完整的System Prompt (基于FunClip的设计)
FUNCLIP_SYSTEM_PROMPT = """你是一个视频srt字幕分析剪辑器，输入视频的srt字幕，
分析其中的精彩且尽可能连续的片段并裁剪出来，输出四条以内的片段，
将片段中在时间上连续的多个句子及它们的时间戳合并为一条，
注意确保文字与时间戳的正确匹配。输出需严格按照如下格式：
1. [开始时间-结束时间] 文本，注意其中的连接符是"-"

同时为每个片段添加：
- 评分 (0.0-1.0)
- 推荐理由
- 吸引人的标题

最终JSON格式输出示例：
[
  {
    "id": "1",
    "outline": "话题标题",
    "start": "00:00:00,500",
    "end": "00:05:30,123",
    "final_score": 0.85,
    "recommend_reason": "推荐理由",
    "generated_title": "吸引人的标题"
  }
]
"""

FUNCLIP_USER_PROMPT = "这是待裁剪的视频srt字幕："

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
    
    def process(self, srt_path: Path):
        """完整的单步处理流程"""
        logger.info("="*60)
        logger.info("使用FunClip风格处理开始")
        logger.info("="*60)
        
        # 1. 读取和解析SRT
        srt_text = self._read_srt(srt_path)
        
        # 2. 单步LLM处理
        clips, collections = self._single_step_llm_process(srt_text)
        
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
    
    def _single_step_llm_process(self, srt_text: str):
        """单步LLM处理，一次性完成所有任务"""
        if self.llm_manager.current_provider:
            return self._llm_process_with_llm(srt_text)
        else:
            logger.warning("没有可用的LLM提供商，使用降级方案")
            return self._fallback_process(srt_text)
    
    def _llm_process_with_llm(self, srt_text: str):
        """使用LLM处理"""
        try:
            logger.info("开始调用LLM（FunClip风格）...")
            logger.info(f"输入SRT文本长度: {len(srt_text)} 字符")
            
            # 调用LLM
            response = self.llm_manager.current_provider.call(
                FUNCLIP_SYSTEM_PROMPT,
                {"text": FUNCLIP_USER_PROMPT + '\n' + srt_text}
            )
            
            if response and response.content:
                logger.info(f"LLM响应成功，长度: {len(response.content)} 字符")
                logger.info(f"LLM响应内容预览: {response.content[:500]}...")
                
                clips, collections = self._parse_llm_response(response.content)
                return clips, collections
            else:
                logger.warning("LLM返回空响应，使用降级方案")
                
        except Exception as e:
            logger.warning(f"LLM处理失败: {e}，使用降级方案")
        
        return self._fallback_process(srt_text)
    
    def _parse_llm_response(self, response: str):
        """解析LLM返回的响应"""
        clips = []
        
        # 方法1: 直接解析JSON
        try:
            logger.info("尝试直接解析JSON...")
            data = json.loads(response)
            if isinstance(data, list):
                clips = data
                # 确保每个片段都有 id 字段
                for i, clip in enumerate(clips):
                    if 'id' not in clip or not clip['id']:
                        clip['id'] = str(i + 1)
                        logger.warning(f"片段{i+1}缺少id字段，已自动添加: {clip['id']}")
                    logger.info(f"  片段{clip['id']}: {clip.get('outline', 'N/A')}, "
                              f"时间: {clip.get('start', 'N/A')} - {clip.get('end', 'N/A')}, "
                              f"标题: {clip.get('generated_title', 'N/A')}")
                logger.info(f"直接JSON解析成功，共 {len(clips)} 个片段")
                return clips, self._generate_collections(clips)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
        
        # 方法2: 从文本中提取时间戳
        logger.info("尝试从文本中提取时间戳...")
        clips = self._extract_clips_from_text(response)
        
        if clips:
            logger.info(f"文本提取成功，共 {len(clips)} 个片段")
            for i, clip in enumerate(clips):
                logger.info(f"  片段{i+1}: {clip.get('outline', 'N/A')}, "
                          f"时间: {clip.get('start', 'N/A')} -> {clip.get('end', 'N/A')}")
        else:
            logger.warning("文本提取失败，使用降级方案")
            return self._fallback_process(response)
        
        # 生成合集
        collections = self._generate_collections(clips)
        
        return clips, collections
    
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


def run_funclip_pipeline(srt_path: Path,
                         video_path: Path,
                         metadata_dir: Path,
                         clips_output_dir: Path,
                         collections_output_dir: Path):
    """运行FunClip风格的完整流水线"""
    processor = FunClipStyleProcessor(metadata_dir)
    clips, collections = processor.process(srt_path)
    
    logger.info("="*60)
    logger.info(f"处理完成，共生成 {len(clips)} 个切片")
    for i, clip in enumerate(clips):
        logger.info(f"  切片{clip.get('id', i+1)}: {clip.get('generated_title', 'N/A')}")
        logger.info(f"    时间: {clip.get('start', 'N/A')} -> {clip.get('end', 'N/A')}")
        logger.info(f"    评分: {clip.get('final_score', 0)}")
    logger.info("="*60)
    
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
        clips_for_video.append(video_clip)
    
    # 视频生成
    video_generator = VideoGenerator(
        clips_dir=clips_output_dir,
        collections_dir=collections_output_dir,
        metadata_dir=metadata_dir
    )
    
    # 生成clips
    successful_clips = video_generator.generate_clips(clips_for_video, video_path)
    successful_collections = video_generator.generate_collections(collections)
    
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
    
    logger.info(f"FunClip方案处理完成")
    
    return clips, collections
