"""
视频处理工具
"""
import subprocess
import json
import logging
import re
import time
import os
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# 修复导入问题
try:
    from ..core.shared_config import CLIPS_DIR, COLLECTIONS_DIR
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from ..core.shared_config import CLIPS_DIR, COLLECTIONS_DIR

# 导入静音处理器
try:
    from .silence_processor import SilenceProcessor
    silence_processor_available = True
except ImportError:
    silence_processor_available = False
    logger.warning("静音处理器模块未找到")

# 导入静音拼接器（新模块）
try:
    from .silence_concat import SilenceConcat
    silence_concat_available = True
except ImportError:
    silence_concat_available = False
    logger.warning("静音拼接器模块未找到")

logger = logging.getLogger(__name__)

class VideoProcessor:
    """视频处理工具类"""
    
    def __init__(self, clips_dir: Optional[str] = None, collections_dir: Optional[str] = None):
        # 强制使用传入的项目特定路径，不使用全局路径作为后备
        if not clips_dir:
            raise ValueError("clips_dir 参数是必需的，不能使用全局路径")
        if not collections_dir:
            raise ValueError("collections_dir 参数是必需的，不能使用全局路径")
        
        self.clips_dir = Path(clips_dir)
        self.collections_dir = Path(collections_dir)
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名，移除或替换不合法的字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        # 移除或替换不合法的字符
        # Windows和Unix系统都不允许的字符: < > : " | ? * \ /
        # 替换为下划线
        sanitized = re.sub(r'[<>:"|?*\\/]', '_', filename)
        
        # 移除前后空格和点
        sanitized = sanitized.strip(' .')
        
        # 限制长度，避免文件名过长
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        # 确保文件名不为空
        if not sanitized:
            sanitized = "untitled"
            
        return sanitized
    
    @staticmethod
    def convert_srt_time_to_ffmpeg_time(srt_time: str) -> str:
        """
        将SRT时间格式转换为FFmpeg时间格式
        
        Args:
            srt_time: SRT时间格式 (如 "00:00:06,140" 或 "00:00:06.140")
            
        Returns:
            FFmpeg时间格式 (如 "00:00:06.140")
        """
        # 将逗号替换为点
        return srt_time.replace(',', '.')
    
    def process_silence_for_clips(self, input_video: Path, clips_data: List[Dict], 
                                  skip_leading_silence: bool = True,
                                  remove_long_silence: bool = True,
                                  silence_threshold: float = 2.0,
                                  buffer_duration: float = 0.3) -> List[Dict]:
        """
        处理切片的静音
        
        Args:
            input_video: 输入视频路径
            clips_data: 片段数据列表
            skip_leading_silence: 是否跳过开头静音
            remove_long_silence: 是否去除切片内部过长的静音
            silence_threshold: 静音阈值（秒）
            buffer_duration: 语音前后保留的缓冲时间（秒）
            
        Returns:
            处理后的片段数据列表
        """
        if not silence_processor_available:
            logger.warning("静音处理器不可用，跳过静音处理")
            return clips_data
            
        try:
            # 确保 input_video 是 Path 对象
            input_video = Path(input_video)
            
            # 提取音频用于静音检测
            audio_path = input_video.parent / "input_audio.wav"
            
            # 提取音频
            if not SilenceProcessor.extract_audio_from_video(input_video, audio_path):
                logger.warning("无法提取音频，跳过静音处理")
                return clips_data
            
            # 创建静音处理器实例
            processor = SilenceProcessor()
            
            # 计算开头静音跳过时间
            skip_time = 0.0
            if skip_leading_silence:
                skip_time = processor.skip_leading_silence(audio_path)
                logger.info(f"检测到开头静音 {skip_time:.2f} 秒，将自动跳过")
            
            # 处理每个切片
            processed_clips = []
            for clip_data in clips_data:
                clip_start = clip_data['start_time']
                clip_end = clip_data['end_time']
                
                # 转换为秒数
                if isinstance(clip_start, str):
                    clip_start = VideoProcessor.convert_ffmpeg_time_to_seconds(clip_start)
                if isinstance(clip_end, str):
                    clip_end = VideoProcessor.convert_ffmpeg_time_to_seconds(clip_end)
                
                # 应用开头静音跳过
                adjusted_start = clip_start + skip_time
                adjusted_end = clip_end + skip_time
                
                # 如果调整后开始时间超过结束时间，跳过这个切片
                if adjusted_start >= adjusted_end:
                    logger.warning(f"切片 {clip_data['id']} 被静音跳过，已丢弃")
                    continue
                
                # 处理切片内部的静音
                if remove_long_silence and adjusted_end - adjusted_start > 1.0:
                    adjusted_start, adjusted_end = processor.adjust_clip_for_silence(
                        adjusted_start, adjusted_end, audio_path,
                        silence_threshold=silence_threshold,
                        buffer_duration=buffer_duration
                    )
                
                # 转换回时间字符串
                processed_clips.append({
                    **clip_data,
                    'start_time': VideoProcessor.convert_seconds_to_ffmpeg_time(adjusted_start),
                    'end_time': VideoProcessor.convert_seconds_to_ffmpeg_time(adjusted_end),
                    'silence_adjusted': True,
                    'original_start': clip_data['start_time'],
                    'original_end': clip_data['end_time']
                })
            
            # 清理临时音频文件
            audio_path.unlink(missing_ok=True)
            
            logger.info(f"静音处理完成，处理了 {len(processed_clips)} 个切片")
            return processed_clips
            
        except Exception as e:
            logger.error(f"静音处理失败: {e}")
            return clips_data
    
    @staticmethod
    def convert_seconds_to_ffmpeg_time(seconds: float) -> str:
        """
        将秒数转换为FFmpeg时间格式
        
        Args:
            seconds: 秒数
            
        Returns:
            FFmpeg时间格式 (如 "00:00:06.140")
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
    
    @staticmethod
    def convert_ffmpeg_time_to_seconds(time_str: str) -> float:
        """
        将时间格式转换为秒数
        
        Args:
            time_str: 时间格式，可以是 FFmpeg 格式 (如 "00:00:06.140") 或 SRT 格式 (如 "00:00:06,140")
            
        Returns:
            秒数
        """
        try:
            # 统一处理：将 SRT 格式的逗号替换为点号
            time_str = time_str.replace(',', '.')
            
            # 处理毫秒部分
            if '.' in time_str:
                time_part, ms_part = time_str.split('.')
                milliseconds = int(ms_part)
            else:
                time_part = time_str
                milliseconds = 0
            
            # 解析时分秒
            h, m, s = map(int, time_part.split(':'))
            
            return h * 3600 + m * 60 + s + milliseconds / 1000
        except Exception as e:
            logger.error(f"时间格式转换失败: {time_str}, 错误: {e}")
            return 0.0
    
    @staticmethod
    def extract_clip(input_video: Path, output_path: Path, 
                    start_time: str, end_time: str) -> bool:
        """
        从视频中提取指定时间段的片段
        
        Args:
            input_video: 输入视频路径
            output_path: 输出视频路径
            start_time: 开始时间 (格式: "00:01:25,140")
            end_time: 结束时间 (格式: "00:02:53,500")
            
        Returns:
            是否成功
        """
        try:
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 转换时间格式：从SRT格式转换为FFmpeg格式
            ffmpeg_start_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(start_time)
            ffmpeg_end_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(end_time)
            
            # 计算持续时间
            start_seconds = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_start_time)
            end_seconds = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_end_time)
            duration = end_seconds - start_seconds
            
            # 构建优化的FFmpeg命令
            # 使用 -ss 在输入前进行精确定位，使用 -t 指定持续时间
            cmd = [
                'ffmpeg',
                '-ss', ffmpeg_start_time,  # 在输入前定位，更精确
                '-i', str(input_video),
                '-t', str(duration),  # 使用持续时间而不是绝对结束时间
                '-c:v', 'copy',  # 复制视频流
                '-c:a', 'copy',  # 复制音频流
                '-avoid_negative_ts', 'make_zero',
                '-y',  # 覆盖输出文件
                str(output_path)
            ]
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                logger.info(f"成功提取视频片段: {output_path} ({ffmpeg_start_time} -> {ffmpeg_end_time}, 时长: {duration:.2f}秒)")
                return True
            else:
                logger.error(f"提取视频片段失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"视频处理异常: {str(e)}")
            return False
    
    @staticmethod
    def get_video_duration(video_path: Path) -> float:
        """
        获取视频的实际时长（秒）

        Args:
            video_path: 视频文件路径

        Returns:
            视频时长（秒），获取失败返回0.0
        """
        import shutil
        import re

        try:
            # 优先使用 ffprobe，如果不存在则使用 ffmpeg
            ffprobe_path = shutil.which('ffprobe')
            if ffprobe_path:
                cmd = [ffprobe_path, '-v', 'error', '-show_entries',
                       'format=duration', '-of',
                       'default=noprint_wrappers=1:nokey=1', str(video_path)]
                result = subprocess.run(cmd, capture_output=True, text=True,
                                      encoding='utf-8', errors='ignore')
                if result.returncode == 0 and result.stdout.strip():
                    return float(result.stdout.strip())
            else:
                # 使用 ffmpeg 作为替代方案
                ffmpeg_path = shutil.which('ffmpeg')
                if ffmpeg_path:
                    cmd = [ffmpeg_path, '-i', str(video_path), '-f', 'null', '-y']
                    result = subprocess.run(cmd, capture_output=True, text=True,
                                          encoding='utf-8', errors='ignore', timeout=30)
                    # 从 stderr 中解析时长
                    # 格式: Duration: 00:01:30.50, bitrate: xxx kb/s
                    output = result.stderr + result.stdout
                    match = re.search(r'Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})', output)
                    if match:
                        hours = int(match.group(1))
                        minutes = int(match.group(2))
                        seconds = int(match.group(3))
                        centiseconds = int(match.group(4))
                        return float(hours * 3600 + minutes * 60 + seconds + centiseconds / 100)
            return 0.0
        except Exception as e:
            logger.debug(f"获取视频时长失败: {e}")
            return 0.0
    
    @staticmethod
    def create_collection(clips_list: List[Path], output_path: Path) -> bool:
        """
        将多个视频片段拼接成合集
        
        Args:
            clips_list: 视频片段路径列表
            output_path: 输出合集路径
            
        Returns:
            是否成功
        """
        try:
            # 验证输入参数
            if not clips_list:
                logger.error("clips_list为空，无法创建合集")
                return False
            
            # 验证所有视频文件是否存在
            valid_clips = []
            for clip_path in clips_list:
                if not clip_path.exists():
                    logger.warning(f"视频文件不存在，跳过: {clip_path}")
                    continue
                valid_clips.append(clip_path)
            
            if not valid_clips:
                logger.error("没有有效的视频文件，无法创建合集")
                return False
            
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建concat文件
            concat_file = output_path.parent / "concat_list.txt"
            
            with open(concat_file, 'w', encoding='utf-8') as f:
                for clip_path in valid_clips:
                    # 使用绝对路径并转义单引号
                    abs_path = clip_path.absolute()
                    escaped_path = str(abs_path).replace("'", "'\"'\"'")
                    f.write(f"file '{escaped_path}'\n")
            
            # 验证concat文件内容
            if concat_file.stat().st_size == 0:
                logger.error("concat文件为空，无法创建合集")
                concat_file.unlink(missing_ok=True)
                return False
            
            # 构建FFmpeg命令 - 使用H.264编码确保兼容性
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c:v', 'libx264',  # 使用H.264视频编码
                '-preset', 'ultrafast',  # 使用最快的编码预设
                '-crf', '28',  # 稍微降低质量以加快编码速度
                '-c:a', 'aac',  # 使用AAC音频编码
                '-b:a', '128k',  # 音频比特率
                '-movflags', '+faststart',  # 优化网络播放
                '-y',
                str(output_path)
            ]
            
            logger.info(f"执行FFmpeg命令: {' '.join(cmd)}")
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            # 清理临时文件
            concat_file.unlink(missing_ok=True)
            
            if result.returncode == 0:
                logger.info(f"成功创建合集: {output_path}")
                return True
            else:
                logger.error(f"创建合集失败: {result.stderr}")
                logger.error(f"FFmpeg stdout: {result.stdout}")
                return False
                
        except Exception as e:
            logger.error(f"视频拼接异常: {str(e)}")
            return False
    
    @staticmethod
    def extract_thumbnail(video_path: Path, output_path: Path, time_offset: int = 5) -> bool:
        """
        从视频中提取缩略图
        
        Args:
            video_path: 视频文件路径
            output_path: 输出缩略图路径
            time_offset: 提取时间点（秒）
            
        Returns:
            是否成功
        """
        try:
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 构建FFmpeg命令
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-ss', str(time_offset),
                '-vframes', '1',
                '-q:v', '2',  # 高质量
                '-y',  # 覆盖输出文件
                str(output_path)
            ]
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0 and output_path.exists():
                logger.info(f"成功提取缩略图: {output_path}")
                return True
            else:
                logger.error(f"提取缩略图失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"提取缩略图异常: {str(e)}")
            return False
    
    @staticmethod
    def get_video_info(video_path: Path) -> Dict:
        """
        获取视频信息
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频信息字典
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                return {
                    'duration': float(info['format']['duration']),
                    'size': int(info['format']['size']),
                    'bitrate': int(info['format']['bit_rate']),
                    'streams': info['streams']
                }
            else:
                logger.error(f"获取视频信息失败: {result.stderr}")
                return {}
                
        except Exception as e:
            logger.error(f"获取视频信息异常: {str(e)}")
            return {}
    
    def batch_extract_clips(self, input_video: Path, clips_data: List[Dict], 
                           apply_silence_processing: bool = True,
                           use_silence_concat: bool = False) -> List[Path]:
        """
        批量提取视频片段
        
        Args:
            input_video: 输入视频路径
            clips_data: 片段数据列表，每个元素包含id、title、start_time、end_time
            apply_silence_processing: 是否应用静音处理（调整时间）
            use_silence_concat: 是否使用静音拼接器（去除长静音，保留所有语音）
            
        Returns:
            成功提取的片段路径列表
        """
        # 应用静音处理（调整时间边界）
        if apply_silence_processing and not use_silence_concat:
            clips_data = self.process_silence_for_clips(input_video, clips_data)
        
        successful_clips = []
        
        # 初始化静音拼接器（如果启用）
        silence_concat_processor = None
        if use_silence_concat and silence_concat_available:
            silence_concat_processor = SilenceConcat(
                long_silence_threshold=3.0,
                short_silence_keep=1.0,
                buffer_duration=0.2
            )
        
        for clip_data in clips_data:
            clip_id = clip_data['id']
            title = clip_data.get('title', f"片段_{clip_id}")
            start_time = clip_data['start_time']
            end_time = clip_data['end_time']
            
            # 转换为秒数（用于静音拼接器）
            clip_start_sec = start_time
            clip_end_sec = end_time
            if isinstance(start_time, str):
                clip_start_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(start_time)
            if isinstance(end_time, str):
                clip_end_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(end_time)
            
            # 使用标题作为文件名，并清理不合法的字符
            safe_title = VideoProcessor.sanitize_filename(title)
            output_path = self.clips_dir / f"{clip_id}_{safe_title}.mp4"
            
            logger.info(f"提取切片 {clip_id}: {start_time} -> {end_time}, 输出: {output_path}")
            
            # 使用静音拼接器处理（去除长静音）
            if silence_concat_processor:
                success = silence_concat_processor.process_clip(
                    input_video=input_video,
                    output_video=output_path,
                    clip_start=clip_start_sec,
                    clip_end=clip_end_sec,
                    clip_id=clip_id
                )
            else:
                # 处理时间格式 - 如果是秒数，转换为FFmpeg格式
                if isinstance(start_time, (int, float)):
                    start_time = VideoProcessor.convert_seconds_to_ffmpeg_time(start_time)
                if isinstance(end_time, (int, float)):
                    end_time = VideoProcessor.convert_seconds_to_ffmpeg_time(end_time)
                
                success = VideoProcessor.extract_clip(input_video, output_path, start_time, end_time)
            
            if success:
                successful_clips.append(output_path)
                actual_duration = VideoProcessor.get_video_duration(output_path)
                if actual_duration > 0:
                    clip_data['duration'] = actual_duration
                    logger.debug(f"切片 {clip_id} 实际时长: {actual_duration:.3f}s")
                logger.info(f"切片 {clip_id} 提取成功")
            else:
                logger.error(f"切片 {clip_id} 提取失败")
        
        return successful_clips
    
    def _calculate_optimal_threads(self, clips_count: int) -> int:
        """
        根据服务器配置自动计算最优线程数
        
        Args:
            clips_count: 待处理的切片数量
            
        Returns:
            最优线程数
        """
        try:
            import psutil
            
            # 获取CPU核心数
            cpu_cores = psutil.cpu_count(logical=True) or 4
            
            # 获取可用内存（GB）
            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024 ** 3)
            
            # 判断磁盘类型：通过读取速度判断是否为SSD
            # SSD通常读取速度 > 100MB/s，机械硬盘通常 < 50MB/s
            disk_io = psutil.disk_io_counters()
            if disk_io.read_time > 0:
                read_speed = disk_io.read_bytes / disk_io.read_time / 1024  # KB/s
                is_ssd = read_speed > 50 * 1024  # > 50MB/s 认为是SSD
            else:
                # 默认假设是SSD
                is_ssd = True
            
            # 基础线程数 = CPU核心数的一半（留一半给系统和其他任务）
            base_threads = max(2, cpu_cores // 2)
            
            # 根据磁盘类型调整
            if is_ssd:
                disk_factor = 2.0
                logger.debug(f"检测到SSD，磁盘因子: {disk_factor}")
            else:
                disk_factor = 0.5
                logger.debug(f"检测到机械硬盘，磁盘因子: {disk_factor}")
            
            # 根据内存调整
            if available_gb < 4:
                memory_factor = 0.5
            elif available_gb < 8:
                memory_factor = 0.75
            else:
                memory_factor = 1.0
            logger.debug(f"可用内存: {available_gb:.1f}GB，内存因子: {memory_factor}")
            
            # 计算最优线程数
            optimal_threads = int(base_threads * disk_factor * memory_factor)
            
            # 确保线程数在合理范围内
            min_threads = 1
            max_threads = min(clips_count, cpu_cores, 16)  # 最大16线程
            
            result = max(min_threads, min(optimal_threads, max_threads))
            logger.info(f"自动计算最优线程数: {result} (CPU: {cpu_cores}核, 内存: {available_gb:.1f}GB, 磁盘: {'SSD' if is_ssd else 'HDD'})")
            
            return result
            
        except ImportError:
            # 如果没有psutil，返回默认值
            logger.debug("psutil未安装，使用默认线程数")
            return min(4, clips_count)
        except Exception as e:
            # 出现异常时返回默认值
            logger.debug(f"计算最优线程数失败: {e}，使用默认线程数")
            return min(4, clips_count)
    
    def batch_extract_clips_parallel(self, input_video: Path, clips_data: List[Dict],
                                    apply_silence_processing: bool = True,
                                    max_workers: int = None,
                                    progress_callback=None) -> List[Path]:
        """
        并行批量提取视频片段（使用多线程同时处理多个切片）
        
        Args:
            input_video: 输入视频路径
            clips_data: 片段数据列表，每个元素包含id、title、start_time、end_time
            apply_silence_processing: 是否应用静音处理（调整时间）
            max_workers: 最大并发线程数，默认None（自动根据服务器配置计算）
            progress_callback: 进度回调函数，接收 (completed_count, total_count, clip_id, success)
        
        Returns:
            成功提取的片段路径列表
        
        性能优化策略:
            1. 自动检测服务器配置（CPU核心数、内存、磁盘类型）
            2. SSD自动使用更高并行度，机械硬盘自动降低并行度
            3. 内存不足时自动减少线程数
            4. 切片数量较少时自动使用串行处理
        
        注意事项:
            - 并行处理会增加系统资源消耗，但已自动适配服务器配置
            - 静音处理在并行前统一完成（串行执行），然后并行提取切片
            - 如果需要使用静音拼接器（use_silence_concat），请使用串行版本
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed, Future
        import time
        
        # 应用静音处理（在并行前串行执行）
        if apply_silence_processing:
            clips_data = self.process_silence_for_clips(input_video, clips_data)
        
        total_clips = len(clips_data)
        successful_clips: List[Path] = []
        completed_count = 0
        
        if total_clips == 0:
            logger.warning("没有切片需要处理")
            return successful_clips
        
        # 如果切片数量较少，使用串行处理（避免线程开销）
        if total_clips <= 2:
            logger.info(f"切片数量较少({total_clips}个)，使用串行处理")
            return self.batch_extract_clips(input_video, clips_data, 
                                          apply_silence_processing=False)
        
        # 自动计算最优线程数（如果未指定）
        if max_workers is None:
            max_workers = self._calculate_optimal_threads(total_clips)
        
        # 检测磁盘类型，决定是否添加IO延迟
        need_io_delay = False
        try:
            import psutil
            disk_io = psutil.disk_io_counters()
            if disk_io.read_time > 0:
                read_speed = disk_io.read_bytes / disk_io.read_time / 1024
                need_io_delay = read_speed <= 50 * 1024  # < 50MB/s 认为是机械硬盘
        except Exception:
            pass
        
        logger.info(f"开始并行提取 {total_clips} 个切片，使用 {max_workers} 个线程{'（机械硬盘模式）' if need_io_delay else ''}")
        
        def _extract_clip_wrapper(clip_data: Dict) -> Tuple[str, bool, str, Optional[Path]]:
            """切片提取包装函数，用于线程池执行"""
            clip_id = clip_data['id']
            title = clip_data.get('title', f"片段_{clip_id}")
            start_time = clip_data['start_time']
            end_time = clip_data['end_time']
            
            # 转换为秒数
            clip_start_sec = start_time
            clip_end_sec = end_time
            if isinstance(start_time, str):
                clip_start_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(start_time)
            if isinstance(end_time, str):
                clip_end_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(end_time)
            
            # 使用标题作为文件名
            safe_title = VideoProcessor.sanitize_filename(title)
            output_path = self.clips_dir / f"{clip_id}_{safe_title}.mp4"
            
            logger.debug(f"线程开始处理切片 {clip_id}: {start_time} -> {end_time}")
            
            # 处理时间格式
            if isinstance(start_time, (int, float)):
                start_time = VideoProcessor.convert_seconds_to_ffmpeg_time(start_time)
            if isinstance(end_time, (int, float)):
                end_time = VideoProcessor.convert_seconds_to_ffmpeg_time(end_time)
            
            success = VideoProcessor.extract_clip(input_video, output_path, start_time, end_time)
            
            # 机械硬盘模式：添加IO延迟，避免磁盘过载
            if need_io_delay:
                time.sleep(0.1)  # 100ms延迟
            
            if success:
                # 获取实际视频时长并更新 clip_data
                actual_duration = VideoProcessor.get_video_duration(output_path)
                if actual_duration > 0:
                    clip_data['duration'] = actual_duration
                    logger.debug(f"切片 {clip_id} 实际时长: {actual_duration:.3f}s")
                return str(clip_id), True, "提取成功", output_path
            else:
                return str(clip_id), False, "提取失败", None
        
        # 创建线程池
        with ThreadPoolExecutor(max_workers=max_workers,
                               thread_name_prefix="VideoClipWorker") as executor:
            # 提交所有任务
            future_to_clip: Dict[Future, str] = {}
            
            for clip_data in clips_data:
                future = executor.submit(_extract_clip_wrapper, clip_data)
                future_to_clip[future] = str(clip_data['id'])
            
            # 处理完成的任务
            for future in as_completed(future_to_clip):
                clip_id = future_to_clip[future]
                try:
                    result_clip_id, success, message, output_path = future.result()
                    
                    if success and output_path:
                        successful_clips.append(output_path)
                    
                    # 更新进度
                    completed_count += 1
                    if progress_callback:
                        progress_callback(completed_count, total_clips, clip_id, success)
                    
                    # 记录结果
                    status = "成功" if success else "失败"
                    logger.info(f"[{completed_count}/{total_clips}] 切片 {clip_id} {status}")
                    
                except Exception as e:
                    completed_count += 1
                    logger.error(f"[{completed_count}/{total_clips}] 切片 {clip_id} 处理异常: {str(e)}")
                    if progress_callback:
                        progress_callback(completed_count, total_clips, clip_id, False)
        
        logger.info(f"并行提取完成，成功 {len(successful_clips)}/{total_clips} 个切片")
        return successful_clips
    
    def create_collections_from_metadata(self, collections_data: List[Dict]) -> List[Path]:
        """
        根据元数据创建合集
        
        Args:
            collections_data: 合集数据列表
            
        Returns:
            成功创建的合集路径列表
        """
        successful_collections = []
        
        for collection_data in collections_data:
            collection_id = collection_data['id']
            collection_title = collection_data.get('collection_title', f'合集_{collection_id}')
            clip_ids = collection_data['clip_ids']
            
            # 构建片段路径列表
            clips_list = []
            for clip_id in clip_ids:
                # 查找对应的切片文件
                # 新的文件名格式是: {clip_id}_{title}.mp4
                clip_path = self.clips_dir / f"{clip_id}_*.mp4"
                found_clips = list(self.clips_dir.glob(f"{clip_id}_*.mp4"))
                
                if found_clips:
                    found_clip = found_clips[0]  # 取第一个匹配的文件
                    clips_list.append(found_clip)
                    logger.info(f"找到合集 {collection_id} 的切片: {found_clip.name}")
                else:
                    logger.warning(f"未找到合集 {collection_id} 的切片 {clip_id}")
            
            if clips_list:
                # 使用collection_title作为文件名，并清理不合法的字符
                safe_title = VideoProcessor.sanitize_filename(collection_title)
                output_path = self.collections_dir / f"{safe_title}.mp4"
                
                if VideoProcessor.create_collection(clips_list, output_path):
                    successful_collections.append(output_path)
                    logger.info(f"成功创建合集 {collection_id}: {output_path}")
            else:
                logger.warning(f"合集 {collection_id} 没有找到任何有效的切片文件")
        
        return successful_collections
    
    @staticmethod
    def _find_ffprobe_path() -> Optional[str]:
        """
        查找ffprobe可执行文件路径
        按优先级搜索：环境变量PATH > ffmpeg所在目录 > 常见安装路径
        """
        import shutil
        
        # 1. 首先尝试直接查找
        ffprobe_path = shutil.which('ffprobe')
        if ffprobe_path:
            return ffprobe_path
        
        # 2. 尝试查找ffmpeg目录（ffprobe通常和ffmpeg在一起）
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            ffmpeg_dir = Path(ffmpeg_path).parent
            ffprobe_candidate = ffmpeg_dir / 'ffprobe.exe' if os.name == 'nt' else ffmpeg_dir / 'ffprobe'
            if ffprobe_candidate.exists():
                return str(ffprobe_candidate)
        
        # 3. 搜索常见安装路径（包含用户已安装的路径）
        common_paths = [
            'C:\\ffmpeg\\bin\\ffprobe.exe',
            'C:\\Program Files\\ffmpeg\\bin\\ffprobe.exe',
            'C:\\Program Files (x86)\\ffmpeg\\bin\\ffprobe.exe',
            '/usr/local/bin/ffprobe',
            '/usr/bin/ffprobe',
            # 用户已安装的路径
            'D:\\software\\install\\ffprobe.exe',
            'D:\\software\\install\\bin\\ffprobe.exe',
        ]
        
        for path in common_paths:
            if Path(path).exists():
                return path
        
        return None
    
    @staticmethod
    def _find_ffmpeg_path() -> Optional[str]:
        """
        查找ffmpeg可执行文件路径
        """
        import shutil
        
        # 1. 首先尝试直接查找
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            return ffmpeg_path
        
        # 2. 搜索常见安装路径
        common_paths = [
            'C:\\ffmpeg\\bin\\ffmpeg.exe',
            'C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe',
            'C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe',
            '/usr/local/bin/ffmpeg',
            '/usr/bin/ffmpeg',
            # 用户已安装的路径
            'D:\\software\\install\\ffmpeg.exe',
        ]
        
        for path in common_paths:
            if Path(path).exists():
                return path
        
        return None
    
    @staticmethod
    def _detect_video_info(video_path: Path) -> Dict:
        """
        检测视频编码详细信息
        支持自动查找ffprobe路径，如果找不到则使用ffmpeg作为后备方案
        """
        # 首先尝试使用ffprobe
        result = VideoProcessor._detect_video_info_with_ffprobe(video_path)
        if result:
            return result
        
        # ffprobe不可用，尝试使用ffmpeg作为后备方案
        logger.info("ffprobe不可用，尝试使用ffmpeg获取视频信息")
        result = VideoProcessor._detect_video_info_with_ffmpeg(video_path)
        if result:
            return result
        
        # 两者都不可用，返回空字典（将回退到重新编码）
        logger.warning("ffprobe和ffmpeg都无法获取视频信息，将使用重新编码模式")
        return {}
    
    @staticmethod
    def _detect_video_info_with_ffprobe(video_path: Path) -> Dict:
        """
        使用ffprobe检测视频编码详细信息
        """
        try:
            ffprobe_path = VideoProcessor._find_ffprobe_path()
            
            if not ffprobe_path:
                logger.debug("ffprobe未找到")
                return {}
            
            cmd = [
                ffprobe_path, '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-show_format', str(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                logger.debug(f"ffprobe命令执行失败: {result.stderr}")
                return {}
            
            info = json.loads(result.stdout)
            
            video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
            audio_stream = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
            
            def _parse_fps(frame_rate: str) -> float:
                if '/' in frame_rate:
                    num, den = map(int, frame_rate.split('/'))
                    return num / den
                return float(frame_rate)
            
            return {
                'width': int(video_stream['width']) if video_stream else 0,
                'height': int(video_stream['height']) if video_stream else 0,
                'video_codec': video_stream['codec_name'] if video_stream else '',
                'audio_codec': audio_stream['codec_name'] if audio_stream else '',
                'fps': _parse_fps(video_stream['r_frame_rate']) if video_stream else 0,
                'duration': float(info.get('format', {}).get('duration', 0)),
                'bitrate': int(info.get('format', {}).get('bit_rate', 0))
            }
        except Exception as e:
            logger.debug(f"使用ffprobe检测视频信息异常: {e}")
            return {}
    
    @staticmethod
    def _detect_video_info_with_ffmpeg(video_path: Path) -> Dict:
        """
        使用ffmpeg检测视频编码详细信息（后备方案）
        通过解析ffmpeg -i输出获取基本信息
        """
        try:
            ffmpeg_path = VideoProcessor._find_ffmpeg_path()
            
            if not ffmpeg_path:
                logger.debug("ffmpeg未找到")
                return {}
            
            # 使用ffmpeg -i获取视频信息，重定向stderr到stdout
            cmd = [ffmpeg_path, '-i', str(video_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            # ffmpeg -i返回非零退出码是正常的，我们只关心stderr输出
            output = result.stderr if result.stderr else result.stdout
            
            if not output:
                logger.debug("ffmpeg没有输出")
                return {}
            
            return VideoProcessor._parse_ffmpeg_output(output)
        
        except Exception as e:
            logger.debug(f"使用ffmpeg检测视频信息异常: {e}")
            return {}
    
    @staticmethod
    def _parse_ffmpeg_output(output: str) -> Dict:
        """
        解析ffmpeg -i的输出，提取视频信息
        """
        info = {}
        
        # 匹配视频流信息（确保匹配的是分辨率，而不是十六进制代码）
        video_pattern = re.compile(r'Stream.*Video:\s*([a-zA-Z0-9_]+).*?,\s*(\d+)x(\d+)\s')
        video_match = video_pattern.search(output)
        if video_match:
            info['video_codec'] = video_match.group(1)
            info['width'] = int(video_match.group(2))
            info['height'] = int(video_match.group(3))
        
        # 匹配音频流信息
        audio_pattern = re.compile(r'Stream.*Audio:\s*([a-zA-Z0-9_]+)')
        audio_match = audio_pattern.search(output)
        if audio_match:
            info['audio_codec'] = audio_match.group(1)
        
        # 匹配时长信息
        duration_pattern = re.compile(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)')
        duration_match = duration_pattern.search(output)
        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2))
            seconds = float(duration_match.group(3))
            info['duration'] = hours * 3600 + minutes * 60 + seconds
        
        # 匹配帧率信息
        fps_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*fps')
        fps_match = fps_pattern.search(output)
        if fps_match:
            info['fps'] = float(fps_match.group(1))
        
        # 匹配比特率信息
        bitrate_pattern = re.compile(r'(\d+)\s*kb/s')
        bitrate_match = bitrate_pattern.search(output)
        if bitrate_match:
            info['bitrate'] = int(bitrate_match.group(1)) * 1000
        
        logger.debug(f"从ffmpeg输出解析到的视频信息: {info}")
        return info
    
    @staticmethod
    def _verify_codec_consistency(video_infos: List[Dict]) -> bool:
        """
        验证所有视频是否可以流复制拼接
        """
        if not video_infos:
            return False
        
        reference = video_infos[0]
        
        for info in video_infos[1:]:
            if (info['video_codec'] != reference['video_codec'] or
                info['width'] != reference['width'] or
                info['height'] != reference['height'] or
                abs(info['fps'] - reference['fps']) > 0.1 or
                info['audio_codec'] != reference['audio_codec']):
                return False
        
        return True
    
    @staticmethod
    def _execute_ffmpeg_with_retry(cmd: List[str], max_retries: int = 3, 
                                  description: str = "FFmpeg操作") -> bool:
        """
        带重试机制的FFmpeg命令执行
        """
        for attempt in range(max_retries):
            logger.info(f"执行 {description} (尝试 {attempt + 1}/{max_retries})")
            
            try:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    encoding='utf-8', 
                    errors='ignore',
                    timeout=300
                )
                
                if result.returncode == 0:
                    logger.info(f"{description}成功")
                    return True
                
                stderr = result.stderr.lower()
                
                if 'invalid data found' in stderr or 'codec not found' in stderr:
                    logger.warning(f"检测到编码错误，调整参数重试")
                    cmd = VideoProcessor._adjust_params_for_codec_error(cmd)
                
                elif 'out of memory' in stderr:
                    logger.warning(f"检测到内存不足，降低编码质量重试")
                    cmd = VideoProcessor._adjust_params_for_memory_error(cmd)
                
                else:
                    logger.error(f"{description}失败: {result.stderr}")
                    if attempt == max_retries - 1:
                        VideoProcessor._save_debug_info(cmd, result, description)
            
            except subprocess.TimeoutExpired:
                logger.warning(f"{description}超时，重试")
                cmd = VideoProcessor._adjust_params_for_timeout(cmd)
            
            except Exception as e:
                logger.error(f"{description}异常: {e}")
        
        return False
    
    @staticmethod
    def _adjust_params_for_codec_error(cmd: List[str]) -> List[str]:
        """调整参数应对编码错误"""
        new_cmd = []
        i = 0
        while i < len(cmd):
            if cmd[i] == '-c:v' and i + 1 < len(cmd):
                if cmd[i + 1] == 'copy':
                    new_cmd.extend(['-c:v', 'libx264', '-preset', 'fast'])
                    i += 2
                    continue
            elif cmd[i] == '-c:a' and i + 1 < len(cmd):
                if cmd[i + 1] == 'copy':
                    new_cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
                    i += 2
                    continue
            new_cmd.append(cmd[i])
            i += 1
        return new_cmd
    
    @staticmethod
    def _adjust_params_for_memory_error(cmd: List[str]) -> List[str]:
        """调整参数应对内存不足"""
        new_cmd = []
        i = 0
        while i < len(cmd):
            if cmd[i] == '-crf' and i + 1 < len(cmd):
                current_crf = int(cmd[i + 1])
                new_cmd.extend(['-crf', str(min(current_crf + 3, 35))])
                i += 2
                continue
            elif cmd[i] == '-preset' and i + 1 < len(cmd):
                new_cmd.extend(['-preset', 'ultrafast'])
                i += 2
                continue
            new_cmd.append(cmd[i])
            i += 1
        return new_cmd
    
    @staticmethod
    def _adjust_params_for_timeout(cmd: List[str]) -> List[str]:
        """调整参数应对超时"""
        return VideoProcessor._adjust_params_for_memory_error(cmd)
    
    @staticmethod
    def _save_debug_info(cmd: List[str], result: subprocess.CompletedProcess, description: str):
        """保存调试信息"""
        debug_dir = Path('debug')
        debug_dir.mkdir(exist_ok=True)
        debug_file = debug_dir / f"ffmpeg_debug_{int(time.time())}.txt"
        
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(f"描述: {description}\n")
            f.write(f"命令: {' '.join(cmd)}\n")
            f.write(f"\nSTDOUT:\n{result.stdout}\n")
            f.write(f"\nSTDERR:\n{result.stderr}\n")
            f.write(f"\n返回码: {result.returncode}\n")
        
        logger.info(f"调试信息已保存到: {debug_file}")
    
    @staticmethod
    def create_collection_fast(clips_list: List[Path], output_path: Path) -> bool:
        """
        使用流复制模式快速拼接视频（无需重新编码）
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            concat_file = output_path.parent / "concat_list.txt"
            with open(concat_file, 'w', encoding='utf-8') as f:
                for clip_path in clips_list:
                    abs_path = clip_path.absolute()
                    escaped_path = str(abs_path).replace("'", "'\"'\"'")
                    f.write(f"file '{escaped_path}'\n")
            
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c:v', 'copy',
                '-c:a', 'copy',
                '-movflags', '+faststart',
                '-y',
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            concat_file.unlink(missing_ok=True)
            
            if result.returncode == 0:
                logger.info(f"快速拼接成功: {output_path}")
                return True
            else:
                logger.warning(f"流复制失败，回退到重新编码: {result.stderr}")
                return VideoProcessor.create_collection(clips_list, output_path)
                
        except Exception as e:
            logger.error(f"快速拼接异常: {e}")
            return False
    
    @staticmethod
    def create_collection_adaptive(clips_list: List[Path], output_path: Path, 
                                  use_transition: bool = False) -> bool:
        """
        自适应视频拼接
        自动检测编码参数，选择最佳拼接策略
        """
        if not clips_list:
            logger.error("clips_list为空")
            return False
        
        # 检测所有视频的编码信息
        video_infos = [VideoProcessor._detect_video_info(clip) for clip in clips_list]
        
        # 过滤无效信息
        valid_infos = [info for info in video_infos if info]
        
        if not valid_infos:
            logger.error("无法获取视频编码信息")
            return False
        
        # 选择拼接策略
        can_stream_copy = VideoProcessor._verify_codec_consistency(valid_infos)
        
        if can_stream_copy and not use_transition:
            return VideoProcessor.create_collection_fast(clips_list, output_path)
        elif use_transition:
            return VideoProcessor.create_collection_with_transition(clips_list, output_path)
        else:
            return VideoProcessor.create_collection(clips_list, output_path)
    
    @staticmethod
    def create_collection_with_transition(clips_list: List[Path], output_path: Path, 
                                         transition_duration: float = 0.5) -> bool:
        """
        带淡入淡出转场效果的拼接
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if len(clips_list) < 2:
                # 单个视频直接复制
                cmd = [
                    'ffmpeg',
                    '-i', str(clips_list[0]),
                    '-c:v', 'copy',
                    '-c:a', 'copy',
                    '-y',
                    str(output_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                return result.returncode == 0
            
            # 构建FFmpeg命令
            # 使用xfade滤镜实现转场效果
            filter_complex_parts = []
            input_maps = []
            
            # 为每个输入创建映射
            for i, _ in enumerate(clips_list):
                input_maps.append(f"[{i}:v][{i}:a]")
            
            # 添加转场滤镜
            # 使用xfade实现淡入淡出转场
            filter_complex_parts.append(f"[{0}:v][{1}:v]xfade=transition=fade:duration={transition_duration}[v01]")
            
            for i in range(2, len(clips_list)):
                filter_complex_parts.append(f"[v{i-2}{i-1}][{i}:v]xfade=transition=fade:duration={transition_duration}[v{i-1}{i}]")
            
            # 音频处理：交叉淡入
            audio_filter = []
            for i in range(len(clips_list) - 1):
                audio_filter.append(f"[{i}:a]afade=out:st=0:d={transition_duration}[a{i}out]")
                audio_filter.append(f"[{i+1}:a]afade=in:st=0:d={transition_duration}[a{i+1}in]")
            
            # 构建完整命令
            cmd = [
                'ffmpeg',
                *sum([['-i', str(c)] for c in clips_list], []),
                '-filter_complex', ';'.join(filter_complex_parts + audio_filter),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                logger.info(f"带转场效果拼接成功: {output_path}")
                return True
            else:
                logger.error(f"转场拼接失败: {result.stderr}")
                # 回退到普通拼接
                return VideoProcessor.create_collection(clips_list, output_path)
                
        except Exception as e:
            logger.error(f"转场拼接异常: {e}")
            return VideoProcessor.create_collection(clips_list, output_path)