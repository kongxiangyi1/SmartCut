"""
合集模型
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum, Table, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from enum import Enum as PyEnum
from .base import BaseModel


class CollectionStatus(PyEnum):
    """合集状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# 创建Clip和Collection的多对多关系中间表
clip_collection = Table(
    "clip_collection",
    BaseModel.metadata,
    Column("clip_id", String(36), ForeignKey("clips.id", ondelete="CASCADE"), primary_key=True),
    Column("collection_id", String(36), ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True)
)


class Collection(BaseModel):
    """合集模型"""
    __tablename__ = "collections"

    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    collection_title = Column(String(255), nullable=False)
    collection_summary = Column(Text, nullable=True)
    collection_type = Column(String(50), default="ai_recommended")
    collection_metadata = Column(JSON, nullable=True)
    status = Column(Enum(CollectionStatus), default=CollectionStatus.PENDING)
    
    # 关联关系
    clips = relationship(
        "Clip", 
        secondary=clip_collection,
        back_populates="collections"
    )

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "collection_title": self.collection_title,
            "collection_summary": self.collection_summary,
            "collection_type": self.collection_type,
            "collection_metadata": self.collection_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
