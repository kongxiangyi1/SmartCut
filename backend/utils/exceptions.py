"""
产品介绍模块化 - 异常类定义
"""

class ProductDetectionError(Exception):
    """产品识别异常"""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class SegmentClassificationError(Exception):
    """片段分类异常"""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class ReuseLibraryError(Exception):
    """复用库操作异常"""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class ProductKeywordLoaderError(Exception):
    """产品词库加载异常"""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message