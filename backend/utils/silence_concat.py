"""
静音拼接器 - 用于处理包含静音的视频片段
"""

import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SilenceConcat:
    """静音拼接器类，用于处理包含静音的视频片段拼接"""
    
    def __init__(self, long_silence_threshold: float = 3.0, 
                 short_silence_keep: float = 1.0,
                 buffer_duration: float = 0.2):
        """
        初始化静音拼接器
        
        Args:
            long_silence_threshold: 长静音阈值（秒），超过此值认为是长静音
            short_silence_keep: 短静音保留时间（秒）
            buffer_duration: 语音前后保留的缓冲时间（秒）
        """
        self.long_silence_threshold = long_silence_threshold
        self.short_silence_keep = short_silence_keep
        self.buffer_duration = buffer_duration
    
    def process_and_concat(self, video_clips: List[Dict], output_path: Path,
                          silence_threshold: float = -40.0) -> bool:
        """
        处理视频片段中的静音并拼接
        
        Args:
            video_clips: 视频片段列表，每个元素包含：
                - path: 视频文件路径
                - start_time: 开始时间
                - end_time: 结束时间
            output_path: 输出文件路径
            silence_threshold: 静音阈值（dB）
            
        Returns:
            是否成功
        """
        try:
            if not video_clips:
                logger.error("没有视频片段")
                return False
            
            if len(video_clips) == 1:
                # 只有一个片段，直接复制
                import shutil
                shutil.copy(video_clips[0]['path'], output_path)
                return True
            
            # 简化处理：直接拼接所有片段
            concat_list = output_path.parent / "concat_list.txt"
            with open(concat_list, 'w', encoding='utf-8') as f:
                for clip in video_clips:
                    f.write(f"file '{clip['path']}'\n")
            
            # 使用 FFmpeg 拼接
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_list),
                '-c', 'copy',
                '-y',
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=600
            )
            
            # 清理临时文件
            if concat_list.exists():
                concat_list.unlink()

            if result.returncode == 0:
                logger.info(f"成功拼接视频: {output_path}")
                return True
            else:
                logger.error(f"拼接视频失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"拼接视频异常: {e}")
            return False
    
    def extract_speech_segments(self, audio_path: Path, 
                              silence_threshold: float = -40.0) -> List[Dict]:
        """
        从音频中提取语音片段
        
        Args:
            audio_path: 音频文件路径
            silence_threshold: 静音阈值（dB）
            
        Returns:
            语音片段列表，每个元素包含 start 和 end
        """
        try:
            # 使用 FFmpeg silencedetect 滤镜检测语音片段
            cmd = [
                'ffmpeg',
                '-i', str(audio_path),
                '-af', f'silencedetect=noise={silence_threshold}dB:d={self.long_silence_threshold}',
                '-f', 'null',
                '-'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=300
            )
            
            # 解析输出
            output = result.stderr
            import re
            
            speech_segments = []
            lines = output.split('\n')
            
            i = 0
            while i < len(lines):
                line = lines[i]
                if 'silence_end' in line:
                    # 提取静音结束时间
                    match = re.search(r'silence_end:\s*([\d.]+)', line)
                    if match:
                        speech_start = float(match.group(1))
                        # 添加缓冲时间
                        speech_start = max(0, speech_start - self.buffer_duration)
                        
                        # 查找对应的静音开始
                        if i > 0 and 'silence_start' in lines[i-1]:
                            match_start = re.search(r'silence_start:\s*([\d.]+)', lines[i-1])
                            if match_start:
                                silence_end = float(match_start.group(1))
                                speech_end = silence_end + self.buffer_duration
                                
                                speech_segments.append({
                                    'start': speech_start,
                                    'end': speech_end
                                })
                i += 1
            
            logger.info(f"提取到 {len(speech_segments)} 个语音片段")
            return speech_segments
            
        except Exception as e:
            logger.error(f"提取语音片段失败: {e}")
            return []
    
    def concat_videos(self, video_paths: List[Path], output_path: Path) -> bool:
        """
        拼接多个视频文件
        
        Args:
            video_paths: 视频文件路径列表
            output_path: 输出文件路径
            
        Returns:
            是否成功
        """
        try:
            if not video_paths:
                logger.error("没有视频文件")
                return False
            
            # 创建文件列表
            concat_list = output_path.parent / "concat_list.txt"
            with open(concat_list, 'w', encoding='utf-8') as f:
                for video_path in video_paths:
                    f.write(f"file '{video_path}'\n")
            
            # 使用 FFmpeg 拼接
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_list),
                '-c', 'copy',
                '-y',
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=600
            )
            
            # 清理临时文件
            if concat_list.exists():
                concat_list.unlink()
            
            if result.returncode == 0:
                logger.info(f"成功拼接视频: {output_path}")
                return True
            else:
                logger.error(f"拼接视频失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"拼接视频异常: {e}")
            return False
