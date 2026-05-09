"""
日志配置模块
配置应用程序的日志记录
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

def setup_logging(name: str = 'product_detector', log_level: int = logging.DEBUG) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        log_level: 日志级别
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 确保日志目录存在
    os.makedirs('logs', exist_ok=True)
    
    # 文件处理器（保留最近5个日志文件，每个最大10MB）
    file_handler = RotatingFileHandler(
        'logs/product_detector.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台处理器（设置 UTF-8 编码以支持 emoji）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    # 修复 Windows 控制台 Unicode 编码问题
    console_handler.stream = open(1, 'w', encoding='utf-8', closefd=False)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

class PerformanceMonitor:
    """
    性能监控器
    用于记录和统计检测性能指标
    """
    
    def __init__(self):
        self._total_calls = 0
        self._total_time = 0.0
        self._min_time = float('inf')
        self._max_time = 0.0
        self._confidence_sum = 0.0
    
    def record(self, elapsed_time: float, confidence: float = 0.0):
        """
        记录单次调用
        
        Args:
            elapsed_time: 耗时（秒）
            confidence: 检测置信度
        """
        self._total_calls += 1
        self._total_time += elapsed_time
        self._min_time = min(self._min_time, elapsed_time)
        self._max_time = max(self._max_time, elapsed_time)
        self._confidence_sum += confidence
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        if self._total_calls == 0:
            return {}
        
        return {
            "total_calls": self._total_calls,
            "avg_time_ms": round((self._total_time / self._total_calls) * 1000, 2),
            "min_time_ms": round(self._min_time * 1000, 2),
            "max_time_ms": round(self._max_time * 1000, 2),
            "total_time_ms": round(self._total_time * 1000, 2),
            "throughput": round(self._total_calls / max(self._total_time, 0.0001), 2),
            "avg_confidence": round(self._confidence_sum / self._total_calls, 2)
        }
    
    def reset(self):
        """重置统计数据"""
        self._total_calls = 0
        self._total_time = 0.0
        self._min_time = float('inf')
        self._max_time = 0.0
        self._confidence_sum = 0.0
