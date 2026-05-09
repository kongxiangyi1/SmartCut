"""
产品词库加载器
支持从外部配置文件加载产品关键词
"""
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any

from .exceptions import ProductKeywordLoaderError

logger = logging.getLogger(__name__)

class ProductKeywordLoader:
    """产品词库加载器"""
    
    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "data" / "product_keywords.yaml"
        self.config_path = config_path
        self.keywords: Dict[str, Any] = {}
        self._load_keywords()
    
    def _load_keywords(self):
        """加载词库配置"""
        try:
            if not self.config_path.exists():
                raise ProductKeywordLoaderError(f"词库配置文件不存在: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.keywords = yaml.safe_load(f)
            
            logger.info(f"产品词库加载成功，包含 {len(self.keywords.get('categories', {}))} 个类别")
        
        except ProductKeywordLoaderError:
            raise
        except Exception as e:
            raise ProductKeywordLoaderError(f"词库加载失败: {str(e)}")
    
    def reload(self):
        """重新加载词库"""
        self._load_keywords()
        logger.info("产品词库已重新加载")
    
    def get_categories(self) -> Dict[str, List[str]]:
        """获取所有产品类别"""
        return self.keywords.get('categories', {})
    
    def get_category_keywords(self, category: str) -> List[str]:
        """获取指定类别的关键词"""
        return self.keywords.get('categories', {}).get(category, [])
    
    def get_price_patterns(self) -> List[str]:
        """获取价格匹配模式"""
        return self.keywords.get('price_patterns', [])
    
    def get_promotion_keywords(self) -> List[str]:
        """获取促销关键词"""
        return self.keywords.get('promotion_keywords', [])
    
    def get_function_keywords(self) -> List[str]:
        """获取功能关键词"""
        return self.keywords.get('function_keywords', [])
    
    def get_synonyms(self) -> Dict[str, List[str]]:
        """获取同义词映射表"""
        return self.keywords.get('synonyms', {})
    
    def get_multicategory_keywords(self) -> Dict[str, List[str]]:
        """获取多义词映射表"""
        return self.keywords.get('multicategory_keywords', {})
    
    def get_context_hints(self) -> Dict[str, List[str]]:
        """获取上下文提示词映射表"""
        return self.keywords.get('context_hints', {})
    
    def get_all_product_names(self) -> List[str]:
        """获取所有产品名称"""
        all_names = []
        for category, names in self.get_categories().items():
            all_names.extend(names)
        return all_names