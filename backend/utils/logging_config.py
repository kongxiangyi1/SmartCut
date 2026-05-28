"""
日志配置
用于设置应用程序的日志记录
"""

import logging
import os
import sys
import io
from logging.handlers import RotatingFileHandler


def setup_logging(level: str = "INFO") -> None:
    """
    设置日志配置

    Args:
        level: 日志级别，默认为 INFO
    """
    # 获取日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 创建日志目录（项目根目录下的logs文件夹）
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)

    # 配置日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有的处理器
    root_logger.handlers.clear()

    # 创建控制台处理器（设置UTF-8编码避免Windows乱码）
    if sys.platform == "win32":
        # Windows系统强制UTF-8编码
        console_handler = logging.StreamHandler(stream=io.TextIOWrapper(
            sys.stdout.buffer, encoding='utf-8', errors='replace'
        ))
    else:
        console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 创建文件处理器（带轮转）
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=1024 * 1024 * 50,  # 50MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 设置特定模块的日志级别
    logging.getLogger("uvicorn").setLevel(log_level)
    logging.getLogger("fastapi").setLevel(log_level)
