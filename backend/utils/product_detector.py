"""
产品识别器
识别文本中的产品特征信息
"""
import re
import logging
import time
import difflib
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from .product_keyword_loader import ProductKeywordLoader
from .exceptions import ProductDetectionError
from .logging_config import setup_logging, PerformanceMonitor

logger = setup_logging('product_detector')

class ProductDetector:
    """产品识别器"""
    
    def __init__(self, config_path: Path = None):
        self.keyword_loader = ProductKeywordLoader(config_path)
        self._cache = {}
        self._compile_patterns()
        self._build_inverted_index()
        self._build_synonym_mapping()
        self._load_multicategory_keywords()
        self._load_context_hints()
        self._performance_monitor = PerformanceMonitor()
        logger.info("产品识别器初始化完成")
    
    def _build_synonym_mapping(self):
        """
        构建同义词映射表
        优先从YAML配置文件加载，如不存在则使用内置默认值
        """
        self._synonyms = self.keyword_loader.get_synonyms()
        
        # 如果配置文件中没有同义词，则使用默认值
        if not self._synonyms:
            self._synonyms = {
                "手机": ["智能手机", "移动电话", "智能机"],
                "电脑": ["计算机", "笔记本", "台式机", "笔记本电脑"],
                "手表": ["腕表", "智能手表", "手环", "智能手环"],
                "耳机": ["蓝牙耳机", "无线耳机", "耳塞", "耳麦"],
                "充电器": ["快充", "无线充", "充电头", "数据线"],
                "充电宝": ["移动电源"],
                "面霜": ["乳液", "精华", "爽肤水", "眼霜", "精华液"],
                "洗发水": ["洗发露", "洗头膏", "洗发液"],
                "沐浴露": ["沐浴乳", "洗澡液"],
                "牛奶": ["纯牛奶", "鲜奶", "脱脂牛奶", "水牛纯牛奶"],
                "鸡蛋": ["土鸡蛋", "柴鸡蛋", "可生食鸡蛋"],
                "大米": ["米", "白米", "香米", "稻花香大米", "五常大米"],
                "酱油": ["生抽", "老抽", "酱油膏"],
                "醋": ["陈醋", "米醋", "香醋"],
                "智能音箱": ["音箱"],
                "扫地机器人": ["扫地机"],
            }
        logger.info(f"同义词映射表构建完成，共 {len(self._synonyms)} 个标准词")
    
    def _load_multicategory_keywords(self):
        """
        加载多义词映射表
        从YAML配置文件加载，支持一个词属于多个类别
        """
        self._multicategory_keywords = self.keyword_loader.get_multicategory_keywords()
        
        # 如果配置文件中没有，则使用默认值
        if not self._multicategory_keywords:
            self._multicategory_keywords = {
                "手表": ["智能穿戴", "饰品"],
                "项链": ["饰品", "智能穿戴"],
                "戒指": ["饰品", "智能穿戴"],
                "音箱": ["智能穿戴", "家电"],
                "眼镜": ["智能穿戴", "饰品"],
            }
        logger.info(f"多义词映射表加载完成，共 {len(self._multicategory_keywords)} 个词")
    
    def _load_context_hints(self):
        """
        加载上下文提示词映射表
        从YAML配置文件加载，用于根据上下文调整产品权重
        """
        self._context_hints = self.keyword_loader.get_context_hints()
        
        # 如果配置文件中没有，则使用默认值
        if not self._context_hints:
            self._context_hints = {
                "智能": ["智能穿戴", "手机数码", "智能家居"],
                "蓝牙": ["智能穿戴", "手机数码"],
                "便携": ["手机数码", "生活电器"],
                "有机": ["生鲜", "食品"],
                "特价": ["促销"],
                "包邮": ["促销"],
                "买一送一": ["促销"],
                "限时": ["促销"],
                "首饰": ["饰品"],
                "珠宝": ["饰品"],
                "家电": ["生活电器", "厨房电器"],
            }
        logger.info(f"上下文提示词加载完成，共 {len(self._context_hints)} 个提示词")
    
    def _compile_patterns(self):
        """预编译正则表达式"""
        self._price_regexes = [
            re.compile(pattern) for pattern in self.keyword_loader.get_price_patterns()
        ]
        logger.debug(f"预编译价格模式: {len(self._price_regexes)} 个")
    
    def _build_inverted_index(self):
        """
        构建关键词到类别的倒排索引
        同时按关键词长度排序，确保优先匹配更长的关键词
        """
        self._keyword_to_category = {}
        self._sorted_keywords = []
        
        categories = self.keyword_loader.get_categories()
        for category, keywords in categories.items():
            for keyword in keywords:
                self._keyword_to_category[keyword] = category
                self._sorted_keywords.append(keyword)
        
        # 按关键词长度降序排序，确保优先匹配更长的关键词
        self._sorted_keywords.sort(key=lambda x: -len(x))
        logger.info(f"倒排索引构建完成，共 {len(self._sorted_keywords)} 个关键词，{len(categories)} 个类别")
    
    def detect_product_features(self, text: str) -> Dict[str, Any]:
        """
        检测文本中的产品特征
        
        Args:
            text: 输入文本
        
        Returns:
            {
                "product_name": str | None,
                "category": str | None,
                "products": List[Tuple[str, str]] | None,
                "price": str | None,
                "features": List[str],
                "promotion": bool,
                "confidence": float
            }
        """
        start_time = time.time()
        
        try:
            if not text or not isinstance(text, str):
                raise ProductDetectionError("输入文本无效")
            
            # 检查缓存
            if text in self._cache:
                elapsed_time = time.time() - start_time
                self._performance_monitor.record(elapsed_time, self._cache[text]["confidence"])
                return self._cache[text]
            
            # 限制文本长度
            original_length = len(text)
            if len(text) > 1000:
                text = text[:1000]
                logger.warning(f"文本过长（{original_length}字符），已截断处理")
            
            logger.debug(f"开始检测产品特征: {text[:50]}...")
            
            result = {
                "product_name": None,
                "category": None,
                "products": None,
                "price": None,
                "features": [],
                "promotion": False,
                "confidence": 0.0
            }
            
            # 1. 识别产品名称和类别（支持多产品）
            products = self._extract_all_products(text)
            if products:
                result["product_name"] = products[0][0]
                result["category"] = products[0][1]
                result["products"] = products
                logger.debug(f"检测到产品: {products}")
            
            # 2. 提取价格信息
            price = self._extract_price(text)
            result["price"] = price
            if price:
                logger.debug(f"检测到价格: {price}")
            
            # 3. 提取功能特征
            features = self._extract_features(text)
            result["features"] = features
            if features:
                logger.debug(f"检测到特征: {features}")
            
            # 4. 检测促销信息
            promotion = self._detect_promotion(text)
            result["promotion"] = promotion
            if promotion:
                logger.debug("检测到促销信息")
            
            # 5. 计算置信度
            confidence = self._calculate_confidence(result)
            result["confidence"] = confidence
            
            # 缓存结果
            self._cache[text] = result
            
            # 限制缓存大小
            if len(self._cache) > 1000:
                keys = list(self._cache.keys())[:100]
                for key in keys:
                    del self._cache[key]
            
            # 记录性能数据
            elapsed_time = time.time() - start_time
            self._performance_monitor.record(elapsed_time, confidence)
            
            logger.debug(f"检测完成: 产品={result['product_name']}, 置信度={confidence:.2f}, 耗时={elapsed_time*1000:.2f}ms")
            
            return result
        
        except ProductDetectionError as e:
            elapsed_time = time.time() - start_time
            self._performance_monitor.record(elapsed_time, 0.0)
            logger.error(f"产品识别失败: {e}")
            return {"confidence": 0.0}
        except Exception as e:
            elapsed_time = time.time() - start_time
            self._performance_monitor.record(elapsed_time, 0.0)
            logger.error(f"产品识别异常: {e}", exc_info=True)
            return {"confidence": 0.0}
    
    def get_performance_stats(self) -> dict:
        """
        获取性能统计信息
        
        Returns:
            性能统计字典
        """
        return self._performance_monitor.get_stats()
    
    def reset_performance_stats(self):
        """重置性能统计"""
        self._performance_monitor.reset()
    
    def _expand_query_with_synonyms(self, text: str) -> str:
        """
        使用同义词扩展查询文本
        将同义词替换为标准词，提升检测灵活性
        
        Args:
            text: 原始文本
        
        Returns:
            扩展后的文本（同义词已替换为标准词）
        """
        expanded_text = text
        for standard_word, synonyms in self._synonyms.items():
            for synonym in synonyms:
                if synonym in expanded_text:
                    # 记录同义词替换
                    logger.debug(f"同义词替换: {synonym} -> {standard_word}")
                    expanded_text = expanded_text.replace(synonym, standard_word)
        return expanded_text
    
    _fuzzy_match_PHONETIC_ERRORS = {
        "蓝芽": "蓝牙",
        "平果": "苹果",
        "岩糖": "果糖",
        "鸡胸": "鸡胸肉",
        "智手表": "智能手表",
        "智手环": "智能手环",
        "智眼镜": "智能眼镜",
        "智音箱": "智能音箱",
        "智耳机": "智能耳机",
    }
    
    def _fuzzy_match(self, text: str, threshold: float = 0.65) -> List[Tuple[str, str]]:
        """
        模糊匹配产品关键词
        支持前缀匹配、谐音错字处理、编辑距离优化
        
        Args:
            text: 输入文本
            threshold: 相似度阈值（0-1，越高越严格）
        
        Returns:
            匹配的产品列表 [(产品名, 类别), ...]
        """
        matches = []
        text_words = text.split()
        seen_keywords = set()
        
        for keyword in self._sorted_keywords:
            if len(keyword) < 3 or keyword in seen_keywords:
                continue
            
            # 检查是否有更长的关键词包含此关键词（避免"手表"先匹配"智能手表"）
            has_longer_match = False
            for other_keyword in self._sorted_keywords:
                if other_keyword != keyword and len(other_keyword) > len(keyword):
                    if keyword in other_keyword and keyword in text_words:
                        has_longer_match = True
                        break
            if has_longer_match:
                continue
            
            for word in text_words:
                if len(word) < 2:
                    continue
                
                # 方法1: 检查谐音错字映射（如"蓝芽" -> "蓝牙"）
                if word in self._fuzzy_match_PHONETIC_ERRORS:
                    corrected = self._fuzzy_match_PHONETIC_ERRORS[word]
                    if corrected == keyword:
                        matches.append((keyword, self._keyword_to_category[keyword]))
                        seen_keywords.add(keyword)
                        logger.debug(f"谐音匹配: '{word}' -> '{keyword}'")
                        break
                    continue
                
                # 方法2: 前缀匹配优化（如"智手表" -> "智能手表"）
                # 检查输入词的前2-3个字符是否与关键词的前缀匹配
                if len(word) >= 2 and len(keyword) > len(word):
                    # 取word的前2个字符检查是否匹配keyword的前缀
                    word_prefix = word[:2]
                    if keyword.startswith(word_prefix) and len(keyword) >= 3:
                        # 进一步检查：如果word是keyword的子串，给予高置信度
                        if word in keyword:
                            similarity = 0.85
                            matches.append((keyword, self._keyword_to_category[keyword]))
                            seen_keywords.add(keyword)
                            logger.debug(f"前缀子串匹配: '{word}' -> '{keyword}' (相似度: {similarity:.2f})")
                            break
                        # 检查是否只是缺少某个字符
                        for i in range(len(keyword)):
                            if keyword[:i] + keyword[i+1:] == word:
                                similarity = 0.82
                                matches.append((keyword, self._keyword_to_category[keyword]))
                                seen_keywords.add(keyword)
                                logger.debug(f"缺字符匹配: '{word}' -> '{keyword}' (相似度: {similarity:.2f})")
                                break
                
                # 方法3: 直接相似度匹配
                similarity = difflib.SequenceMatcher(None, keyword, word).ratio()
                
                # 方法4: 检查是否有单字符替换（如"蓝芽" -> "蓝牙"）
                if len(word) == len(keyword) and len(word) >= 3:
                    diff_count = sum(c1 != c2 for c1, c2 in zip(word, keyword))
                    if diff_count == 1:
                        similarity = max(similarity, 0.85)
                
                # 方法5: 长度差异容忍（长词允许更多差异）
                if len(keyword) >= 4 and len(word) >= 3:
                    len_diff = abs(len(keyword) - len(word))
                    if len_diff <= 1:
                        similarity = max(similarity, 0.7)
                
                if similarity >= threshold:
                    category = self._keyword_to_category[keyword]
                    matches.append((keyword, category))
                    seen_keywords.add(keyword)
                    logger.debug(f"模糊匹配: '{word}' -> '{keyword}' (相似度: {similarity:.2f})")
                    break
        
        return matches
    
    def _extract_all_products_with_weight(self, text: str) -> List[Tuple[str, str, float]]:
        """
        提取文本中所有匹配的产品名称、类别及权重
        权重因素：出现频率(40%) + 文本位置(30%) + 关键词长度(30%)
        
        Args:
            text: 输入文本
        
        Returns:
            产品列表 [(产品名, 类别, 权重), ...]，按权重降序排序
        """
        products = []
        found_keywords = set()
        text_length = len(text) if text else 1
        
        for keyword in self._sorted_keywords:
            if keyword in text and keyword not in found_keywords:
                # 计算各因素
                frequency = text.count(keyword)
                position = text.find(keyword) / text_length  # 位置越靠前值越小
                keyword_length = len(keyword)
                
                # 计算权重（归一化处理）
                freq_score = min(frequency * 0.2, 0.4)  # 最高0.4
                pos_score = (1 - position) * 0.3  # 最高0.3
                len_score = min(keyword_length * 0.05, 0.3)  # 最高0.3
                
                weight = freq_score + pos_score + len_score
                
                category = self._keyword_to_category[keyword]
                products.append((keyword, category, weight))
                found_keywords.add(keyword)
                logger.debug(f"产品权重计算: {keyword} -> {weight:.3f}")
        
        # 按权重降序排序
        products.sort(key=lambda x: -x[2])
        return products
    
    def _remove_negative_context(self, text: str) -> str:
        """
        去除否定词影响范围内的产品词
        支持排除"不买"、"没有"等否定词后的产品
        
        Args:
            text: 原始文本
        
        Returns:
            去除否定语境后的文本
        """
        negative_patterns = [
            (r"不买(\S+?)买", r"买"),      # 不买A买B -> 买B
            (r"不买(\S+?)要", r"要"),      # 不买A要B -> 要B
            (r"不要(\S+?)要", r"要"),      # 不要A要B -> 要B
            (r"不要(\S+?)买", r"买"),      # 不要A买B -> 买B
            (r"不要(\S+?)，", r"，"),      # 不要A，... -> ，...
            (r"没有(\S+?)有", r"有"),      # 没有A有B -> 有B
            (r"没有(\S+?)要", r"要"),      # 没有A要B -> 要B
            (r"不喜欢(\S+?)喜欢", r"喜欢"),# 不喜欢A喜欢B -> 喜欢B
            (r"不喜欢(\S+?)要", r"要"),    # 不喜欢A要B -> 要B
        ]
        
        result = text
        
        import re
        for pattern, replacement in negative_patterns:
            result = re.sub(pattern, replacement, result)
        
        # 处理纯否定情况
        pure_negative_patterns = [
            r"不买任何东西",
            r"没有想买的",
            r"什么都不买",
            r"什么都不要",
        ]
        
        for pattern in pure_negative_patterns:
            if pattern in result:
                return ""
        
        return result.strip()
    
    def _resolve_multiple_categories(self, keyword: str, context: str) -> str:
        """
        根据上下文解析多义词的类别
        
        Args:
            keyword: 多义词
            context: 上下文文本
        
        Returns:
            解析后的类别
        """
        if keyword not in self._multicategory_keywords:
            return self._keyword_to_category.get(keyword)
        
        categories = self._multicategory_keywords[keyword]
        
        # 根据上下文提示词判断类别
        for hint_word, relevant_categories in self._context_hints.items():
            if hint_word in context:
                for category in categories:
                    if category in relevant_categories:
                        logger.debug(f"多义词解析: '{keyword}' -> '{category}' (根据上下文: {hint_word})")
                        return category
        
        # 默认返回第一个类别
        return categories[0]
    
    def _adjust_weight_by_context(self, products: List[Tuple[str, str, float]], text: str) -> List[Tuple[str, str, float]]:
        """
        根据上下文调整产品权重
        
        Args:
            products: 产品列表 [(产品名, 类别, 权重), ...]
            text: 上下文文本
        
        Returns:
            调整权重后的产品列表
        """
        adjusted_products = []
        
        for product, category, weight in products:
            adjusted_weight = weight
            
            # 根据上下文提示词调整权重
            for hint_word, relevant_categories in self._context_hints.items():
                if hint_word in text and category in relevant_categories:
                    adjusted_weight *= 1.2  # 权重提升20%
                    logger.debug(f"上下文权重调整: '{product}' * 1.2 (提示词: {hint_word})")
            
            # 确保权重不超过1.0
            adjusted_products.append((product, category, min(adjusted_weight, 1.0)))
        
        return adjusted_products
    
    def _extract_all_products(self, text: str) -> List[Tuple[str, str]]:
        """
        提取文本中所有匹配的产品名称和类别
        使用倒排索引、同义词扩展、否定词处理、上下文感知和多义词解析
        
        Args:
            text: 输入文本
        
        Returns:
            产品列表 [(产品名, 类别), ...]，保持原始文本中的具体名称
        """
        # 1. 去除否定语境
        cleaned_text = self._remove_negative_context(text)
        
        # 1.5 预先进行模糊匹配，找出可能映射的关键词
        fuzzy_matches = self._fuzzy_match(cleaned_text)
        fuzzy_keywords = set(kw for kw, _ in fuzzy_matches)
        logger.debug(f"模糊匹配预结果: {fuzzy_keywords}")
        
        found_products = []
        found_keywords = set()
        text_length = len(cleaned_text) if cleaned_text else 1
        
        # 2. 从清理后的文本中检测具体的产品名称（保留原始名称）
        for keyword in self._sorted_keywords:
            # 检查关键词是否在文本中
            if keyword not in cleaned_text or keyword in found_keywords:
                continue
            
            # 检查是否有更长的关键词也包含此关键词且在文本中
            # 或者是否有模糊匹配到的更长的关键词
            has_longer_in_text = False
            for other_keyword in self._sorted_keywords:
                if other_keyword != keyword and len(other_keyword) > len(keyword):
                    if keyword in other_keyword and other_keyword in cleaned_text:
                        has_longer_in_text = True
                        logger.debug(f"跳过短关键词: '{keyword}' (有更长匹配 '{other_keyword}')")
                        break
            
            # 额外检查：如果有模糊匹配到的更长的关键词包含此关键词，也跳过
            if not has_longer_in_text:
                for fuzzy_kw in fuzzy_keywords:
                    if keyword in fuzzy_kw and len(fuzzy_kw) > len(keyword):
                        has_longer_in_text = True
                        logger.debug(f"跳过短关键词(模糊匹配): '{keyword}' (有模糊匹配 '{fuzzy_kw}')")
                        break
            
            if has_longer_in_text:
                continue
            
            # 计算权重
            frequency = cleaned_text.count(keyword)
            position = cleaned_text.find(keyword) / text_length
            keyword_length = len(keyword)
            
            freq_score = min(frequency * 0.2, 0.4)
            pos_score = (1 - position) * 0.3
            len_score = min(keyword_length * 0.05, 0.3)
            weight = freq_score + pos_score + len_score
            
            # 处理多义词
            category = self._resolve_multiple_categories(keyword, text)
            if category:
                found_products.append((keyword, category, weight))
                found_keywords.add(keyword)
        
        # 3. 使用同义词检测（返回标准词作为补充）
        for standard_word, synonyms in self._synonyms.items():
            for synonym in synonyms:
                if synonym in cleaned_text and standard_word not in found_keywords:
                    if standard_word in self._keyword_to_category:
                        position = cleaned_text.find(synonym) / text_length
                        weight = 0.4 + (1 - position) * 0.2
                        
                        category = self._resolve_multiple_categories(standard_word, text)
                        if category:
                            found_products.append((standard_word, category, weight))
                            found_keywords.add(standard_word)
        
        # 4. 添加模糊匹配结果（作为补充）
        for word in cleaned_text.split():
            if len(word) < 2:
                continue
            
            for keyword in self._sorted_keywords:
                if keyword in found_keywords or len(keyword) < 3:
                    continue
                
                similarity = difflib.SequenceMatcher(None, keyword, word).ratio()
                if similarity >= 0.75:
                    category = self._resolve_multiple_categories(keyword, text)
                    if category:
                        found_products.append((keyword, category, 0.25 + similarity * 0.1))
                        found_keywords.add(keyword)
                        logger.debug(f"模糊匹配: '{word}' -> '{keyword}' (相似度: {similarity:.2f})")
        
        # 5. 根据上下文调整权重
        found_products = self._adjust_weight_by_context(found_products, text)
        
        # 6. 按权重降序排序
        found_products.sort(key=lambda x: -x[2])
        
        # 7. 返回产品名称和类别（去除权重）
        return [(p[0], p[1]) for p in found_products]
    
    def _extract_product_name(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """提取产品名称和类别（兼容旧接口）"""
        products = self._extract_all_products(text)
        if products:
            return products[0]
        return None, None
    
    def _extract_price(self, text: str) -> Optional[str]:
        """提取价格信息"""
        for regex in self._price_regexes:
            match = regex.search(text)
            if match:
                return match.group()
        return None
    
    def _extract_features(self, text: str) -> List[str]:
        """提取功能特征"""
        features = []
        
        function_keywords = self.keyword_loader.get_function_keywords()
        for keyword in function_keywords:
            if keyword in text:
                features.append(keyword)
        
        for keyword in self._sorted_keywords:
            if keyword in text and keyword not in features:
                features.append(keyword)
        
        return features
    
    def _detect_promotion(self, text: str) -> bool:
        """检测促销信息"""
        promotion_keywords = self.keyword_loader.get_promotion_keywords()
        return any(keyword in text for keyword in promotion_keywords)
    
    def _calculate_confidence(self, features: Dict[str, Any]) -> float:
        """计算识别置信度"""
        score = 0.0
        
        if features.get("product_name"):
            score += 0.3
            products = features.get("products", [])
            if len(products) > 1:
                score += min(0.2, len(products) * 0.05)
        
        if features.get("price"):
            score += 0.2
        
        feature_list = features.get("features", [])
        if feature_list:
            score += 0.2 + min(0.1, len(feature_list) * 0.02)
        
        if features.get("promotion"):
            score += 0.2
        
        return min(1.0, score)
