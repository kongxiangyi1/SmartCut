"""
项目模型
定义项目的基本信息和状态
"""

import enum
from typing import Optional, List
from sqlalchemy import Column, String, Float, Enum, JSON, DateTime, Text, Boolean, Integer
from sqlalchemy.orm import relationship
from .base import BaseModel


class ProjectType(str, enum.Enum):
    """项目类型枚举"""
    DEFAULT = "default"           # 默认类型
    KNOWLEDGE = "knowledge"       # 知识类
    BUSINESS = "business"         # 商业类
    OPINION = "opinion"           # 观点类
    EXPERIENCE = "experience"     # 经验类
    SPEECH = "speech"             # 演讲类
    CONTENT_REVIEW = "content_review"  # 内容评论
    ENTERTAINMENT = "entertainment"    # 娱乐类
    UPLOAD = "upload"             # 上传视频
    BILIBILI = "bilibili"         # B站视频
    YOUTUBE = "youtube"           # YouTube视频


class ProjectStatus(str, enum.Enum):
    """项目状态枚举"""
    PENDING = "pending"           # 待处理
    PROCESSING = "processing"     # 处理中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消


class Project(BaseModel):
    """项目模型"""
    
    __tablename__ = "projects"
    
    # 基本信息
    name = Column(
        String(255), 
        nullable=False, 
        comment="项目名称"
    )
    description = Column(
        Text, 
        nullable=True, 
        comment="项目描述"
    )
    
    # 类型信息
    project_type = Column(
        Enum(ProjectType), 
        default=ProjectType.UPLOAD,
        nullable=False,
        comment="项目类型"
    )
    
    # 状态信息
    status = Column(
        Enum(ProjectStatus), 
        default=ProjectStatus.PENDING,
        nullable=False,
        comment="项目状态"
    )
    
    # 文件信息
    video_path = Column(
        String(500), 
        nullable=True, 
        comment="原始视频文件路径"
    )
    subtitle_path = Column(
        String(500), 
        nullable=True, 
        comment="字幕文件路径"
    )
    
    # 视频元数据
    video_duration = Column(
        Float, 
        nullable=True, 
        comment="视频时长（秒）"
    )
    video_size = Column(
        Float, 
        nullable=True, 
        comment="视频文件大小（字节）"
    )
    video_metadata = Column(
        JSON, 
        nullable=True, 
        comment="视频元数据"
    )
    
    # 处理配置
    config = Column(
        JSON, 
        nullable=True, 
        comment="处理配置参数"
    )
    
    # 输出配置
    output_config = Column(
        JSON, 
        nullable=True, 
        comment="输出配置"
    )
    
    # 处理状态
    current_step = Column(
        Integer, 
        default=0,
        nullable=False,
        comment="当前处理步骤"
    )
    progress = Column(
        Float, 
        default=0.0,
        nullable=False,
        comment="整体进度（0-100）"
    )
    progress_message = Column(
        String(500), 
        nullable=True, 
        comment="进度消息"
    )
    
    # 错误信息
    error_message = Column(
        Text, 
        nullable=True, 
        comment="错误信息"
    )
    
    # 统计信息
    clip_count = Column(
        Integer, 
        default=0,
        nullable=False,
        comment="切片数量"
    )
    processed_clip_count = Column(
        Integer, 
        default=0,
        nullable=False,
        comment="已处理切片数量"
    )
    
    # 扩展信息
    extended_info = Column(
        JSON, 
        nullable=True, 
        comment="扩展信息"
    )
    
    # 项目元数据
    project_metadata = Column(
        JSON, 
        nullable=True, 
        comment="项目元数据"
    )
    
    # 处理配置
    processing_config = Column(
        JSON, 
        nullable=True, 
        comment="处理配置"
    )
    
    # 处理开始时间
    started_at = Column(
        DateTime, 
        nullable=True, 
        comment="处理开始时间"
    )

    # 完成时间
    completed_at = Column(
        DateTime, 
        nullable=True, 
        comment="完成时间"
    )
    
    # 缩略图
    thumbnail = Column(
        Text, 
        nullable=True, 
        comment="视频缩略图（base64）"
    )
    
    # 统计信息
    total_clips = Column(
        Integer, 
        default=0,
        nullable=False,
        comment="总切片数"
    )
    total_collections = Column(
        Integer, 
        default=0,
        nullable=False,
        comment="总合集数"
    )
    
    # 设置
    settings = Column(
        JSON, 
        nullable=True, 
        comment="设置"
    )
    
    # 关联关系
    clips = relationship(
        "Clip", 
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', status={self.status})>"
    
    @property
    def is_processing(self):
        """是否正在处理"""
        return self.status == ProjectStatus.PROCESSING
    
    @property
    def is_completed(self):
        """是否已完成"""
        return self.status == ProjectStatus.COMPLETED
    
    @property
    def has_error(self):
        """是否有错误"""
        return self.status == ProjectStatus.FAILED
