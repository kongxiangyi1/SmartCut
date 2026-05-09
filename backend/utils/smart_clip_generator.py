"""
智能切片生成器
实现钩子+话题+产品复用的切片策略
"""
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

from .hook_extractor import HookExtractor

logger = logging.getLogger(__name__)

# 产品关键词库
PRODUCT_KEYWORDS = {
    'purchase': ['链接', '购买', '点击', '下单', '购物车', '小黄车', '购物袋'],
    'promotion': ['优惠', '福利', '限时', '特价', '秒杀', '折扣', '满减'],
    'product': ['商品', '推荐', '好物', '神器', '必备', '精选'],
    'brand': ['品牌', '官方', '正品', '旗舰店', '授权']
}

class SmartClipGenerator:
    """智能切片生成器"""
    
    def __init__(self):
        self.hook_extractor = HookExtractor()
        self.product_config = {
            'min_duration': 5,
            'max_search_range': 300,
            'min_confidence': 0.5,
            'score_weights': {
                'time': 0.3,
                'semantic': 0.3,
                'confidence': 0.2,
                'position': 0.2
            }
        }
    
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
    
    def extract_all_product_pitches(self, srt_data: List[Dict]) -> List[Dict]:
        """
        提取视频中所有产品/带货内容
        """
        product_pitches = []
        current_pitch = None
        
        for i, sub in enumerate(srt_data):
            text = sub['text']
            
            # 检测是否包含产品相关关键词
            matched_categories = []
            for category, keywords in PRODUCT_KEYWORDS.items():
                if any(kw in text for kw in keywords):
                    matched_categories.append(category)
            
            if matched_categories:
                if current_pitch is None:
                    current_pitch = {
                        'start_time': sub['start_time'],
                        'end_time': sub['end_time'],
                        'text': text,
                        'categories': matched_categories,
                        'confidence': self._calculate_product_confidence(matched_categories, text)
                    }
                else:
                    current_pitch['end_time'] = sub['end_time']
                    current_pitch['text'] += ' ' + text
                    current_pitch['categories'] = list(set(current_pitch['categories'] + matched_categories))
            
            elif current_pitch:
                duration = self._time_to_seconds(current_pitch['end_time']) - \
                          self._time_to_seconds(current_pitch['start_time'])
                
                if duration >= self.product_config['min_duration']:
                    product_pitches.append(current_pitch)
                
                current_pitch = None
        
        # 按置信度排序
        product_pitches.sort(key=lambda x: x['confidence'], reverse=True)
        
        logger.info(f"提取到 {len(product_pitches)} 个产品片段")
        return product_pitches
    
    def _calculate_product_confidence(self, categories: List[str], text: str) -> float:
        """计算产品片段置信度"""
        score = 0.0
        
        # 类别数量加分
        score += len(categories) * 0.2
        
        # 关键词密度加分
        keyword_count = sum(1 for cat in categories 
                           for kw in PRODUCT_KEYWORDS[cat] 
                           if kw in text)
        score += min(keyword_count * 0.1, 0.3)
        
        # 长度加分（适中长度更好）
        text_length = len(text)
        if 20 <= text_length <= 100:
            score += 0.3
        elif text_length > 100:
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的语义相似度"""
        words1 = set(text1.replace('，', ' ').replace('。', ' ').split())
        words2 = set(text2.replace('，', ' ').replace('。', ' ').split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return 0.0
        
        jaccard_score = len(intersection) / len(union)
        
        # 额外考虑产品关键词匹配
        product_keywords_flat = [kw for cat in PRODUCT_KEYWORDS.values() for kw in cat]
        topic_keywords = [w for w in words1 if w in product_keywords_flat]
        product_keywords_found = [w for w in words2 if w in product_keywords_flat]
        
        if topic_keywords and product_keywords_found:
            jaccard_score += 0.1
        
        return min(jaccard_score, 1.0)
    
    def _extract_topic_text(self, topic: Dict, srt_data: List[Dict]) -> str:
        """提取话题对应的字幕文本"""
        topic_start = self._time_to_seconds(topic['start_time'])
        topic_end = self._time_to_seconds(topic['end_time'])
        
        topic_text = ''
        for sub in srt_data:
            sub_start = self._time_to_seconds(sub['start_time'])
            sub_end = self._time_to_seconds(sub['end_time'])
            
            if sub_start >= topic_start and sub_end <= topic_end:
                topic_text += sub['text'] + ' '
        
        return topic_text.strip()
    
    def find_best_product_match(self, topic: Dict, product_pitches: List[Dict], 
                               srt_data: List[Dict]) -> Optional[Dict]:
        """
        为话题找到最佳匹配的产品片段
        """
        if not product_pitches:
            return None
        
        topic_end_sec = self._time_to_seconds(topic['end_time'])
        topic_text = self._extract_topic_text(topic, srt_data)
        
        best_match = None
        best_score = -1
        
        for product in product_pitches:
            product_start_sec = self._time_to_seconds(product['start_time'])
            
            # 1. 时间距离分数（0-1）
            time_distance = abs(product_start_sec - topic_end_sec)
            time_score = max(0, 1 - time_distance / self.product_config['max_search_range'])
            
            # 2. 语义相似度分数（0-1）
            semantic_score = self._calculate_semantic_similarity(topic_text, product['text'])
            
            # 3. 置信度分数
            confidence_score = product.get('confidence', 0.5)
            
            # 4. 位置相关性分数（0-1）
            position_score = 1 if product_start_sec >= topic_end_sec else 0.7
            
            # 综合评分
            weights = self.product_config['score_weights']
            total_score = (
                time_score * weights['time'] +
                semantic_score * weights['semantic'] +
                confidence_score * weights['confidence'] +
                position_score * weights['position']
            )
            
            if total_score > best_score and total_score >= self.product_config['min_confidence']:
                best_score = total_score
                best_match = {**product, 'match_score': total_score}
        
        return best_match
    
    def generate_clips(self, topics: List[Dict], srt_data: List[Dict]) -> List[Dict]:
        """
        生成完整切片：钩子 + 核心话题 + 产品引导
        """
        # 1. 提取所有产品片段
        product_pitches = self.extract_all_product_pitches(srt_data)
        
        clips = []
        
        for topic in topics:
            # 2. 提取钩子
            hook = self.hook_extractor.extract_best_hook(srt_data, topic['start_time'])
            
            # 3. 匹配产品
            product = self.find_best_product_match(topic, product_pitches, srt_data)
            
            # 4. 计算切片时间范围
            clip_start = hook['start_time'] if hook else topic['start_time']
            clip_end = product['end_time'] if product else topic['end_time']
            
            # 5. 计算时长
            duration = self._time_to_seconds(clip_end) - self._time_to_seconds(clip_start)
            
            clip = {
                'topic_id': topic.get('id'),
                'topic_title': topic.get('outline', topic.get('title', '未命名')),
                'hook': hook,
                'topic_content': {
                    'start_time': topic['start_time'],
                    'end_time': topic['end_time']
                },
                'product_pitch': product,
                'start_time': clip_start,
                'end_time': clip_end,
                'duration': duration,
                'product_reused': product is not None,
                'product_id': product.get('id') if product else None,
                'quality_score': hook['quality_score'] if hook else 0
            }
            
            clips.append(clip)
            logger.info(f"生成切片: {clip['topic_title']} (时长: {duration:.2f}秒, 有钩子: {hook is not None}, 有产品: {product is not None})")
        
        return clips