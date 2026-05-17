"""
静音处理器 - 处理视频切片中的静音部分
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SilenceProcessor:
    """静音处理器类，用于处理视频切片中的静音部分"""
    
    @staticmethod
    def extract_audio_from_video(video_path: Path, audio_output_path: Path) -> bool:
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
            audio_output_path: 音频输出路径
            
        Returns:
            是否成功提取音频
        """
        try:
            # 使用 FFmpeg 提取音频
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vn',  # 不要视频
                '-acodec', 'pcm_s16le',  # 音频编码格式
                '-ar', '16000',  # 采样率
                '-ac', '1',  # 单声道
                '-y',  # 覆盖输出文件
                str(audio_output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.info(f"成功提取音频: {audio_output_path}")
                return True
            else:
                logger.error(f"提取音频失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("提取音频超时")
            return False
        except Exception as e:
            logger.error(f"提取音频异常: {e}")
            return False
    
    @staticmethod
    def skip_leading_silence(audio_path: Path, threshold: float = -40.0) -> float:
        """
        计算开头静音跳过时间
        
        Args:
            audio_path: 音频文件路径
            threshold: 静音阈值（dB）
            
        Returns:
            开头静音持续时间（秒）
        """
        try:
            # 使用 FFmpeg 的 volumedetect 滤镜检测音量
            cmd = [
                'ffmpeg',
                '-i', str(audio_path),
                '-af', f'volumedetect',
                '-f', 'null',
                '-'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # 解析输出获取平均音量
            output = result.stderr
            mean_volume = None
            
            for line in output.split('\n'):
                if 'mean_volume' in line:
                    # 提取平均音量值
                    import re
                    match = re.search(r'mean_volume:\s*([-\d.]+)\s*dB', line)
                    if match:
                        mean_volume = float(match.group(1))
                        break
            
            if mean_volume is not None and mean_volume < threshold:
                # 如果平均音量低于阈值，认为有静音
                # 这里简化处理，返回 0
                logger.info(f"检测到开头静音，平均音量: {mean_volume} dB")
                return 0.0
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"检测开头静音失败: {e}")
            return 0.0
    
    @staticmethod
    def process_silence(audio_path: Path, threshold: float = -40.0, 
                       min_silence_duration: float = 0.5) -> list:
        """
        处理音频中的静音
        
        Args:
            audio_path: 音频文件路径
            threshold: 静音阈值（dB）
            min_silence_duration: 最小静音持续时间（秒）
            
        Returns:
            静音区间列表 [(start, end), ...]
        """
        try:
            # 使用 FFmpeg 的 silencedetect 滤镜检测静音
            cmd = [
                'ffmpeg',
                '-i', str(audio_path),
                '-af', f'silencedetect=noise={threshold}dB:d={min_silence_duration}',
                '-f', 'null',
                '-'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # 解析输出获取静音区间
            output = result.stderr
            silence_ranges = []
            
            import re
            # 匹配 "silence_start: xxx" 和 "silence_end: xxx"
            start_matches = re.findall(r'silence_start:\s*([\d.]+)', output)
            end_matches = re.findall(r'silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)', output)
            
            # 处理静音区间
            for i, (end_time, duration) in enumerate(end_matches):
                if i < len(start_matches):
                    start_time = float(start_matches[i])
                    end_time = float(end_time)
                    silence_ranges.append((start_time, end_time))
            
            logger.info(f"检测到 {len(silence_ranges)} 个静音区间")
            return silence_ranges
            
        except Exception as e:
            logger.error(f"处理静音失败: {e}")
            return []
    
    @staticmethod
    def concat_with_silence_removed(video_paths: list, output_path: Path,
                                    silence_threshold: float = -40.0) -> bool:
        """
        拼接视频并移除静音部分
        
        Args:
            video_paths: 视频文件路径列表
            output_path: 输出文件路径
            silence_threshold: 静音阈值（dB）
            
        Returns:
            是否成功
        """
        try:
            # 简化处理：直接拼接视频，不处理静音
            # 完整实现需要先处理每个视频的静音，然后拼接
            
            if not video_paths:
                logger.error("没有视频文件")
                return False
            
            if len(video_paths) == 1:
                # 只有一个视频，直接复制
                import shutil
                shutil.copy(video_paths[0], output_path)
                return True
            
            # 多个视频，创建文件列表
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
                timeout=600
            )
            
            # 清理临时文件
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
    
    @staticmethod
    def adjust_clip_for_silence(start_time: float, end_time: float, audio_path: Path,
                               silence_threshold: float = -40.0,
                               buffer_duration: float = 0.2,
                               long_silence_threshold: float = 3.0) -> Tuple[float, float]:
        """
        调整切片时间以移除长静音部分
        
        Args:
            start_time: 切片开始时间（秒）
            end_time: 切片结束时间（秒）
            audio_path: 音频文件路径
            silence_threshold: 静音阈值（dB）
            buffer_duration: 语音前后保留的缓冲时间（秒）
            long_silence_threshold: 长静音阈值（秒），超过此值认为是长静音
            
        Returns:
            调整后的 (start_time, end_time)
        """
        try:
            # 使用 FFmpeg silencedetect 滤镜检测静音
            # 只分析指定时间范围内的音频
            cmd = [
                'ffmpeg',
                '-i', str(audio_path),
                '-ss', str(start_time),
                '-to', str(end_time),
                '-af', f'silencedetect=noise={silence_threshold}dB:d={buffer_duration}',
                '-f', 'null',
                '-'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # 解析输出获取静音区间
            output = result.stderr
            
            # 提取所有静音区间
            silence_ranges = []
            lines = output.split('\n')
            
            for i, line in enumerate(lines):
                if 'silence_start' in line:
                    # 提取静音开始时间
                    match = re.search(r'silence_start:\s*([\d.]+)', line)
                    if match:
                        silence_start = float(match.group(1))
                        # 查找对应的 silence_end
                        for j in range(i+1, min(i+5, len(lines))):
                            if 'silence_end' in lines[j]:
                                match_end = re.search(r'silence_end:\s*([\d.]+)', lines[j])
                                if match_end:
                                    silence_end = float(match_end.group(1))
                                    silence_duration = silence_end - silence_start
                                    
                                    # 只记录长静音
                                    if silence_duration >= long_silence_threshold:
                                        # 转换为绝对时间
                                        silence_ranges.append((
                                            start_time + silence_start,
                                            start_time + silence_end
                                        ))
                                break
            
            if not silence_ranges:
                # 没有检测到长静音，返回原始时间
                return start_time, end_time
            
            # 计算调整后的时间
            adjusted_start = start_time
            adjusted_end = end_time
            
            for silence_start, silence_end in silence_ranges:
                # 计算静音持续时间
                silence_duration = silence_end - silence_start
                
                # 如果静音在开始附近，缩短开始时间
                if silence_start - start_time < 1.0:
                    adjusted_start = silence_end + buffer_duration
                
                # 如果静音在结束附近，缩短结束时间
                if end_time - silence_end < 1.0:
                    adjusted_end = silence_start - buffer_duration
                
                # 如果静音在中间，计算需要移除的时间
                if adjusted_start <= silence_start and silence_end <= adjusted_end:
                    # 保留短缓冲
                    cut_amount = silence_duration - (2 * buffer_duration)
                    if cut_amount > 0:
                        # 这里简化处理：不做真正的剪切，只是记录
                        pass
            
            # 确保调整后的时间有效
            adjusted_start = max(start_time, adjusted_start)
            adjusted_end = min(end_time, adjusted_end)
            
            # 确保开始时间小于结束时间
            if adjusted_start >= adjusted_end:
                logger.warning(f"调整后时间无效 ({adjusted_start:.2f} >= {adjusted_end:.2f})，保持原时间")
                return start_time, end_time
            
            logger.info(f"静音调整: ({start_time:.2f}, {end_time:.2f}) -> ({adjusted_start:.2f}, {adjusted_end:.2f})")
            return adjusted_start, adjusted_end
            
        except Exception as e:
            logger.error(f"调整切片静音失败: {e}")
            return start_time, end_time
