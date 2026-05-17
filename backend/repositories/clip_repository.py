"""
切片仓库模块
"""

from sqlalchemy.orm import Session
from backend.models.clip import Clip


class ClipRepository:
    """切片数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, clip_id: str) -> Clip:
        """根据ID获取切片"""
        return self.db.query(Clip).filter(Clip.id == clip_id).first()

    def get_all(self) -> list:
        """获取所有切片"""
        return self.db.query(Clip).all()

    def create(self, **kwargs) -> Clip:
        """创建新切片"""
        clip = Clip(**kwargs)
        self.db.add(clip)
        self.db.commit()
        self.db.refresh(clip)
        return clip

    def update(self, clip: Clip, **kwargs) -> Clip:
        """更新切片"""
        for key, value in kwargs.items():
            setattr(clip, key, value)
        self.db.commit()
        self.db.refresh(clip)
        return clip

    def delete(self, clip_id: str) -> bool:
        """删除切片"""
        clip = self.get_by_id(clip_id)
        if clip:
            self.db.delete(clip)
            self.db.commit()
            return True
        return False

    def find_by(self, **kwargs) -> list:
        """根据条件查找切片"""
        query = self.db.query(Clip)
        for key, value in kwargs.items():
            query = query.filter(getattr(Clip, key) == value)
        return query.all()

    def get_by_project(self, project_id: str) -> list:
        """根据项目ID获取切片"""
        return self.db.query(Clip).filter(Clip.project_id == project_id).all()
