"""
Collection-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from .base import BaseSchema, PaginationResponse


class CollectionCreate(BaseSchema):
    """Schema for creating a new collection."""
    project_id: str = Field(..., description="Project ID")
    name: str = Field(..., min_length=1, max_length=200, description="Collection name")
    description: Optional[str] = Field(default=None, description="Collection description")
    collection_type: Optional[str] = Field(default="ai_recommended", description="Collection type")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class CollectionUpdate(BaseSchema):
    """Schema for updating a collection."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200, description="Collection name")
    description: Optional[str] = Field(default=None, description="Collection description")
    collection_type: Optional[str] = Field(default=None, description="Collection type")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class CollectionResponse(BaseSchema):
    """Schema for collection response."""
    id: str = Field(description="Collection ID")
    project_id: str = Field(description="Project ID")
    name: str = Field(description="Collection name")
    description: Optional[str] = Field(default=None, description="Collection description")
    collection_type: str = Field(description="Collection type")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    created_at: Optional[datetime] = Field(default=None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Updated timestamp")


class CollectionListResponse(BaseSchema):
    """Schema for paginated collection list response."""
    items: List[CollectionResponse] = Field(default_factory=list, description="List of collections")
    pagination: PaginationResponse = Field(description="Pagination information")
