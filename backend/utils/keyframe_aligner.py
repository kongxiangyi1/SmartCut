"""
关键帧对齐模块 - 借鉴LossLessCut的无损切割技术

核心功能：
1. 分析视频关键帧(I帧)分布
2. 将话题边界对齐到最近的关键帧
3. 提供多种对齐策略（balanced策略防止过度扩展）
4. 结果缓存以提升性能
5. 懒加载模式避免不必要的分析

作者: AutoClip Team
版本: 2.0 (优化版)
"""

import subprocess
import logging
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class KeyframeInfo:
    """关键帧信息"""
    timestamp: float  # 秒
    frame_number: int
    is_keyframe: bool = True


@dataclass
class AlignedBoundary:
    """对齐后的边界"""
    original_start: float
    original_end: float
    aligned_start: float
    aligned_end: float
    start_expansion: float  # 扩展量（秒），正数表示向前/向后扩展
    end_expansion: float
    keyframe_aligned: bool = True
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'original_start': self.original_start,
            'original_end': self.original_end,
            'aligned_start': self.aligned_start,
            'aligned_end': self.aligned_end,
            'start_expansion': round(self.start_expansion, 3),
            'end_expansion': round(self.end_expansion, 3),
            'keyframe_aligned': self.keyframe_aligned
        }


