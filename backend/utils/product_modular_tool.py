"""
产品介绍模块化工具整合
提供统一的接口
"""
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .product_detector import ProductDetector
from .segment_classifier import SegmentClassifier
from .reuse_value_calculator import ReuseValueCalculator
from .reuse_library import ReuseLibrary

logger = logging.getLogger(__name__)

class ProductModularTool:
    """产品介绍模块化工具"""
    
    def __init__(self):
        self.product_detector = ProductDetector()
        self.segment_classifier = SegmentClassifier()
        self.reuse_value_calculator = ReuseValueCalculator()
        self.reuse_library = ReuseLibrary()
    
    def process_clips(self, clips: List[Dict]) -> List[Dict]:
        """
        处理切片列表，识别产品介绍片段
        
        Args:
            clips: 切片列表
        
        Returns:
            增强后的切片列表（包含segment_type和reuse_value）
        """
        enhanced_clips = []
        
        for clip in clips:
            enhanced_clip = self._process_clip(clip)
            enhanced_clips.append(enhanced_clip)
        
        return enhanced_clips
    
    def _process_clip(self, clip: Dict) -> Dict:
        """
        处理单个切片
        
        Args:
            clip: 切片数据
        
        Returns:
            增强后的切片数据
        """
        enhanced_clip = clip.copy()
        enhanced_clip["segments"] = []
        
        # 获取句子列表
        sentences = clip.get("sentences", [])
        
        if not sentences:
            enhanced_clip["segment_type"] = "topic"
            enhanced_clip["reuse_value"] = 0.0
            enhanced_clip["reusable_clips"] = []
            return enhanced_clip
        
        # 分类所有句子
        classified_sentences = self.segment_classifier.classify_all(sentences)
        
        # 合并连续相同类型的句子
        segments = self._merge_segments(classified_sentences)
        
        # 计算每个片段的复用价值
        segments_with_value = []
        reusable_clips = []
        
        for segment in segments:
            # 获取片段文本
            segment_text = "".join(
                sent["text"] for sent in sentences[segment["start_index"]:segment["end_index"]+1]
            )
            
            # 检测产品特征
            features = self.product_detector.detect_product_features(segment_text)
            
            # 计算复用价值
            reuse_value = self.reuse_value_calculator.calculate(features)
            
            segment_info = {
                "start": segment["start"],
                "end": segment["end"],
                "duration": segment["end"] - segment["start"],
                "type": segment["type"],
                "product_features": features,
                "reuse_value": reuse_value,
                "tags": []
            }
            
            # 添加标签
            if reuse_value >= 0.6:
                segment_info["tags"].append("high_reuse")
            
            if features.get("product_name"):
                segment_info["tags"].append(features["product_name"])
            
            segments_with_value.append(segment_info)
            
            # 标记可复用片段
            if segment["type"] == "product_intro" and reuse_value >= 0.5:
                reusable_clips.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "duration": segment["end"] - segment["start"],
                    "type": "product_intro",
                    "product_name": features.get("product_name"),
                    "reuse_value": reuse_value,
                    "tags": segment_info["tags"]
                })
        
        enhanced_clip["segments"] = segments_with_value
        enhanced_clip["reusable_clips"] = reusable_clips
        
        # 设置主类型和复用价值
        if reusable_clips:
            enhanced_clip["segment_type"] = "product_intro"
            enhanced_clip["reuse_value"] = max(r["reuse_value"] for r in reusable_clips)
        else:
            enhanced_clip["segment_type"] = "topic"
            enhanced_clip["reuse_value"] = 0.0
        
        return enhanced_clip
    
    def _merge_segments(self, classified_sentences: List[Dict]) -> List[Dict]:
        """
        合并连续相同类型的句子
        
        Args:
            classified_sentences: 分类后的句子列表
        
        Returns:
            合并后的片段列表
        """
        if not classified_sentences:
            return []
        
        segments = []
        current_type = classified_sentences[0]["segment_type"]
        current_start = classified_sentences[0].get("start", 0)
        current_start_index = 0
        
        for i, sentence in enumerate(classified_sentences):
            if sentence["segment_type"] != current_type:
                # 结束当前片段
                segments.append({
                    "start": current_start,
                    "end": classified_sentences[i-1].get("end", 0),
                    "type": current_type,
                    "start_index": current_start_index,
                    "end_index": i-1
                })
                
                # 开始新片段
                current_type = sentence["segment_type"]
                current_start = sentence.get("start", 0)
                current_start_index = i
        
        # 添加最后一个片段
        segments.append({
            "start": current_start,
            "end": classified_sentences[-1].get("end", 0),
            "type": current_type,
            "start_index": current_start_index,
            "end_index": len(classified_sentences) - 1
        })
        
        return segments
    
    def extract_reusable_clips(self, clip: Dict) -> List[Dict]:
        """
        从切片中提取可复用片段
        
        Args:
            clip: 切片数据
        
        Returns:
            可复用片段列表
        """
        enhanced_clip = self._process_clip(clip)
        return enhanced_clip.get("reusable_clips", [])
    
    def save_reusable_clips(self, clip: Dict, project_dir: Path):
        """
        将可复用片段保存到复用库
        
        Args:
            clip: 切片数据
            project_dir: 项目目录
        
        Returns:
            保存的片段数量
        """
        reusable_clips = self.extract_reusable_clips(clip)
        count = 0
        
        for rc in reusable_clips:
            # 创建片段文件路径
            clip_id = clip.get("id", "unknown")
            segment_path = project_dir / "reuse_clips" / f"{clip_id}_{rc['start']}s-{rc['end']}s.mp4"
            
            # 保存到复用库
            metadata = {
                "duration": rc["duration"],
                "product_name": rc["product_name"],
                "category": rc.get("category"),
                "reuse_value": rc["reuse_value"],
                "tags": rc["tags"],
                "source_clip_id": clip_id,
                "source_video": clip.get("source_video"),
                "source_start": rc["start"],
                "source_end": rc["end"]
            }
            
            # 这里需要实际提取视频片段
            # 暂时只保存元数据
            self.reuse_library.add_clip(segment_path, metadata)
            count += 1
        
        return count
    
    def get_reuse_library_statistics(self) -> Dict[str, Any]:
        """获取复用库统计信息"""
        return self.reuse_library.get_statistics()