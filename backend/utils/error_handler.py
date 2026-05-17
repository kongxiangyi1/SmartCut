"""
错误处理器模块
提供统一的错误处理和异常类
"""

from enum import Enum
from typing import Optional


class ErrorCategory(str, Enum):
    """错误类别枚举"""
    VALIDATION = "validation"
    DATABASE = "database"
    EXTERNAL_API = "external_api"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    PROCESSING = "processing"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ErrorLevel(str, Enum):
    """错误级别枚举"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AutoClipsException(Exception):
    """AutoClip自定义异常类"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        level: ErrorLevel = ErrorLevel.ERROR,
        error_code: Optional[str] = None,
        details: Optional[dict] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.level = level
        self.error_code = error_code
        self.details = details or {}
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "message": self.message,
            "category": self.category.value,
            "level": self.level.value,
            "error_code": self.error_code,
            "details": self.details
        }


class ValidationError(AutoClipsException):
    """验证错误"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            level=ErrorLevel.WARNING,
            details=details
        )


class DatabaseError(AutoClipsException):
    """数据库错误"""
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(
            message,
            category=ErrorCategory.DATABASE,
            level=ErrorLevel.ERROR,
            error_code=error_code
        )


class ExternalAPIError(AutoClipsException):
    """外部API错误"""
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[dict] = None):
        super().__init__(
            message,
            category=ErrorCategory.EXTERNAL_API,
            level=ErrorLevel.ERROR,
            error_code=error_code,
            details=details
        )


class AuthenticationError(AutoClipsException):
    """认证错误"""
    def __init__(self, message: str):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            level=ErrorLevel.WARNING
        )


class AuthorizationError(AutoClipsException):
    """授权错误"""
    def __init__(self, message: str):
        super().__init__(
            message,
            category=ErrorCategory.AUTHORIZATION,
            level=ErrorLevel.WARNING
        )


class ProcessingError(AutoClipsException):
    """处理错误"""
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[dict] = None):
        super().__init__(
            message,
            category=ErrorCategory.PROCESSING,
            level=ErrorLevel.ERROR,
            error_code=error_code,
            details=details
        )


class SystemError(AutoClipsException):
    """系统错误"""
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            level=ErrorLevel.CRITICAL,
            error_code=error_code
        )
