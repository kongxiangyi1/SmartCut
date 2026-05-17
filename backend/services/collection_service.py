"""
合集服务
提供合集相关的业务逻辑操作
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from ..services.base import BaseService
from ..repositories.collection_repository import CollectionRepository
from ..models.collection import Collection
from ..schemas.collection import CollectionCreate, CollectionUpdate, CollectionResponse, CollectionListResponse
from ..schemas.base import PaginationParams, PaginationResponse


class CollectionService(BaseService[Collection, CollectionCreate, CollectionUpdate, CollectionResponse]):
    """Collection service with business logic."""
    
    def __init__(self, db: Session):
        repository = CollectionRepository(db)
        super().__init__(repository)
        self.db = db
    
    def create_collection(self, collection_data: CollectionCreate) -> Collection:
        """Create a new collection with business logic."""
        data = collection_data.model_dump()
        orm_data = {
            "project_id": data["project_id"],
            "collection_title": data.get("name", "") or data.get("collection_title", ""),
            "collection_summary": data.get("description") or data.get("collection_summary", ""),
            "collection_type": data.get("collection_type", "ai_recommended"),
            "collection_metadata": data.get("metadata", {}),
        }
        return self.create(**orm_data)
    
    def update_collection(self, collection_id: str, collection_data: CollectionUpdate) -> Optional[Collection]:
        """Update a collection with business logic."""
        update_data = {k: v for k, v in collection_data.model_dump().items() if v is not None}
        if not update_data:
            return self.get(collection_id)
        
        return self.update(collection_id, **update_data)
    
    def get_collections_by_project(self, project_id: str, skip: int = 0, limit: int = 100) -> List[Collection]:
        """Get collections by project ID."""
        return self.repository.find_by(project_id=project_id)
    
    def get_collections_paginated(
        self, 
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> CollectionListResponse:
        """Get paginated collections with filtering."""
        filter_dict = filters or {}
        
        items, pagination_response = self.get_paginated(pagination, filter_dict)
        
        # Convert to response schemas
        collection_responses = []
        for collection in items:
            collection_responses.append(CollectionResponse(
                id=str(collection.id),
                project_id=str(collection.project_id),
                name=str(collection.collection_title),
                description=str(collection.collection_summary) if collection.collection_summary else None,
                collection_type=collection.collection_type,
                metadata=collection.collection_metadata or {},
                created_at=getattr(collection, 'created_at', None),
                updated_at=getattr(collection, 'updated_at', None)
            ))
        
        return CollectionListResponse(
            items=collection_responses,
            pagination=pagination_response
        )
