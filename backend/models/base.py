"""
基础模型类
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
import uuid

# 从core.database导入Base，确保所有模型使用同一个Base对象
from backend.core.database import Base


class BaseModel(Base):
    """基础模型类，提供通用字段"""

    __abstract__ = True  # 这是一个抽象基类，不会创建表

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="唯一标识符"
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="创建时间"
    )

    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="更新时间"
    )
