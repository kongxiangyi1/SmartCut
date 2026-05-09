"""
视频场景检测器
检测视频中的场景切换，用于辅助边界检测
"""
import logging
import subprocess
import json
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class VideoSceneDetector:
    """视频场景检测器"""
    
    def __init__(self):
        self.ffmpeg_available = self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> bool:
        """检查 ffmpeg 是否可用"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"ffmpeg 不可用: {e}")
            return False
    
    def detect_scene_changes(self, video_path: Path, threshold: float = 0.3) -> List[Dict]:
        """
        检测视频中的场景切换
        
        Args:
            video_path: 视频文件路径
            threshold: 场景变化阈值（0-1）
            
        Returns:
            场景切换列表，每个元素包含：
            - time: 切换时间（秒）
            - confidence: 置信度
            - type: 切换类型
        """
        if not self.ffmpeg_available:
            logger.warning("ffmpeg 不可用，返回空结果")
            return []
        
        if not video_path.exists():
            logger.error(f"视频文件不存在: {video_path}")
            return []
        
        try:
            logger.info(f"开始检测场景切换: {video_path}")
            
            # 使用 ffprobe 提取帧信息
            scene_changes = self._detect_with_ffmpeg(video_path, threshold)
            
            logger.info(f"场景检测完成，找到 {len(scene_changes)} 个场景切换")
            return scene_changes
            
        except Exception as e:
            logger.error(f"场景检测失败: {e}")
            return []
    
    def _detect_with_ffmpeg(self, video_path: Path, threshold: float) -> List[Dict]:
        """使用 ffmpeg 检测场景切换"""
        scene_changes = []
        
        # 使用 ffmpeg 的 scene filter 检测场景变化
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-filter:v', f'scale=320:240,scene=threshold={threshold}',
            '-f', 'null',
            '-'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, stderr=subprocess.STDOUT)
        
        # 解析输出中的场景切换信息
        for line in result.stdout.splitlines():
            if 'scene change' in line.lower():
                # 提取时间信息
                # 格式示例: frame=  123 fps= 30 q=-1.0 Lsize=       0kB time=00:00:04.10 bitrate=   0.0kbits/s dup=0 drop=0 speed=1.23x
                # 或者包含 scene change 的行
                time_match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
                if time_match:
                    time_str = time_match.group(1)
                    time_seconds = self._parse_time(time_str)
                    scene_changes.append({
                        'time': time_seconds,
                        'confidence': self._calculate_scene_confidence(line),
                        'type': 'scene_change',
                        'source': 'video_scene'
                    })
        
        return scene_changes
    
    def _parse_time(self, time_str: str) -> float:
        """解析 ffmpeg 时间格式"""
        parts = time_str.split(':')
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        return 0.0
    
    def _calculate_scene_confidence(self, line: str) -> float:
        """计算场景切换置信度"""
        # 简化实现：基于帧差异或其他指标
        return 0.8  # 默认高置信度
    
    def find_boundary_candidates(self, video_path: Path, threshold: float = 0.7) -> List[Dict]:
        """
        寻找潜在的边界候选点
        
        Args:
            video_path: 视频文件路径
            threshold: 置信度阈值
            
        Returns:
            边界候选点列表
        """
        scene_changes = self.detect_scene_changes(video_path)
        
        candidates = []
        for scene in scene_changes:
            if scene['confidence'] >= threshold:
                candidates.append({
                    'time': scene['time'],
                    'confidence': scene['confidence'],
                    'source': 'video_scene'
                })
        
        return candidates


# 添加正则表达式导入
import re
