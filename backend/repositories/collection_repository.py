"""
合集仓库模块
"""

from sqlalchemy.orm import Session
from backend.models.collection import Collection


class CollectionRepository:
    """合集数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, collection_id: str) -> Collection:
        """根据ID获取合集"""
        return self.db.query(Collection).filter(Collection.id == collection_id).first()

    def get_all(self) -> list:
        """获取所有合集"""
        return self.db.query(Collection).all()

    def create(self, **kwargs) -> Collection:
        """创建新合集"""
        collection = Collection(**kwargs)
        self.db.add(collection)
        self.db.commit()
        self.db.refresh(collection)
        return collection

    def update(self, collection: Collection, **kwargs) -> Collection:
        """更新合集"""
        for key, value in kwargs.items():
            setattr(collection, key, value)
        self.db.commit()
        self.db.refresh(collection)
        return collection

    def delete(self, collection_id: str) -> bool:
        """删除合集"""
        collection = self.get_by_id(collection_id)
        if collection:
            self.db.delete(collection)
            self.db.commit()
            return True
        return False

    def find_by(self, **kwargs) -> list:
        """根据条件查找合集"""
        query = self.db.query(Collection)
        for key, value in kwargs.items():
            query = query.filter(getattr(Collection, key) == value)
        return query.all()

    def get_by_project(self, project_id: str) -> list:
        """根据项目ID获取合集"""
        return self.db.query(Collection).filter(Collection.project_id == project_id).all()
