"""
基础服务类
"""

from sqlalchemy.orm import Session
from typing import Any, Generic, TypeVar, Optional, List, Dict
from datetime import datetime

# 定义类型变量
ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")
ResponseSchemaType = TypeVar("ResponseSchemaType")


class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType, ResponseSchemaType]):
    """基础服务类，提供通用的数据库操作方法"""

    def __init__(self, repository):
        self.repository = repository
        self.db = repository.db

    def commit(self):
        """提交事务"""
        self.db.commit()

    def rollback(self):
        """回滚事务"""
        self.db.rollback()

    def add(self, obj: Any):
        """添加对象到会话"""
        self.db.add(obj)

    def delete(self, obj: Any):
        """从会话中删除对象"""
        self.db.delete(obj)

    def refresh(self, obj: Any):
        """刷新对象"""
        self.db.refresh(obj)
    
    def get(self, entity_id: str) -> Optional[ModelType]:
        """根据ID获取实体"""
        return self.repository.get_by_id(entity_id)
    
    def get_all(self) -> List[ModelType]:
        """获取所有实体"""
        return self.repository.get_all()
    
    def create(self, **kwargs) -> ModelType:
        """创建实体"""
        # 直接创建模型对象
        model_class_name = self.repository.__class__.__name__.replace('Repository', '')
        # 尝试导入对应的模型模块
        try:
            model_module = __import__(f'backend.models.{model_class_name.lower()}', fromlist=[model_class_name])
            model_cls = getattr(model_module, model_class_name)
        except (ImportError, AttributeError):
            # 尝试从backend.models直接导入
            from backend.models import project, task, clip, collection
            models_map = {
                'Project': project.Project,
                'Task': task.Task,
                'Clip': clip.Clip,
                'Collection': collection.Collection
            }
            model_cls = models_map.get(model_class_name)
        
        if model_cls:
            entity = model_cls(**kwargs)
            self.db.add(entity)
            self.db.commit()
            self.db.refresh(entity)
            return entity
        else:
            raise NotImplementedError(f"Model class {model_class_name} not found")
    
    def update(self, entity_id: str, **kwargs) -> Optional[ModelType]:
        """更新实体"""
        entity = self.repository.get_by_id(entity_id)
        if entity:
            for key, value in kwargs.items():
                setattr(entity, key, value)
            self.db.commit()
            self.db.refresh(entity)
            return entity
        return None
    
    def delete_by_id(self, entity_id: str) -> bool:
        """根据ID删除实体"""
        return self.repository.delete(entity_id)
    
    def get_paginated(self, pagination, filters: Dict = None):
        """获取分页数据"""
        # 基础实现，子类可以覆盖
        items = self.get_all()
        
        # 应用过滤器
        if filters:
            for key, value in filters.items():
                items = [item for item in items if getattr(item, key, None) == value]
        
        # 应用分页
        total = len(items)
        offset = (pagination.page - 1) * pagination.page_size
        paginated_items = items[offset:offset + pagination.page_size]
        
        from ..schemas.base import PaginationResponse
        pagination_response = PaginationResponse(
            page=pagination.page,
            page_size=pagination.page_size,
            total=total,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )
        
        return paginated_items, pagination_response
