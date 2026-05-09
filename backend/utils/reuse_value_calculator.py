"""
复用价值计算器
计算片段的复用价值
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ReuseValueCalculator:
    """复用价值计算器"""
    
    # 评分权重配置
    WEIGHTS = {
        "product_name": 0.4,      # 产品名称
        "price": 0.2,            # 价格信息
        "features": 0.25,        # 功能描述
        "promotion": 0.15        # 促销信息
    }
    
    def calculate(self, features: Dict[str, Any]) -> float:
        """
        计算复用价值
        
        Args:
            features: 产品特征字典
        
        Returns:
            复用价值 (0-1)
        """
        try:
            score = 0.0
            
            # 产品名称
            if features.get("product_name"):
                score += self.WEIGHTS["product_name"]
            
            # 价格信息
            if features.get("price"):
                score += self.WEIGHTS["price"]
            
            # 功能描述（根据特征数量调整）
            feature_count = len(features.get("features", []))
            if feature_count > 0:
                score += self.WEIGHTS["features"] * min(feature_count / 3, 1.0)
            
            # 促销信息
            if features.get("promotion"):
                score += self.WEIGHTS["promotion"]
            
            return min(1.0, round(score, 2))
        
        except Exception as e:
            logger.error(f"复用价值计算异常: {e}")
            return 0.0
    
    def get_score_breakdown(self, features: Dict[str, Any]) -> Dict[str, float]:
        """
        获取评分明细
        
        Args:
            features: 产品特征字典
        
        Returns:
            各维度评分明细
        """
        breakdown = {}
        
        # 产品名称
        breakdown["product_name"] = {
            "score": self.WEIGHTS["product_name"] if features.get("product_name") else 0.0,
            "weight": self.WEIGHTS["product_name"],
            "has_feature": bool(features.get("product_name"))
        }
        
        # 价格信息
        breakdown["price"] = {
            "score": self.WEIGHTS["price"] if features.get("price") else 0.0,
            "weight": self.WEIGHTS["price"],
            "has_feature": bool(features.get("price"))
        }
        
        # 功能描述
        feature_count = len(features.get("features", []))
        features_score = self.WEIGHTS["features"] * min(feature_count / 3, 1.0)
        breakdown["features"] = {
            "score": features_score,
            "weight": self.WEIGHTS["features"],
            "has_feature": feature_count > 0,
            "feature_count": feature_count
        }
        
        # 促销信息
        breakdown["promotion"] = {
            "score": self.WEIGHTS["promotion"] if features.get("promotion") else 0.0,
            "weight": self.WEIGHTS["promotion"],
            "has_feature": bool(features.get("promotion"))
        }
        
        # 总分
        breakdown["total"] = {
            "score": self.calculate(features),
            "max_score": 1.0
        }
        
        return breakdown
    
    def is_high_reuse(self, features: Dict[str, Any], threshold: float = 0.6) -> bool:
        """
        判断是否为高复用价值片段
        
        Args:
            features: 产品特征字典
            threshold: 阈值
        
        Returns:
            是否为高复用价值
        """
        return self.calculate(features) >= threshold