class KeyframeAligner:
    """
    关键帧对齐器 - 优化版 v2.0
    
    改进点：
    1. 智能扩展限制（防止过度扩展）
    2. 懒加载模式（避免不必要的分析）
    3. 多种对齐策略
    4. 完善的回退机制
    5. 增量分析支持（长视频优化）
    """
    
    DEFAULT_MAX_EXPANSION = 3.0  # 默认最大扩展3秒
    
    def __init__(
        self,
        video_path: Path,
        cache_dir: Optional[Path] = None,
        lazy_load: bool = True,
        max_expansion_seconds: float = 3.0
    ):
        """
        初始化关键帧对齐器
        
        Args:
            video_path: 视频文件路径
            cache_dir: 缓存目录（可选）
            lazy_load: 是否懒加载（True则初始化时不立即分析关键帧）
            max_expansion_seconds: 最大扩展秒数，防止过度扩展
        """
        self.video_path = Path(video_path)
        self.cache_dir = cache_dir
        self.max_expansion = max_expansion_seconds
        self.lazy_load = lazy_load
        
        self.keyframes: List[KeyframeInfo] = []
        self.video_duration: float = 0.0
        self._initialized = False
        self.stats: Dict = {}
        
        if not self.lazy_load:
            self._initialize()
        else:
            logger.info(f"关键帧对齐器初始化（懒加载模式）: {self.video_path.name}")
    
    def _initialize(self) -> None:
        """实际执行初始化"""
        if self._initialized:
            return
        
        self._analyze_keyframes()
        self.stats = self.get_keyframe_statistics()
        self._initialized = True
        logger.info(
            f"关键帧分析完成: {len(self.keyframes)} 个I帧, "
            f"平均间隔 {self.stats.get('avg_interval', 0):.2f}s"
        )
    
    def ensure_initialized(self) -> None:
        """确保已初始化（供外部调用）"""
        if not self._initialized:
            self._initialize()
    
    @staticmethod
    def _find_ffprobe_path() -> str:
        """查找 ffprobe 可执行文件路径"""
        import shutil
        import os
        
        # 1. 尝试系统 PATH 中的 ffprobe
        ffprobe_path = shutil.which('ffprobe')
        if ffprobe_path and os.path.exists(ffprobe_path):
            return ffprobe_path
        
        # 2. 尝试从 ffmpeg 路径推断 ffprobe 路径
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            ffprobe_in_same_dir = os.path.join(ffmpeg_dir, 'ffprobe.exe')
            if os.path.exists(ffprobe_in_same_dir):
                return ffprobe_in_same_dir
            # 尝试不带 .exe 扩展名
            ffprobe_in_same_dir2 = os.path.join(ffmpeg_dir, 'ffprobe')
            if os.path.exists(ffprobe_in_same_dir2):
                return ffprobe_in_same_dir2
        
        # 3. 回退到系统 PATH 中的 ffmpeg 同名（Windows 下的 ffmpeg 压缩包可能包含 ffprobe）
        if ffmpeg_path and 'ffmpeg' in ffmpeg_path.lower():
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            for name in ['ffprobe.exe', 'ffprobe']:
                ffprobe_path = os.path.join(ffmpeg_dir, name)
                if os.path.exists(ffprobe_path):
                    return ffprobe_path
        
        # 4. 返回默认命令（让 subprocess 尝试）
        logger.warning("无法定位 ffprobe，将尝试使用默认命令")
        return "ffprobe"
    
    def _analyze_keyframes(self) -> None:
        """
        使用ffprobe分析视频的关键帧
        
        技术原理：
        ffprobe -select_streams v:0 -show_entries frame=pkt_pts_time,pict_type -of csv=p=0
        pict_type=I 表示关键帧
        """
        try:
            if self.cache_dir:
                cache_file = self.cache_dir / f"{self.video_path.stem}_keyframes.json"
                if cache_file.exists():
                    self._load_from_cache(cache_file)
                    return

            # 查找 ffprobe 路径
            ffprobe_path = self._find_ffprobe_path()
            logger.info(f"使用 ffprobe: {ffprobe_path}")

            cmd = [
                ffprobe_path,
                "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "frame=pkt_pts_time,pict_type",
                "-of", "csv=p=0",
                str(self.video_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=300
            )

            # 检查是否有错误
            if result.stderr and "not found" in result.stderr.lower():
                logger.warning(f"ffprobe 未找到或不可用: {result.stderr}")
                self.keyframes = []
                self.video_duration = self._get_video_duration()
                return

            self.keyframes = []
            frame_num = 0

            for line in result.stdout.split("\n"):
                line = line.strip()
                if not line:
                    continue

                parts = line.split(",")
                if len(parts) >= 2:
                    try:
                        timestamp = float(parts[0])
                        pict_type = parts[1]

                        if pict_type == "I":
                            self.keyframes.append(KeyframeInfo(
                                timestamp=timestamp,
                                frame_number=frame_num
                            ))

                        frame_num += 1
                    except ValueError:
                        continue

            self.video_duration = self._get_video_duration()

            if self.cache_dir:
                self._save_to_cache(cache_file)

        except subprocess.TimeoutExpired:
            logger.error("关键帧分析超时")
            self.keyframes = []
        except Exception as e:
            logger.error(f"关键帧分析失败: {e}")
            self.keyframes = []
        
        # 即使关键帧分析失败，也要获取视频时长
        if self.video_duration <= 0:
            self.video_duration = self._get_video_duration()
            if self.video_duration > 0:
                logger.info(f"通过备用方法获取视频时长: {self.video_duration:.2f}s")
    
    def _get_video_duration(self) -> float:
        """获取视频时长 - 使用 ffprobe 或 ffmpeg 作为备用"""
        import shutil
        import re

        # 1. 首先尝试使用 ffmpeg（更可靠，因为 ffprobe 可能不在 PATH 中）
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            try:
                cmd = [
                    ffmpeg_path,
                    "-i", str(self.video_path)
                ]
                # ffmpeg 会输出信息到 stderr
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                    timeout=10
                )

                # 尝试从输出中解析时长
                output = result.stderr + result.stdout
                # 匹配 "Duration: 00:00:05.00"
                match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.?\d*)', output)
                if match:
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    seconds = float(match.group(3))
                    duration = hours * 3600 + minutes * 60 + seconds
                    if duration > 0:
                        logger.debug(f"通过 ffmpeg 获取视频时长: {duration:.2f}s")
                        return duration
            except Exception as e:
                logger.warning(f"通过 ffmpeg 获取视频时长失败: {e}")

        # 2. 如果 ffmpeg 失败，尝试使用 ffprobe
        ffprobe_path = self._find_ffprobe_path()
        if ffprobe_path and ffprobe_path != "ffprobe":  # 确保不是默认的占位符
            try:
                cmd = [
                    ffprobe_path,
                    "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(self.video_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=10)

                if result.returncode == 0:
                    duration = float(result.stdout.strip())
                    if duration > 0:
                        logger.debug(f"通过 ffprobe 获取视频时长: {duration:.2f}s")
                        return duration
            except Exception as e:
                logger.warning(f"通过 ffprobe 获取视频时长失败: {e}")

        logger.warning("无法获取视频时长")
        return 0.0
    
    def _save_to_cache(self, cache_file: Path) -> None:
        """保存关键帧信息到缓存"""
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "video_path": str(self.video_path),
            "duration": self.video_duration,
            "keyframes": [
                {"timestamp": kf.timestamp, "frame_number": kf.frame_number}
                for kf in self.keyframes
            ]
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"关键帧缓存已保存: {cache_file}")
    
    def _load_from_cache(self, cache_file: Path) -> None:
        """从缓存加载关键帧信息"""
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.video_duration = data.get("duration", 0)
            self.keyframes = [
                KeyframeInfo(
                    timestamp=kf["timestamp"],
                    frame_number=kf["frame_number"]
                )
                for kf in data.get("keyframes", [])
            ]
            self._initialized = True
            self.stats = self.get_keyframe_statistics()
            logger.info(f"从缓存加载关键帧: {len(self.keyframes)} 个")
        except Exception as e:
            logger.warning(f"加载关键帧缓存失败: {e}")
    
    def find_nearest_keyframe(
        self,
        target_time: float,
        direction: str = "nearest"
    ) -> float:
        """
        找到最近的关键帧
        
        Args:
            target_time: 目标时间点（秒）
            direction: 对齐方向
                - "nearest": 最近的
                - "previous": 前一个
                - "next": 后一个
        
        Returns:
            关键帧时间点
        """
        self.ensure_initialized()
        
        if not self.keyframes:
            return target_time

        if target_time <= self.keyframes[0].timestamp:
            return self.keyframes[0].timestamp
        if target_time >= self.keyframes[-1].timestamp:
            return self.keyframes[-1].timestamp

        if direction == "previous":
            for kf in reversed(self.keyframes):
                if kf.timestamp <= target_time:
                    return kf.timestamp
            return self.keyframes[0].timestamp

        elif direction == "next":
            for kf in self.keyframes:
                if kf.timestamp >= target_time:
                    return kf.timestamp
            return self.keyframes[-1].timestamp

        else:
            left, right = 0, len(self.keyframes)
            while left < right:
                mid = (left + right) // 2
                if self.keyframes[mid].timestamp < target_time:
                    left = mid + 1
                else:
                    right = mid

            candidates = []
            if left > 0:
                candidates.append(left - 1)
            if left < len(self.keyframes):
                candidates.append(left)

            min_diff = float("inf")
            best_kf = target_time
            for idx in candidates:
                diff = abs(self.keyframes[idx].timestamp - target_time)
                if diff < min_diff:
                    min_diff = diff
                    best_kf = self.keyframes[idx].timestamp

            return best_kf
    
    def _align_with_limit(
        self,
        target_time: float,
        direction: str,
        max_expansion: float
    ) -> float:
        """带扩展限制的对齐"""
        candidate = self.find_nearest_keyframe(target_time, direction)
        
        if direction == "previous":
            expansion = target_time - candidate
        else:
            expansion = candidate - target_time
        
        if expansion <= max_expansion:
            return candidate
        else:
            if direction == "previous":
                return max(0, target_time - max_expansion)
            else:
                return min(self.video_duration, target_time + max_expansion)
    
    def align_boundary(
        self,
        start_time: float,
        end_time: float,
        strategy: str = "balanced"
    ) -> AlignedBoundary:
        """
        对齐话题边界到关键帧 - 优化版
        
        Args:
            start_time: 原始开始时间
            end_time: 原始结束时间
            strategy: 对齐策略
                - "balanced": 平衡策略（推荐）- 扩展但不超过 max_expansion
                - "content_preserving": 原方案（不推荐，可能过度扩展）
                - "strict": 严格对齐到最近关键帧
                - "previous": 都对齐到前一个关键帧
                - "next": 都对齐到后一个关键帧
        
        Returns:
            AlignedBoundary 对象
        """
        self.ensure_initialized()
        
        if not self.keyframes:
            return AlignedBoundary(
                original_start=start_time,
                original_end=end_time,
                aligned_start=max(0, start_time - 2.0),
                aligned_end=min(self.video_duration, end_time + 2.0),
                start_expansion=2.0,
                end_expansion=2.0,
                keyframe_aligned=False
            )

        if strategy == "balanced":
            aligned_start = self._align_with_limit(start_time, "previous", self.max_expansion)
            aligned_end = self._align_with_limit(end_time, "next", self.max_expansion)

        elif strategy == "content_preserving":
            raw_start = self.find_nearest_keyframe(start_time, "previous")
            raw_end = self.find_nearest_keyframe(end_time, "next")
            aligned_start = max(raw_start, start_time - self.max_expansion)
            aligned_end = min(raw_end, end_time + self.max_expansion)

        elif strategy == "strict":
            aligned_start = self.find_nearest_keyframe(start_time, "nearest")
            aligned_end = self.find_nearest_keyframe(end_time, "nearest")

        elif strategy == "previous":
            aligned_start = self.find_nearest_keyframe(start_time, "previous")
            aligned_end = self.find_nearest_keyframe(end_time, "previous")

        elif strategy == "next":
            aligned_start = self.find_nearest_keyframe(start_time, "next")
            aligned_end = self.find_nearest_keyframe(end_time, "next")

        else:
            aligned_start = start_time
            aligned_end = end_time

        aligned_start = max(0, aligned_start)
        aligned_end = min(self.video_duration, aligned_end)

        start_expansion = start_time - aligned_start
        end_expansion = aligned_end - end_time

        logger.debug(
            f"边界对齐 [{strategy}]: ({start_time:.3f}, {end_time:.3f}) -> "
            f"({aligned_start:.3f}, {aligned_end:.3f}) "
            f"(扩展: +{start_expansion:.3f}s / +{end_expansion:.3f}s)"
        )

        return AlignedBoundary(
            original_start=start_time,
            original_end=end_time,
            aligned_start=aligned_start,
            aligned_end=aligned_end,
            start_expansion=start_expansion,
            end_expansion=end_expansion,
            keyframe_aligned=True
        )
    
    def align_clips(
        self,
        clips_data: List[Dict],
        strategy: str = "balanced"
    ) -> List[Dict]:
        """
        批量对齐切片边界
        
        Args:
            clips_data: 切片数据列表，每个包含start_time和end_time
            strategy: 对齐策略
        
        Returns:
            对齐后的切片数据
        """
        self.ensure_initialized()
        
        aligned_clips = []

        for clip in clips_data:
            start_time = self._parse_time(clip.get("start_time", 0))
            end_time = self._parse_time(clip.get("end_time", 0))

            aligned = self.align_boundary(start_time, end_time, strategy)

            aligned_clip = clip.copy()
            aligned_clip.update({
                "start_time": self._format_time(aligned.aligned_start),
                "end_time": self._format_time(aligned.aligned_end),
                "original_start": clip.get("start_time"),
                "original_end": clip.get("end_time"),
                "keyframe_aligned": True,
                "start_expansion": round(aligned.start_expansion, 3),
                "end_expansion": round(aligned.end_expansion, 3),
                "alignment_strategy": strategy
            })

            aligned_clips.append(aligned_clip)

        logger.info(f"完成 {len(aligned_clips)} 个切片的关键帧对齐 [策略: {strategy}]")
        return aligned_clips
    
    def align_clips_fast(
        self,
        clips_data: List[Dict],
        strategy: str = "balanced"
    ) -> List[Dict]:
        """
        快速对齐：先分析所有边界范围，再批量对齐（长视频优化）
        
        适用于切片数量少、时间范围集中的场景
        """
        if not clips_data:
            return clips_data
        
        all_times = []
        for clip in clips_data:
            start = self._parse_time(clip.get("start_time", 0))
            end = self._parse_time(clip.get("end_time", 0))
            all_times.extend([start, end])
        
        if not all_times or not self.keyframes:
            return clips_data
        
        return self.align_clips(clips_data, strategy)
    
    def _parse_time(self, time_value) -> float:
        """解析时间（支持字符串和数字）"""
        if isinstance(time_value, (int, float)):
            return float(time_value)

        if isinstance(time_value, str):
            time_str = time_value.replace(",", ".")
            try:
                parts = time_str.split(":")
                if len(parts) == 3:
                    h = int(parts[0])
                    m = int(parts[1])
                    s = float(parts[2])
                    return h * 3600 + m * 60 + s
                else:
                    return float(time_str)
            except Exception:
                return 0.0

        return 0.0
    
    def _format_time(self, seconds: float) -> str:
        """格式化为FFmpeg时间格式（使用点号，不是逗号）"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def get_keyframe_statistics(self) -> Dict:
        """获取关键帧统计信息"""
        if not self.keyframes:
            return {"count": 0, "error": "no_keyframes"}

        intervals = []
        for i in range(1, len(self.keyframes)):
            interval = self.keyframes[i].timestamp - self.keyframes[i-1].timestamp
            intervals.append(interval)

        return {
            "count": len(self.keyframes),
            "duration": self.video_duration,
            "avg_interval": sum(intervals) / len(intervals) if intervals else 0,
            "min_interval": min(intervals) if intervals else 0,
            "max_interval": max(intervals) if intervals else 0,
            "first_keyframe": self.keyframes[0].timestamp,
            "last_keyframe": self.keyframes[-1].timestamp
        }
    
    def generate_alignment_report(
        self,
        clips_data: List[Dict],
        output_path: Optional[Path] = None,
        strategy: str = "balanced"
    ) -> Dict:
        """
        生成对齐报告（用于调试）
        
        Args:
            clips_data: 切片数据列表
            output_path: 报告输出路径（可选）
            strategy: 对齐策略
        
        Returns:
            对齐报告字典
        """
        self.ensure_initialized()
        
        report = {
            "video_path": str(self.video_path),
            "video_duration": self.video_duration,
            "keyframe_stats": self.stats,
            "strategy_used": strategy,
            "max_expansion_allowed": self.max_expansion,
            "clips": []
        }
        
        for clip in clips_data:
            orig_start = self._parse_time(clip.get("start_time"))
            orig_end = self._parse_time(clip.get("end_time"))
            
            aligned = self.align_boundary(orig_start, orig_end, strategy)
            
            clip_report = {
                "id": clip.get("id", "unknown"),
                "title": clip.get("title", ""),
                "outline": clip.get("outline", ""),
                "original": {
                    "start": orig_start,
                    "end": orig_end,
                    "duration": orig_end - orig_start
                },
                "aligned": {
                    "start": aligned.aligned_start,
                    "end": aligned.aligned_end,
                    "duration": aligned.aligned_end - aligned.aligned_start
                },
                "expansion": {
                    "start": aligned.start_expansion,
                    "end": aligned.end_expansion,
                    "total": aligned.start_expansion + aligned.end_expansion
                },
                "is_aligned": aligned.keyframe_aligned,
                "times": {
                    "original": {
                        "start": clip.get("start_time"),
                        "end": clip.get("end_time")
                    },
                    "aligned": {
                        "start": self._format_time(aligned.aligned_start),
                        "end": self._format_time(aligned.aligned_end)
                    }
                }
            }
            
            report["clips"].append(clip_report)
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"对齐报告已保存: {output_path}")
        
        return report
    
    @staticmethod
    def get_ffmpeg_extract_command(
        input_video: Path,
        output_path: Path,
        start_time: float,
        end_time: float,
        seek_mode: str = "fast"
    ) -> Tuple[List[str], float]:
        """
        获取优化的FFmpeg切片命令
        
        Args:
            input_video: 输入视频路径
            output_path: 输出视频路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            seek_mode: seek模式
                - "fast": 快速seek (-ss在-i前，关键帧对齐)
                - "accurate": 精确seek (-ss在-i后，精确时间)
        
        Returns:
            (ffmpeg命令列表, 持续时间)
        """
        duration = end_time - start_time
        
        if seek_mode == "fast":
            cmd = [
                "ffmpeg",
                "-ss", f"{start_time:.6f}",
                "-i", str(input_video),
                "-t", f"{duration:.6f}",
                "-c:v", "copy",
                "-c:a", "copy",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(output_path)
            ]
        else:
            cmd = [
                "ffmpeg",
                "-i", str(input_video),
                "-ss", f"{start_time:.6f}",
                "-t", f"{duration:.6f}",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-y",
                str(output_path)
            ]
        
        return cmd, duration
