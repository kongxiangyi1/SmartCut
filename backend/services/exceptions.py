"""
服务异常模块
定义服务层使用的异常类
"""

from enum import Enum
from typing import Optional, Any


class ServiceErrorCode(str, Enum):
    """服务错误代码枚举"""
    CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_MISSING_REQUIRED = "CONFIG_MISSING_REQUIRED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_PERMISSION_DENIED = "FILE_PERMISSION_DENIED"
    FILE_CORRUPTED = "FILE_CORRUPTED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    STEP_EXECUTION_FAILED = "STEP_EXECUTION_FAILED"
    PIPELINE_VALIDATION_FAILED = "PIPELINE_VALIDATION_FAILED"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_ALREADY_RUNNING = "TASK_ALREADY_RUNNING"
    TASK_CANCELLED = "TASK_CANCELLED"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    PROJECT_ALREADY_EXISTS = "PROJECT_ALREADY_EXISTS"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    CONCURRENT_ACCESS = "CONCURRENT_ACCESS"
    LOCK_ACQUISITION_FAILED = "LOCK_ACQUISITION_FAILED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class ServiceError(Exception):
    """服务层异常类"""
    
    def __init__(
        self,
        error_code: ServiceErrorCode,
        message: str,
        details: Optional[dict] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details
        }


class ConfigError(ServiceError):
    """配置错误"""
    def __init__(self, message: str, error_code: ServiceErrorCode = ServiceErrorCode.CONFIG_INVALID):
        super().__init__(error_code, message)


class FileError(ServiceError):
    """文件错误"""
    def __init__(self, message: str, error_code: ServiceErrorCode = ServiceErrorCode.FILE_NOT_FOUND):
        super().__init__(error_code, message)


class ProcessingError(ServiceError):
    """处理错误"""
    def __init__(self, message: str, error_code: ServiceErrorCode = ServiceErrorCode.PROCESSING_FAILED):
        super().__init__(error_code, message)


class PipelineError(ServiceError):
    """流水线错误"""
    def __init__(self, message: str, error_code: ServiceErrorCode = ServiceErrorCode.STEP_EXECUTION_FAILED):
        super().__init__(error_code, message)


class TaskError(ServiceError):
    """任务错误"""
    def __init__(self, message: str, error_code: ServiceErrorCode = ServiceErrorCode.TASK_NOT_FOUND):
        super().__init__(error_code, message)


class ProjectError(ServiceError):
    """项目错误"""
    def __init__(self, message: str, error_code: ServiceErrorCode = ServiceErrorCode.PROJECT_NOT_FOUND):
        super().__init__(error_code, message)


class SystemError(ServiceError):
    """系统错误"""
    def __init__(self, message: str, error_code: ServiceErrorCode = ServiceErrorCode.SYSTEM_ERROR):
        super().__init__(error_code, message)
