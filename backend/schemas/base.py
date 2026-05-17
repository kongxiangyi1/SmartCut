"""
基础 Pydantic 模式
"""

from datetime import datetime
from typing import Optional, Generic, TypeVar
from pydantic import BaseModel, Field


class BaseSchema(BaseModel):
    """基础模式类"""
    
    class Config:
        from_attributes = True


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")


class PaginationResponse(BaseModel, Generic[TypeVar('T')]):
    """分页响应"""
    total: int = Field(0, description="总数量")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(10, description="每页数量")
    total_pages: int = Field(0, description="总页数")
