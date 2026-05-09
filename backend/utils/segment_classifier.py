"""
片段分类器
判断片段类型（hook/topic/product_intro/brand）
"""
import logging
from typing import Dict, List, Optional

from .product_detector import ProductDetector
from .exceptions import SegmentClassificationError

logger = logging.getLogger(__name__)

class SegmentClassifier:
    """片段分类器"""
    
    def __init__(self):
        self.product_detector = ProductDetector()
    
    def classify(self, sentences: List[Dict], index: int) -> str:
        """
        判断片段类型
        
        Args:
            sentences: 句子列表
            index: 当前句子索引
        
        Returns:
            片段类型: "hook" | "topic" | "product_intro" | "brand"
        """
        try:
            if not sentences or index < 0 or index >= len(sentences):
                raise SegmentClassificationError("无效的输入参数")
            
            sentence = sentences[index]
            text = sentence.get('text', '')
            
            # 1. 判断是否为开头钩子
            if self._is_hook(sentences, index):
                return "hook"
            
            # 2. 判断是否为产品介绍
            if self._is_product_intro(text):
                return "product_intro"
            
            # 3. 判断是否为品牌故事
            if self._is_brand(text):
                return "brand"
            
            # 4. 默认类型为话题内容
            return "topic"
        
        except SegmentClassificationError as e:
            logger.error(f"片段分类失败: {e}")
            return "topic"
        except Exception as e:
            logger.error(f"片段分类异常: {e}")
            return "topic"
    
    def _is_hook(self, sentences: List[Dict], index: int) -> bool:
        """判断是否为开头钩子"""
        # 前3句或前10%的句子视为钩子区域
        total = len(sentences)
        hook_threshold = min(3, int(total * 0.1))
        
        if index < hook_threshold:
            text = sentences[index].get('text', '')
            
            # 检查钩子特征
            hook_features = [
                '？', '！', '你知道', '你以为', '为什么',
                '什么是', '惊人的', '震惊', '揭秘', '真相'
            ]
            
            return any(feature in text for feature in hook_features)
        
        return False
    
    def _is_product_intro(self, text: str) -> bool:
        """判断是否为产品介绍"""
        features = self.product_detector.detect_product_features(text)
        
        # 需要同时满足：产品名称 + (功能/价格)
        has_product = features.get("product_name") is not None
        has_price = features.get("price") is not None
        has_features = len(features.get("features", [])) > 0
        
        return has_product and (has_price or has_features)
    
    def _is_brand(self, text: str) -> bool:
        """判断是否为品牌故事"""
        brand_keywords = [
            '品牌', '理念', '我们', '公司', '企业',
            '创始', '愿景', '使命', '价值观', '文化'
        ]
        
        return any(keyword in text for keyword in brand_keywords)
    
    def classify_all(self, sentences: List[Dict]) -> List[Dict]:
        """
        对所有句子进行分类
        
        Args:
            sentences: 句子列表
        
        Returns:
            包含类型信息的句子列表
        """
        results = []
        
        for i, sentence in enumerate(sentences):
            segment_type = self.classify(sentences, i)
            results.append({
                **sentence,
                "segment_type": segment_type
            })
        
        return results