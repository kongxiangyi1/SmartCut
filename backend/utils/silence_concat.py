"""
静音拼接器 - 使用 VAD 检测 + filter_complex 分段裁剪 + 拼接的方式移除视频切片中的静音部分

优化说明（2025-06-04）：
  - 跳过音频提取环节：silencedetect 可直接读视频音频流，无需额外写 WAV
  - 使用 filter_complex 一次完成多段 trim+concat，替代分步 split+concat
  - 减少 ffmpeg 调用次数：7 次 → 3 次，编码次数：5 次 → 1 次
"""

import subprocess
import logging
import re
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SilenceConcat:
    """静音拼接器，用于检测并移除视频切片中的静音部分"""

    def __init__(self,
                 long_silence_threshold: float = 1.0,
                 short_silence_keep: float = 0.8,
                 buffer_duration: float = 0.2,
                 silence_threshold_db: float = -35.0):
        """
        Args:
            long_silence_threshold: 超过此秒数的静音将被去除（默认 1 秒）
            short_silence_keep:     间隔 ≤ 此值的相邻语音段将合并保留（默认 0.8 秒）
            buffer_duration:         语音区间前后保留的缓冲时间（秒）
            silence_threshold_db:    静音检测分贝阈值（默认 -35 dB）
        """
        self.long_silence_threshold = long_silence_threshold
        self.short_silence_keep = short_silence_keep
        self.buffer_duration = buffer_duration
        self.silence_threshold_db = silence_threshold_db

    # ==================================================================
    # 公开入口
    # ==================================================================

    def process_clip(self, input_video: Path, output_video: Path,
                     clip_id: str = "") -> bool:
        """
        对单个已裁剪的视频切片进行静音移除处理。

        流程：检测静音区间 → 反转出语音区间 → 合并短间隔 →
              单次 filter_complex 完成多段 trim+concat。

        Args:
            input_video:  已裁剪好的视频切片路径
            output_video: 处理后的输出路径
            clip_id:      用于日志的标识

        Returns:
            是否成功
        """
        clip_tag = f"[{clip_id}]" if clip_id else ""
        logger.info(f"{clip_tag} 开始静音处理: {input_video.name}")

        # 获取视频时长
        duration = self._get_media_duration(input_video)
        if duration is None or duration <= 0:
            logger.warning(f"{clip_tag} 无法获取视频时长，跳过静音处理")
            return self._fallback_copy(input_video, output_video)

        # Step 1: 直接对视频文件检测静音（无需先提取音频）
        silence_ranges = self._detect_silence_ffmpeg(input_video)
        if silence_ranges is None:
            logger.warning(f"{clip_tag} 静音检测失败，跳过静音处理")
            return self._fallback_copy(input_video, output_video)

        if not silence_ranges:
            logger.info(f"{clip_tag} 未检测到长静音，无需处理")
            return self._fallback_copy(input_video, output_video)

        # Step 2: 反推出语音区间
        speech_ranges = self._silence_to_speech(silence_ranges, duration)
        if not speech_ranges:
            logger.warning(f"{clip_tag} 未检测到有效语音区间，跳过静音处理")
            return self._fallback_copy(input_video, output_video)

        logger.info(f"{clip_tag} 检测到 {len(speech_ranges)} 个语音区间")

        # Step 3: 合并短间隔
        merged = self._merge_segments(speech_ranges, self.short_silence_keep)
        logger.info(f"{clip_tag} 合并后剩余 {len(merged)} 个语音区间")

        if len(merged) == 0:
            logger.warning(f"{clip_tag} 无有效语音区间，跳过静音处理")
            return self._fallback_copy(input_video, output_video)

        # Step 4: 单次 filter_complex 完成 trim+concat
        success = self._filter_complex_trim_concat(input_video, output_video, merged)

        if not success:
            logger.warning(f"{clip_tag} 处理失败，回退到原始视频")
            return self._fallback_copy(input_video, output_video)

        logger.info(f"{clip_tag} 静音处理完成: {output_video.name}")
        return True

    def process_clip_with_vad(
        self,
        input_video: Path,
        output_video: Path,
        clip_start_sec: float,
        clip_end_sec: float,
        full_audio_vad: List[Tuple[float, float]],
        clip_id: str = "",
    ) -> bool:
        """
        使用预计算的 VAD 结果处理单一切片（无需额外 FFmpeg 检测）。

        流程:
            1. 将全音频 VAD 结果映射到 clip 局部坐标
            2. 合并短间隔
            3. filter_complex trim+concat

        Args:
            input_video: 已裁剪好的视频切片路径
            output_video: 处理后的输出路径
            clip_start_sec: clip 在全音频中的开始时间（秒）
            clip_end_sec: clip 在全音频中的结束时间（秒）
            full_audio_vad: 全音频语音区间 [(start, end), ...]
            clip_id: 用于日志的标识

        Returns:
            是否成功
        """
        clip_tag = f"[{clip_id}]" if clip_id else ""
        logger.info(f"{clip_tag} 开始静音处理 (VAD复用模式): {input_video.name}")

        # Step 1: 坐标映射
        from backend.utils.silero_vad_wrapper import SileroVADWrapper

        speech_ranges = SileroVADWrapper.map_to_clip(
            full_audio_vad, clip_start_sec, clip_end_sec
        )

        if not speech_ranges:
            logger.info(f"{clip_tag} 无有效语音区间，跳过静音处理")
            return self._fallback_copy(input_video, output_video)

        logger.info(f"{clip_tag} VAD映射后: {len(speech_ranges)} 个语音区间")

        # Step 2: 合并短间隔
        merged = self._merge_segments(speech_ranges, self.short_silence_keep)
        logger.info(f"{clip_tag} 合并后: {len(merged)} 个语音区间")

        if len(merged) == 0:
            logger.info(f"{clip_tag} 无有效语音区间，跳过静音处理")
            return self._fallback_copy(input_video, output_video)

        # Step 3: filter_complex trim+concat（复用现有方法）
        return self._filter_complex_trim_concat(input_video, output_video, merged)

    # ==================================================================
    # filter_complex 核心方法（替换原有的 split_video + concat_videos）
    # ==================================================================

    def _filter_complex_trim_concat(self, input_video: Path, output_video: Path,
                                     segments: List[Tuple[float, float]]) -> bool:
        """
        单次 ffmpeg 调用，多输入 + concat 完成多段语音提取与拼接。

        原理：每个语音段作为一个独立输入（-ss 快速定位），
              filter_complex 只做 concat，无需 trim，避免重复解码。

        优势：
          - 只解码语音段（不解码整片），速度与旧 split 方案一致
          - 只编码 1 次（旧方案 split+concat 各编码 1 次）
          - 无临时文件
        """
        # 1) 应用 buffer 并过滤过短段
        buffered = self._apply_buffer_non_overlap(segments)
        valid = [(s, e) for s, e in buffered if e - s > 0.3]
        n = len(valid)

        if n == 0:
            logger.warning("multi_input concat: 无有效段")
            return False

        if n == 1:
            # 单段 → 直接 trim（无需 concat）
            s, e = valid[0]
            dur = e - s
            if dur < 0.3:
                return False
            try:
                cmd = [
                    'ffmpeg', '-ss', f'{s:.3f}',
                    '-i', str(input_video),
                    '-t', f'{dur:.3f}',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-y', str(output_video)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True,
                                        encoding='utf-8', errors='ignore', timeout=300)
                return result.returncode == 0
            except Exception as e:
                logger.error(f"multi_input trim 单段异常: {e}")
                return False

        # 2) 构建多输入命令
        #    ffmpeg -ss s1 -t d1 -i input.mp4
        #           -ss s2 -t d2 -i input.mp4
        #           -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]"
        cmd = ['ffmpeg']
        for s, e in valid:
            dur = e - s
            cmd.extend(['-ss', f'{s:.3f}', '-t', f'{dur:.3f}', '-i', str(input_video)])

        # 构建 concat filter
        concat_inputs = ''.join(f'[{i}:v][{i}:a]' for i in range(n))
        filter_complex = f'{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]'
        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            '-y', str(output_video)
        ])

        # 3) 执行
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore', timeout=600)
            if result.returncode == 0:
                logger.info(f"multi_input concat 完成: {n} 段 -> {output_video.name}")
                return True
            else:
                logger.error(f"multi_input concat 失败: {result.stderr[:300]}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("multi_input concat 超时")
            return False
        except Exception as e:
            logger.error(f"multi_input concat 异常: {e}")
            return False

    # ==================================================================
    # 静音检测（FFmpeg silencedetect）
    # ==================================================================

    def _detect_silence_ffmpeg(self, media_path: Path) -> Optional[List[Tuple[float, float]]]:
        """
        使用 FFmpeg silencedetect 检测长静音区间。

        直接读取视频的音频流（无需先提取音频文件）。

        Returns:
            [(start, end), ...] 每个静音区间的起止时间（秒），
            或 None 表示检测失败，或 [] 表示无静音
        """
        try:
            cmd = [
                'ffmpeg',
                '-i', str(media_path),
                '-af', f'silencedetect=noise={self.silence_threshold_db}dB:d={self.long_silence_threshold}',
                '-f', 'null',
                '-'
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='ignore', timeout=300
            )
            output = result.stderr

            silence_ranges: List[Tuple[float, float]] = []

            # 解析 silence_start 和 silence_end
            start_pattern = re.compile(r'silence_start:\s*([\d.]+)')
            end_pattern = re.compile(r'silence_end:\s*([\d.]+)')

            start_times = [float(m) for m in start_pattern.findall(output)]
            end_times = [float(m) for m in end_pattern.findall(output)]

            # silencedetect 输出成对出现：silence_start 后跟 silence_end
            for i in range(min(len(start_times), len(end_times))):
                silence_ranges.append((start_times[i], end_times[i]))

            return silence_ranges

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg silencedetect 超时")
            return None
        except Exception as e:
            logger.error(f"FFmpeg silencedetect 异常: {e}")
            return None

    # ==================================================================
    # 工具方法
    # ==================================================================

    @staticmethod
    def _get_media_duration(media_path: Path) -> Optional[float]:
        """获取媒体时长（秒）"""
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(media_path)
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='ignore', timeout=30
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
            return None
        except Exception:
            return None

    @staticmethod
    def _silence_to_speech(silence_ranges: List[Tuple[float, float]],
                           total_duration: float) -> List[Tuple[float, float]]:
        """
        将静音区间反转为语音区间。

        原始音频:  |---语音---|---静音---|---语音---|---静音---|---语音---|
        反 转 后:  [语音A]      [静音]     [语音B]      [静音]     [语音C]

        返回: [(speech_start, speech_end), ...]
        """
        if not silence_ranges:
            return [(0.0, total_duration)]

        speech: List[Tuple[float, float]] = []

        # 第一段语音：从 0 到第一个静音开始
        first_silence_start = silence_ranges[0][0]
        if first_silence_start > 0:
            speech.append((0.0, first_silence_start))

        # 中间语音：前一个静音结束 到 后一个静音开始
        for i in range(len(silence_ranges) - 1):
            speech_start = silence_ranges[i][1]
            speech_end = silence_ranges[i + 1][0]
            if speech_end > speech_start:
                speech.append((speech_start, speech_end))

        # 最后一段语音：最后一个静音结束 到 视频结束
        last_silence_end = silence_ranges[-1][1]
        if last_silence_end < total_duration:
            speech.append((last_silence_end, total_duration))

        return speech

    @staticmethod
    def _merge_segments(segments: List[Tuple[float, float]],
                        max_gap: float = 1.0) -> List[Tuple[float, float]]:
        """
        合并间隔 ≤ max_gap 的相邻语音段。
        """
        if not segments:
            return []

        sorted_segs = sorted(segments, key=lambda x: x[0])
        merged = [sorted_segs[0]]

        for seg in sorted_segs[1:]:
            if seg[0] - merged[-1][1] <= max_gap:
                merged[-1] = (merged[-1][0], max(merged[-1][1], seg[1]))
            else:
                merged.append(seg)

        return merged

    def _apply_buffer_non_overlap(
        self, segments: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """在每段语音前后加 buffer，同时防止相邻段重叠"""
        if not segments:
            return []

        buffered = []
        for start, end in segments:
            s = max(0.0, start - self.buffer_duration)
            e = end + self.buffer_duration
            buffered.append((s, e))

        # 防止重叠：如果后一段的开始 < 前一段的结束，则取中点
        result = [buffered[0]]
        for i in range(1, len(buffered)):
            prev_s, prev_e = result[-1]
            curr_s, curr_e = buffered[i]
            if curr_s < prev_e:
                mid = (prev_e + curr_s) / 2
                result[-1] = (prev_s, mid)
                result.append((mid, curr_e))
            else:
                result.append((curr_s, curr_e))
        return result

    @staticmethod
    def _cleanup(temp_dir: Path):
        """清理临时目录（兼容旧接口）"""
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")

    @staticmethod
    def _fallback_copy(src: Path, dst: Path) -> bool:
        """回退：直接复制源文件到目标"""
        try:
            shutil.copy2(src, dst)
            return True
        except Exception as e:
            logger.error(f"回退复制失败: {e}")
            return False

    # ==================================================================
    # 兼容旧接口
    # ==================================================================

    def process_and_concat(self, video_clips: list, output_path: Path,
                          silence_threshold: float = -35.0) -> bool:
        """
        兼容旧接口：处理视频片段列表中的静音并拼接。
        """
        self.silence_threshold_db = silence_threshold

        processed: List[Path] = []
        temp_dir = output_path.parent / ".silence_concat_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        for i, clip in enumerate(video_clips):
            clip_path = clip.get('path') if isinstance(clip, dict) else clip
            if isinstance(clip_path, str):
                clip_path = Path(clip_path)

            if not clip_path or not clip_path.exists():
                continue

            processed_path = temp_dir / f"processed_{i:03d}.mp4"
            if self.process_clip(Path(clip_path), processed_path, clip_id=str(i)):
                processed.append(processed_path)
            else:
                processed.append(Path(clip_path))

        if not processed:
            logger.error("没有可处理的视频片段")
            return False

        return self._concat_videos(processed, output_path)

    def extract_speech_segments(self, audio_path: Path,
                                silence_threshold: float = -40.0) -> List[dict]:
        """
        兼容旧接口：从音频中提取语音片段。
        """
        self.silence_threshold_db = silence_threshold

        duration = self._get_media_duration(audio_path)
        if not duration or duration <= 0:
            return []

        silence_ranges = self._detect_silence_ffmpeg(audio_path)
        if not silence_ranges:
            return [{'start': 0.0, 'end': duration}]

        speech_ranges = self._silence_to_speech(silence_ranges, duration)
        return [{'start': s, 'end': e} for s, e in speech_ranges]

    def concat_videos(self, video_paths: List[Path], output_path: Path) -> bool:
        """兼容旧接口：拼接多个视频文件"""
        return self._concat_videos(video_paths, output_path)

    @staticmethod
    def _concat_videos(segment_paths: List[Path], output_path: Path) -> bool:
        """使用 FFmpeg concat demuxer 拼接多个视频片段（兼容旧接口）"""
        if len(segment_paths) == 0:
            return False
        if len(segment_paths) == 1:
            shutil.copy2(segment_paths[0], output_path)
            return True

        concat_file = output_path.parent / ".concat_list.txt"
        try:
            with open(concat_file, 'w', encoding='utf-8') as f:
                for seg in segment_paths:
                    f.write(f"file '{seg}'\n")

            cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', str(concat_file),
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                '-movflags', '+faststart',
                str(output_path)
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='ignore', timeout=600
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"拼接视频异常: {e}")
            return False
        finally:
            if concat_file.exists():
                concat_file.unlink()