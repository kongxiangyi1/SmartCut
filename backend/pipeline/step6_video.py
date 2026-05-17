"""
Step 6: 视频生成 - 根据聚类结果生成最终视频切片
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

# 导入依赖
from ..utils.video_processor import VideoProcessor
from ..utils.smart_clip_generator import SmartClipGenerator
from ..utils.subtitle_processor import SubtitleProcessor
from ..core.shared_config import METADATA_DIR, CLIPS_DIR, COLLECTIONS_DIR

logger = logging.getLogger(__name__)

class VideoGenerator:
    """视频生成器"""
    
    def __init__(self, clips_dir: Optional[str] = None, collections_dir: Optional[str] = None, metadata_dir: Optional[str] = None):
        # 强制使用项目内专属目录，不使用全局目录作为后备
        if not clips_dir:
            raise ValueError("clips_dir 参数是必需的，不能使用全局路径")
        if not collections_dir:
            raise ValueError("collections_dir 参数是必需的，不能使用全局路径")
        
        self.clips_dir = Path(clips_dir)
        self.collections_dir = Path(collections_dir)
        self.metadata_dir = Path(metadata_dir) if metadata_dir else METADATA_DIR
        
        # 确保目录存在
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.collections_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建VideoProcessor实例，强制使用项目内路径
        self.video_processor = VideoProcessor(clips_dir=str(self.clips_dir), collections_dir=str(self.collections_dir))
        
        # 创建智能切片生成器
        self.smart_clip_generator = SmartClipGenerator()
    
    def generate_clips(self, clips_with_titles: List[Dict], input_video: Path, 
                       srt_path: Optional[Path] = None, use_smart_clips: bool = False) -> List[Path]:
        """
        生成切片视频
        
        Args:
            clips_with_titles: 带标题的片段数据
            input_video: 输入视频路径
            srt_path: SRT字幕文件路径（用于智能切片）
            use_smart_clips: 是否使用智能切片生成
            
        Returns:
            生成的切片视频路径列表
        """
        logger.info("开始生成切片视频...")
        
        # 如果启用智能切片，先处理话题
        if use_smart_clips and srt_path and srt_path.exists():
            logger.info("使用智能切片生成模式...")
            return self._generate_smart_clips(clips_with_titles, input_video, srt_path)
        
        # 标准切片生成
        clips_data = []
        for clip in clips_with_titles:
            clips_data.append({
                'id': clip['id'],
                'title': clip.get('generated_title', f"片段_{clip['id']}"),
                'start_time': clip['start_time'],
                'end_time': clip['end_time']
            })
        
        # 批量生成切片（使用并行处理提升速度）
        # 注意：batch_extract_clips_parallel 会修改 clips_data 中的时间（静音处理在并行前完成）
        # 不指定 max_workers，让系统自动根据服务器配置（CPU、内存、磁盘类型）计算最优线程数
        successful_clips = self.video_processor.batch_extract_clips_parallel(
            input_video, clips_data
        )
        
        # 将静音处理后的时间同步回 clips_with_titles，确保元数据与实际视频一致
        for clip_data in clips_data:
            for clip in clips_with_titles:
                # 使用 str() 统一类型比较，避免整数和字符串比较失败
                if str(clip['id']) == str(clip_data['id']):
                    # 同步静音处理后的时间
                    if 'start_time' in clip_data:
                        clip['start_time'] = clip_data['start_time']
                    if 'end_time' in clip_data:
                        clip['end_time'] = clip_data['end_time']
                    
                    # 计算 duration - 优先用视频实际时长，如果获取失败则用时间差计算
                    start_sec = self._time_to_seconds(clip['start_time'])
                    end_sec = self._time_to_seconds(clip['end_time'])
                    calculated_duration = end_sec - start_sec
                    
                    # 检查实际视频时长
                    if clip_data.get('duration', 0) > 0:
                        # 优先使用实际视频时长，但确保在合理范围内
                        clip['duration'] = clip_data['duration']
                        logger.debug(f"切片 {clip['id']}: 使用实际视频时长 {clip['duration']:.3f}s")
                    else:
                        # 如果没有实际时长，使用计算的时长
                        clip['duration'] = calculated_duration
                        logger.debug(f"切片 {clip['id']}: 使用计算时长 {calculated_duration:.3f}s")
                    
                    # 确保 duration 是正数
                    if clip['duration'] <= 0:
                        clip['duration'] = max(1.0, calculated_duration)  # 至少1秒
                        logger.warning(f"切片 {clip['id']}: 修正时长为 {clip['duration']:.3f}s")
                    break
        
        logger.info(f"切片视频生成完成，共{len(successful_clips)}个切片")
        return successful_clips
    
    def _time_to_seconds(self, time_str: str) -> float:
        """将时间字符串转换为秒数"""
        try:
            time_str = time_str.replace(',', '.')
            if '.' in time_str:
                time_part, ms_part = time_str.split('.')
                milliseconds = int(ms_part)
            else:
                time_part = time_str
                milliseconds = 0
            
            h, m, s = map(int, time_part.split(':'))
            return h * 3600 + m * 60 + s + milliseconds / 1000
        except Exception:
            return 0.0
    
    def _generate_smart_clips(self, clips_with_titles: List[Dict], input_video: Path, srt_path: Path) -> List[Path]:
        """
        使用智能切片生成器生成切片（钩子+话题+产品复用）
        """
        logger.info("使用智能切片生成器...")
        
        # 加载SRT字幕
        try:
            subtitle_processor = SubtitleProcessor()
            srt_data = subtitle_processor.parse_srt_file(str(srt_path))
        except Exception as e:
            logger.error(f"加载SRT字幕失败: {e}")
            # 回退到标准模式
            return self.generate_clips(clips_with_titles, input_video)
        
        # 使用智能切片生成器处理
        try:
            # 将clips_with_titles转换为话题格式
            topics = []
            for clip in clips_with_titles:
                topics.append({
                    'id': clip['id'],
                    'outline': clip.get('generated_title', clip.get('title', f"话题_{clip['id']}")),
                    'start_time': clip['start_time'],
                    'end_time': clip['end_time']
                })
            
            # 生成智能切片
            smart_clips = self.smart_clip_generator.generate_clips(topics, srt_data)
            
            logger.info(f"智能切片生成器生成了 {len(smart_clips)} 个切片")
            
            # 提取视频切片
            clips_data = []
            for i, smart_clip in enumerate(smart_clips):
                clips_data.append({
                    'id': smart_clip['topic_id'] or str(i + 1),
                    'title': smart_clip['topic_title'],
                    'start_time': smart_clip['start_time'],
                    'end_time': smart_clip['end_time'],
                    'hook_info': smart_clip['hook'],
                    'product_info': smart_clip['product_pitch']
                })
            
            # 批量生成切片
            successful_clips = self.video_processor.batch_extract_clips(input_video, clips_data)
            
            return successful_clips
            
        except Exception as e:
            logger.error(f"智能切片生成失败: {e}")
            # 回退到标准模式
            return self.generate_clips(clips_with_titles, input_video)
    
    def generate_collections(self, collections_data: List[Dict]) -> List[Path]:
        """
        生成合集视频
        
        Args:
            collections_data: 合集数据
            
        Returns:
            生成的合集视频路径列表
        """
        logger.info("开始生成合集视频...")
        
        # 生成合集视频
        successful_collections = self.video_processor.create_collections_from_metadata(collections_data)
        
        logger.info(f"合集视频生成完成，共{len(successful_collections)}个合集")
        return successful_collections
    
    def save_clip_metadata(self, clips_with_titles: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        保存最终的切片元数据到clips_metadata.json
        
        Args:
            clips_with_titles: 带标题的片段数据（来自step4）
            output_path: 输出路径，默认为clips_metadata.json
            
        Returns:
            保存的文件路径
            
        Note:
            此方法保存的是最终的切片元数据，包含视频生成后的完整信息。
            与step4的step4_titles.json不同，这里保存的是用于前端展示的最终数据。
            确保同时保存 final_score 和 score 两个字段，保证兼容性。
        """
        if output_path is None:
            output_path = self.metadata_dir / "clips_metadata.json"
        
        # 确保目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 处理数据：确保同时有 final_score 和 score 两个字段，并且处理 recommend_reason
        processed_clips = []
        for clip in clips_with_titles:
            # 复制原数据
            processed_clip = clip.copy()
            
            # 处理评分字段：确保同时有 final_score 和 score
            if 'final_score' in clip:
                processed_clip['score'] = clip['final_score']
            elif 'score' in clip:
                processed_clip['final_score'] = clip['score']
            else:
                # 如果都没有，设置默认值
                processed_clip['final_score'] = 0.0
                processed_clip['score'] = 0.0
            
            # 处理推荐理由字段
            if 'recommend_reason' in clip and clip['recommend_reason']:
                processed_clip['description'] = clip['recommend_reason']
            elif 'description' in clip and clip['description']:
                processed_clip['recommend_reason'] = clip['description']
            
            # 确保 content 字段存在（用于前端显示）
            if 'content' not in processed_clip:
                outline = processed_clip.get('outline', '')
                if isinstance(outline, dict):
                    outline_text = outline.get('title', '') or outline.get('content', '')
                else:
                    outline_text = str(outline)
                
                processed_clip['content'] = outline_text
            
            processed_clips.append(processed_clip)
        
        # 保存数据
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(processed_clips, f, ensure_ascii=False, indent=2)
        
        logger.info(f"切片元数据已保存到: {output_path}, 包含 {len(processed_clips)} 个切片")
        return output_path
    
    def save_collection_metadata(self, collections_data: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        保存合集元数据
        
        Args:
            collections_data: 合集数据
            output_path: 输出路径
            
        Returns:
            保存的文件路径
        """
        if output_path is None:
            output_path = self.metadata_dir / "collections_metadata.json"
        
        # 确保目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存数据
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(collections_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"合集元数据已保存到: {output_path}")
        return output_path

def run_step6_video(clips_with_titles_path: Path, collections_path: Path, 
                   input_video: Path, output_dir: Optional[Path] = None, 
                   clips_dir: Optional[str] = None, collections_dir: Optional[str] = None, 
                   metadata_dir: Optional[str] = None, srt_path: Optional[Path] = None,
                   use_smart_clips: bool = False) -> Dict:
    """
    运行Step 6: 视频切割
    
    Args:
        clips_with_titles_path: 带标题的片段文件路径
        collections_path: 合集文件路径
        input_video: 输入视频路径
        output_dir: 输出目录
        srt_path: SRT字幕文件路径（用于智能切片）
        use_smart_clips: 是否使用智能切片生成
        
    Returns:
        生成结果信息
    """
    # 加载数据
    with open(clips_with_titles_path, 'r', encoding='utf-8') as f:
        clips_with_titles = json.load(f)
    
    with open(collections_path, 'r', encoding='utf-8') as f:
        collections_data = json.load(f)
    
    # 创建视频生成器
    generator = VideoGenerator(clips_dir=clips_dir, collections_dir=collections_dir, metadata_dir=metadata_dir)
    
    # 生成切片视频（支持智能切片模式）
    successful_clips = generator.generate_clips(clips_with_titles, input_video, srt_path, use_smart_clips)
    
    # 生成合集视频
    successful_collections = generator.generate_collections(collections_data)
    
    # 保存元数据到项目目录
    # 注意：clips_metadata.json在这里保存，包含最终的切片元数据（包含视频路径等信息）
    # 这与step4的step4_titles.json不同，step4只保存带标题的片段数据
    if metadata_dir:
        project_metadata_dir = Path(metadata_dir)
        generator.save_clip_metadata(clips_with_titles, project_metadata_dir / "clips_metadata.json")
        generator.save_collection_metadata(collections_data, project_metadata_dir / "collections_metadata.json")
    else:
        generator.save_clip_metadata(clips_with_titles)
        generator.save_collection_metadata(collections_data)
    
    # 返回结果信息
    result = {
        'clips_generated': len(successful_clips),
        'collections_generated': len(successful_collections),
        'clip_paths': [str(path) for path in successful_clips],
        'collection_paths': [str(path) for path in successful_collections]
    }
    
    logger.info(f"视频生成完成: {result['clips_generated']}个切片, {result['collections_generated']}个合集")
    
    # 保存结果到输出文件
    if output_dir is not None:
        output_path = output_dir / "step6_video_output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"步骤6结果已保存到: {output_path}")
    
    return result