"""
智能钩子提取器
用于从视频字幕中提取高质量的开场钩子内容
"""
import re
from typing import List, Dict, Optional
from pathlib import Path

# 钩子模式定义
HOOK_PATTERNS = {
    'greeting': ['大家好', '欢迎来到', '我是', '哈喽', '各位朋友', '亲爱的观众', '朋友们好'],
    'attention': ['注意看', '大家看', '仔细看', '接下来', '我们来看', '一起来看', '请看'],
    'question': ['你知道吗', '为什么', '怎么样', '什么是', '如何', '怎么', '难道', '谁', '哪个'],
    'suspense': ['没想到', '竟然', '其实', '真相', '秘密', '惊人', '震惊', '不可思议'],
    'benefit': ['免费', '福利', '干货', '技巧', '方法', '秘诀', '实用', '高效'],
    'number': ['3个', '5个', '10个', '三大', '五大', '十大', '第一', '最后', '唯一'],
    'contrast': ['vs', '对比', '区别', '不同', '差异', '选择', '哪个更好'],
    'trend': ['最新', '火爆', '趋势', '必看', '重磅', '热点'],
    'interaction': ['评论区', '弹幕', '投票', '留言', '分享', '点赞']
}

class HookExtractor:
    """智能钩子提取器"""
    
    def __init__(self):
        self.hook_config = {
            'max_duration': 12,       # 钩子最大时长（秒）
            'min_duration': 3,        # 钩子最小时长（秒）
            'min_score': 8,           # 最低评分阈值（0-20）
            'enable_optimization': True,
            'optimization_level': 'medium'
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
    
    def _score_hook_candidate(self, candidate: Dict, srt_data: List[Dict], position: int) -> Dict:
        """
        多维度评分系统（0-20分）
        """
        score = 0
        text = candidate['text']
        total_candidates = len(srt_data)
        
        # 1. 钩子模式匹配（最高10分）
        pattern_scores = {
            'greeting': 3,
            'attention': 4,
            'question': 5,
            'suspense': 5,
            'benefit': 5,
            'number': 4,
            'contrast': 3,
            'trend': 3,
            'interaction': 3
        }
        
        for pattern_type, keywords in HOOK_PATTERNS.items():
            for kw in keywords:
                if kw in text:
                    score += pattern_scores.get(pattern_type, 2)
                    candidate['hook_type'] = pattern_type
                    candidate['matched_keyword'] = kw
                    break
        
        # 2. 情感结尾加分（2分）
        if text.endswith(('？', '?', '！', '!', '...', '。')):
            score += 2
        
        # 3. 长度适中加分（2分）
        text_length = len(text)
        if 8 <= text_length <= 25:
            score += 2
        elif 5 <= text_length <= 30:
            score += 1
        
        # 4. 情感强度检测（2分）
        emotion_words = ['太', '超级', '真的', '非常', '绝对', '特别', '极其']
        emotion_count = sum(1 for em in emotion_words if em in text)
        score += min(emotion_count * 1, 2)
        
        # 5. 位置权重（2分）
        position_ratio = position / total_candidates if total_candidates > 0 else 0
        score += int(position_ratio * 2)
        
        # 6. 上下文连贯性（2分）
        if position > 0:
            prev_text = srt_data[position - 1]['text']
            common_chars = len(set(text) & set(prev_text))
            if common_chars / max(len(text), len(prev_text), 1) > 0.3:
                score += 2
        
        candidate['score'] = min(score, 20)
        return candidate
    
    def _is_coherent(self, text1: str, text2: str) -> bool:
        """检测两段文本是否连贯"""
        common_chars = len(set(text1) & set(text2))
        return common_chars / max(len(text1), len(text2), 1) > 0.3
    
    def extract_best_hook(self, srt_data: List[Dict], topic_start_time: str) -> Optional[Dict]:
        """
        从字幕数据中提取最佳钩子
        """
        topic_start_sec = self._time_to_seconds(topic_start_time)
        hook_end_sec = topic_start_sec
        hook_start_sec = max(0, topic_start_sec - self.hook_config['max_duration'])
        
        # 获取候选字幕
        candidates = []
        for i, sub in enumerate(srt_data):
            sub_start = self._time_to_seconds(sub['start_time'])
            sub_end = self._time_to_seconds(sub['end_time'])
            
            if sub_start >= hook_start_sec and sub_end <= hook_end_sec:
                candidates.append({
                    'start_time': sub['start_time'],
                    'end_time': sub['end_time'],
                    'text': sub['text'],
                    'original_index': i
                })
        
        if not candidates:
            return None
        
        # 评分筛选
        scored_candidates = []
        for i, candidate in enumerate(candidates):
            scored = self._score_hook_candidate(candidate, candidates, i)
            scored_candidates.append(scored)
        
        # 选择最高分候选
        best_hook = max(scored_candidates, key=lambda x: x['score'], default=None)
        
        if best_hook and best_hook['score'] >= self.hook_config['min_score']:
            # 优化钩子内容
            if self.hook_config['enable_optimization']:
                best_hook['text'] = self._optimize_hook_content(best_hook['text'], best_hook.get('hook_type'))
            
            return {
                'start_time': best_hook['start_time'],
                'end_time': topic_start_time,
                'text': best_hook['text'],
                'hook_type': best_hook.get('hook_type'),
                'quality_score': best_hook['score'],
                'matched_keyword': best_hook.get('matched_keyword')
            }
        
        return None
    
    def _optimize_hook_content(self, text: str, hook_type: str) -> str:
        """优化钩子内容"""
        # 1. 去除重复内容
        text = self._remove_duplicates(text)
        
        # 2. 优化标点符号
        text = self._optimize_punctuation(text)
        
        # 3. 增强特定类型钩子
        if hook_type == 'benefit':
            text = self._enhance_benefit_hook(text)
        elif hook_type == 'question':
            text = self._enhance_question_hook(text)
        elif hook_type == 'suspense':
            text = self._enhance_suspense_hook(text)
        
        # 4. 添加引导词（仅在长度允许时）
        if len(text) < 30:
            text = self._add_call_to_action(text)
        
        return text
    
    def _remove_duplicates(self, text: str) -> str:
        """去除重复内容"""
        words = text.split()
        seen = set()
        result = []
        for word in words:
            if word not in seen:
                seen.add(word)
                result.append(word)
        return ''.join(result)
    
    def _optimize_punctuation(self, text: str) -> str:
        """优化标点符号"""
        # 统一中文标点
        text = text.replace('!', '！').replace('?', '？')
        # 去除多余空格
        text = re.sub(r'\s+', '', text)
        return text
    
    def _enhance_benefit_hook(self, text: str) -> str:
        """增强利益型钩子"""
        benefit_enhancers = ['免费', '干货', '独家', '实用', '高效', '快速']
        if not any(enhancer in text for enhancer in benefit_enhancers):
            if '技巧' in text:
                text = text.replace('技巧', '实用技巧')
            elif '方法' in text:
                text = text.replace('方法', '高效方法')
            elif '教程' in text:
                text = text.replace('教程', '干货教程')
        return text
    
    def _enhance_question_hook(self, text: str) -> str:
        """增强问题型钩子"""
        if not text.endswith(('？', '?')):
            text += '？'
        return text
    
    def _enhance_suspense_hook(self, text: str) -> str:
        """增强悬念型钩子"""
        suspense_words = ['竟然', '没想到', '真相是', '秘密是']
        if not any(word in text for word in suspense_words):
            text += '，竟然是这样！'
        return text
    
    def _add_call_to_action(self, text: str) -> str:
        """添加行动号召"""
        ctas = ['记得看完', '看到最后', '别走开', '继续看', '精彩在后面']
        if not any(cta in text for cta in ctas):
            text += '，记得看完！'
        return text
    
    def extract_hooks(self, text: str) -> List[Dict]:
        """
        从文本中直接提取钩子（简化版本，不需要SRT数据）
        """
        hooks = []
        
        # 模式匹配
        for hook_type, keywords in HOOK_PATTERNS.items():
            for kw in keywords:
                if kw in text:
                    score = self._calculate_simple_score(text, hook_type)
                    hooks.append({
                        'type': hook_type,
                        'content': text,
                        'score': score,
                        'matched_keyword': kw
                    })
                    break
        
        # 按评分排序
        hooks.sort(key=lambda x: x['score'], reverse=True)
        
        return hooks
    
    def _calculate_simple_score(self, text: str, hook_type: str) -> float:
        """
        简单评分算法（用于直接文本输入）
        """
        score = 0.0
        
        # 基础模式得分
        pattern_scores = {
            'greeting': 3.0,
            'attention': 4.0,
            'question': 5.0,
            'suspense': 5.0,
            'benefit': 5.0,
            'number': 4.0,
            'contrast': 3.0,
            'trend': 3.0,
            'interaction': 3.0
        }
        
        score += pattern_scores.get(hook_type, 2.0)
        
        # 情感结尾加分
        if text.endswith(('？', '?', '！', '!', '...')):
            score += 1.0
        
        # 长度适中加分
        text_length = len(text)
        if 8 <= text_length <= 25:
            score += 1.5
        elif 5 <= text_length <= 30:
            score += 0.5
        
        # 情感强度检测
        emotion_words = ['太', '超级', '真的', '非常', '绝对', '特别', '极其']
        emotion_count = sum(1 for em in emotion_words if em in text)
        score += min(emotion_count * 0.5, 1.5)
        
        return min(score, 10.0)