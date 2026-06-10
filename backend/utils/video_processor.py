"""
视频处理工具
"""
import subprocess
import json
import logging
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# 修复导入问题
try:
    from ..core.shared_config import CLIPS_DIR, COLLECTIONS_DIR
    from .keyframe_aligner import KeyframeAligner
    from .silence_concat import SilenceConcat
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from ..core.shared_config import CLIPS_DIR, COLLECTIONS_DIR
    from .keyframe_aligner import KeyframeAligner
    from .silence_concat import SilenceConcat

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
        将FFmpeg时间格式转换为秒数
        
        Args:
            time_str: FFmpeg时间格式 (如 "00:00:06.140")
            
        Returns:
            秒数
        """
        try:
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
        从视频中提取指定时间段的片段（帧精确模式）

        Args:
            input_video: 输入视频路径
            output_path: 输出视频路径
            start_time: 开始时间 (格式: "00:01:25,140")
            end_time: 结束时间 (格式: "00:02:53,500")

        Returns:
            是否成功
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 解析并规范时间为秒数（支持SRT或FFmpeg时间格式）
            start_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(
                VideoProcessor.convert_srt_time_to_ffmpeg_time(str(start_time))
            )
            end_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(
                VideoProcessor.convert_srt_time_to_ffmpeg_time(str(end_time))
            )

            # 获取视频总时长并对时间进行边界校验和修正
            video_info = VideoProcessor.get_video_info(input_video)
            video_duration = None
            if video_info and 'duration' in video_info:
                video_duration = float(video_info['duration'])

            # 如果视频时长已知，进行 clamp
            min_duration = 1.0  # 最小切片时长（秒）
            if video_duration is not None:
                # 如果 start 在视频之外，移动到视频尾部留出最小时长
                if start_sec >= video_duration:
                    logger.warning(
                        f"切片开始时间 ({start_sec}) 超出视频总时长 ({video_duration})，将开始时间调整到视频尾部 - {min_duration}s 的位置"
                    )
                    start_sec = max(0.0, video_duration - min_duration)
                    end_sec = video_duration

                # 如果 end 超出视频时长，截断到视频时长
                if end_sec > video_duration:
                    logger.warning(
                        f"切片结束时间 ({end_sec}) 超出视频总时长 ({video_duration})，将结束时间截断到视频总时长"
                    )
                    end_sec = video_duration

            # 校验时间合法性：确保 end > start
            if end_sec <= start_sec + 1e-6:
                # 如果结束时间不大于开始时间，则扩展到最小持续时间并记录警告
                logger.warning(
                    f"切片时间不合法或时长为0 (start={start_time}, end={end_time})，自动扩展到 {min_duration}s"
                )
                end_sec = start_sec + min_duration

                # 如果扩展后仍然超出视频总时长，则将区间移动到视频尾部
                if video_duration is not None and end_sec > video_duration:
                    start_sec = max(0.0, video_duration - min_duration)
                    end_sec = video_duration

            duration = end_sec - start_sec

            # 格式化为FFmpeg时间字符串（使用点号作为小数分隔符）
            ffmpeg_start_time = VideoProcessor.convert_seconds_to_ffmpeg_time(start_sec)
            ffmpeg_duration = f"{duration:.3f}"

            # 流拷贝切割：KeyframeAligner已确保边界对齐到关键帧，
            # 使用 -c copy 避免重编码，速度从分钟级降到秒级
            cmd = [
                'ffmpeg',
                '-ss', ffmpeg_start_time,
                '-i', str(input_video),
                '-t', ffmpeg_duration,
                '-c', 'copy',
                '-y',
                str(output_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')

            if result.returncode == 0:
                ffmpeg_end_time = VideoProcessor.convert_seconds_to_ffmpeg_time(end_sec)
                logger.info(
                    f"成功提取视频片段: {output_path} ({ffmpeg_start_time} -> {ffmpeg_end_time}, 时长: {duration:.2f}秒)"
                )
                return True
            else:
                logger.error(f"提取视频片段失败: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"视频处理异常: {str(e)}")
            return False
    
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
    
    @staticmethod
    def _deduplicate_aligned_boundaries(aligned_clips: List[Dict]) -> List[Dict]:
        """
        关键帧对齐后的相邻切片去重叠处理 + 间隙保护。

        功能：
          1. 去重叠：当切片N的对齐结束时间 > 切片N+1的对齐开始时间时，在中间点分割
          2. 间隙保护：当LLM输出在两个切片间留有间隙（即原边界处有被排除的内容）时，
             阻止关键帧对齐将任何切片扩张到间隙中。

        Args:
            aligned_clips: 关键帧对齐后的切片数据列表

        Returns:
            去重叠+间隙保护后的切片数据列表
        """
        if len(aligned_clips) < 2:
            return aligned_clips

        def _to_seconds(t: object) -> float:
            if isinstance(t, (int, float)):
                return float(t)
            if isinstance(t, str):
                t_str = t.replace(',', '.')
                parts = t_str.split(':')
                if len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                try:
                    return float(t_str)
                except (ValueError, TypeError):
                    return 0.0
            return 0.0

        def _to_time_str(sec: float) -> str:
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = sec % 60
            ms = int(round((s - int(s)) * 1000))
            return f"{h:02d}:{m:02d}:{int(s):02d}.{ms:03d}"

        # 按开始时间排序（确保处理顺序）
        sorted_clips = sorted(aligned_clips, key=lambda c: _to_seconds(c.get('start_time', 0)))

        any_fixed = False
        for i in range(len(sorted_clips) - 1):
            cur = sorted_clips[i]
            nxt = sorted_clips[i + 1]

            cur_end_sec = _to_seconds(cur['end_time'])
            nxt_start_sec = _to_seconds(nxt['start_time'])
            cur_orig_end_sec = _to_seconds(cur.get('original_end', cur['end_time']))
            nxt_orig_start_sec = _to_seconds(nxt.get('original_start', nxt['start_time']))

            # ── 间隙保护 ──
            # LLM 在两个 clip 之间留有间隙(original_end_N < original_start_N+1)，
            # 说明间隙中的内容被 LLM 明确排除。
            # 关键帧对齐不应让任何 clip 扩张到间隙中。
            if cur_orig_end_sec < nxt_orig_start_sec:
                if cur_end_sec > cur_orig_end_sec:
                    new_cur_end = _to_time_str(max(cur_orig_end_sec - 0.05, 0.0))
                    logger.info(
                        f"间隙保护: Clip {cur.get('id','?')} end {cur['end_time']} → {new_cur_end}, "
                        f"原边界 {cur.get('original_end','?')}"
                    )
                    cur['end_time'] = new_cur_end
                    cur_end_sec = cur_orig_end_sec  # 更新用于后续去重叠判断
                    any_fixed = True
                if nxt_start_sec < nxt_orig_start_sec:
                    new_nxt_start = _to_time_str(nxt_orig_start_sec + 0.05)
                    logger.info(
                        f"间隙保护: Clip {nxt.get('id','?')} start {nxt['start_time']} → {new_nxt_start}, "
                        f"原边界 {nxt.get('original_start','?')}"
                    )
                    nxt['start_time'] = new_nxt_start
                    nxt_start_sec = nxt_orig_start_sec  # 更新用于后续去重叠判断
                    any_fixed = True

            # ── 去重叠（间隙保护后仍需检查，因为原始边界也可能重叠） ──
            if nxt_start_sec >= cur_end_sec:
                continue

            # 存在重叠 → 优先尝试恢复到原始边界
            # 中点分割在关键帧间隔较大时，分割点仍可能落在另一话题区域内
            new_cur_end_candidate = min(cur_end_sec, cur_orig_end_sec)
            new_nxt_start_candidate = max(nxt_start_sec, nxt_orig_start_sec)

            if new_cur_end_candidate <= new_nxt_start_candidate:
                # 恢复到原始边界后无重叠（或相邻）→ 使用原始边界
                new_cur_end = _to_time_str(max(new_cur_end_candidate - 0.05, 0.0))
                new_nxt_start = _to_time_str(new_nxt_start_candidate + 0.05)
                logger.info(
                    f"去重叠(恢复原边界): Clip {cur.get('id','?')} end {cur['end_time']} → {new_cur_end}, "
                    f"Clip {nxt.get('id','?')} start {nxt['start_time']} → {new_nxt_start}"
                )
            else:
                # 原始边界本身也重叠 → 在中间点分割
                mid = (cur_end_sec + nxt_start_sec) / 2.0
                new_cur_end = _to_time_str(mid - 0.05)
                new_nxt_start = _to_time_str(mid + 0.05)
                logger.info(
                    f"去重叠(中点分割): Clip {cur.get('id','?')} end {cur['end_time']} → {new_cur_end}, "
                    f"Clip {nxt.get('id','?')} start {nxt['start_time']} → {new_nxt_start}, "
                    f"重叠量 {cur_end_sec - nxt_start_sec:.2f}s"
                )

            cur['end_time'] = new_cur_end
            nxt['start_time'] = new_nxt_start
            any_fixed = True

        if any_fixed:
            logger.info("关键帧对齐后处理完成（去重+间隙保护）")
        return sorted_clips

    def batch_extract_clips(
        self,
        input_video: Path,
        clips_data: List[Dict],
        apply_silence_processing: bool = True,
        full_audio_vad_path: Optional[Path] = None,  # ← 新增
    ) -> Tuple[List[Path], List[Dict]]:
        """
        批量提取视频片段（支持关键帧对齐 + 静音移除后处理）

        Args:
            input_video: 输入视频路径
            clips_data: 片段数据列表
            apply_silence_processing: 是否对提取后的切片应用静音移除处理
            full_audio_vad_path: .vad.json 路径（P1 预计算 VAD 结果）

        Returns:
            元组 (成功提取的片段路径列表, 处理后的片段数据列表)
        """
        successful_clips = []
        processed_clips_data = []

        try:
            cache_dir = input_video.parent / ".keyframe_cache"
            keyframe_aligner = KeyframeAligner(input_video, cache_dir=cache_dir)
            keyframe_aligner.ensure_initialized()
            aligned_clips_data = keyframe_aligner.align_clips(clips_data, strategy="balanced")
            logger.info(f"关键帧对齐完成，共{len(aligned_clips_data)}个切片")
            # 关键帧对齐后去重叠：防止相邻切片因各自对齐关键帧而产生内容重叠
            aligned_clips_data = VideoProcessor._deduplicate_aligned_boundaries(aligned_clips_data)
            logger.info(f"边界去重叠完成，共{len(aligned_clips_data)}个切片")
        except Exception as e:
            logger.warning(f"关键帧对齐失败，将使用原始时间: {e}")
            aligned_clips_data = clips_data

        # 加载 P1 VAD 结果（如果提供）
        full_audio_vad = None
        if full_audio_vad_path and full_audio_vad_path.exists():
            try:
                from backend.utils.silero_vad_wrapper import SileroVADWrapper
                full_audio_vad = SileroVADWrapper.load_vad_json(full_audio_vad_path)
                logger.info(f"加载 P1 VAD 结果: {len(full_audio_vad)} 段语音, 来源: {full_audio_vad_path}")
            except Exception as e:
                logger.warning(f"加载 VAD 结果失败: {e}，将使用 FFmpeg 回退")

        # 初始化静音处理器（如果需要）
        silence_processor = None
        if apply_silence_processing:
            try:
                silence_processor = SilenceConcat(
                    long_silence_threshold=1.0,
                    short_silence_keep=0.8,
                    buffer_duration=0.2,
                    silence_threshold_db=-35.0,
                )
                logger.info("静音处理器初始化成功")
            except Exception as e:
                logger.warning(f"静音处理器初始化失败，将跳过静音处理: {e}")
                silence_processor = None

        for clip_data in aligned_clips_data:
            clip_id = clip_data['id']
            title = clip_data.get('title', f"片段_{clip_id}")
            start_time = clip_data['start_time']
            end_time = clip_data['end_time']
            original_start = clip_data.get('original_start', start_time)
            original_end = clip_data.get('original_end', end_time)

            # 记录原始秒数（用于 VAD 坐标映射）
            try:
                raw_start_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(
                    VideoProcessor.convert_srt_time_to_ffmpeg_time(str(start_time))
                ) if isinstance(start_time, str) else float(start_time)
                raw_end_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(
                    VideoProcessor.convert_srt_time_to_ffmpeg_time(str(end_time))
                ) if isinstance(end_time, str) else float(end_time)
            except Exception:
                raw_start_sec = 0.0
                raw_end_sec = 0.0

            # 处理时间格式
            if isinstance(start_time, (int, float)):
                start_time = VideoProcessor.convert_seconds_to_ffmpeg_time(start_time)
            if isinstance(end_time, (int, float)):
                end_time = VideoProcessor.convert_seconds_to_ffmpeg_time(end_time)

            safe_title = VideoProcessor.sanitize_filename(title)
            output_path = self.clips_dir / f"{clip_id}_{safe_title}.mp4"

            logger.info(
                f"提取切片 {clip_id}: {original_start} -> {original_end} "
                f"(对齐后: {start_time} -> {end_time}), 输出: {output_path}"
            )

            if VideoProcessor.extract_clip(input_video, output_path, start_time, end_time):
                # ---- 静音后处理（VAD 复用模式优先） ----
                if silence_processor is not None:
                    temp_path = output_path.with_suffix(f".silence_temp{output_path.suffix}")
                    try:
                        if full_audio_vad is not None and raw_end_sec > raw_start_sec:
                            # VAD 复用模式：用 P1 VAD 结果，无需 FFmpeg 检测
                            logger.info(f"切片 {clip_id} 开始静音移除处理 (VAD复用)")
                            success = silence_processor.process_clip_with_vad(
                                input_video=output_path,
                                output_video=temp_path,
                                clip_start_sec=raw_start_sec,
                                clip_end_sec=raw_end_sec,
                                full_audio_vad=full_audio_vad,
                                clip_id=str(clip_id),
                            )
                        else:
                            # 回退模式：老方法（FFmpeg silencedetect）
                            logger.info(f"切片 {clip_id} 开始静音移除处理 (FFmpeg回退)")
                            success = silence_processor.process_clip(
                                input_video=output_path,
                                output_video=temp_path,
                                clip_id=str(clip_id),
                            )

                        if success and temp_path.exists():
                            temp_path.replace(output_path)
                            logger.info(f"切片 {clip_id} 静音移除完成")
                        else:
                            logger.warning(f"切片 {clip_id} 静音移除无变化，保留原切片")
                            if temp_path.exists():
                                temp_path.unlink()
                    except Exception as e:
                        logger.warning(f"切片 {clip_id} 静音处理异常: {e}，保留原切片")
                        if temp_path.exists():
                            temp_path.unlink()
                # ---- 静音后处理结束 ----

                successful_clips.append(output_path)
                processed_clips_data.append({
                    'id': clip_id,
                    'title': title,
                    'start_time': start_time,
                    'end_time': end_time,
                    'original_start': original_start,
                    'original_end': original_end,
                    'output_path': str(output_path),
                    'keyframe_aligned': clip_data.get('keyframe_aligned', False),
                    'silence_processed': silence_processor is not None,
                    'vad_reused': full_audio_vad is not None,
                })

                logger.info(f"切片 {clip_id} 提取成功")
            else:
                logger.error(f"切片 {clip_id} 提取失败")

        logger.info(f"批量提取完成，成功 {len(successful_clips)}/{len(clips_data)} 个切片")
        return successful_clips, processed_clips_data
    
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