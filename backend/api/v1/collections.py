"""

合集API路由

"""



import logging

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from backend.core.database import get_db

from backend.services.collection_service import CollectionService

from backend.schemas.collection import CollectionCreate, CollectionUpdate, CollectionResponse, CollectionListResponse

from backend.schemas.base import PaginationParams



logger = logging.getLogger(__name__)



router = APIRouter()





def get_collection_service(db: Session = Depends(get_db)) -> CollectionService:

    """Dependency to get collection service."""

    return CollectionService(db)





@router.post("/", response_model=CollectionResponse)

async def create_collection(

    collection_data: CollectionCreate,

    collection_service: CollectionService = Depends(get_collection_service)

):

    """Create a new collection."""

    try:

        collection = collection_service.create_collection(collection_data)

        # Convert to response schema

        status_obj = getattr(collection, 'status', None)

        status_value = status_obj.value if hasattr(status_obj, 'value') else 'created'

        

        return CollectionResponse(

            id=str(getattr(collection, 'id', '')),

            project_id=str(getattr(collection, 'project_id', '')),

            name=str(getattr(collection, 'name', '')),

            description=str(getattr(collection, 'description', '')) if getattr(collection, 'description', None) else None,

            theme=getattr(collection, 'theme', None),

            status=status_value,

            tags=getattr(collection, 'tags', []) or [],

            metadata=getattr(collection, 'collection_metadata', {}) or {},

            video_path=getattr(collection, 'export_path', None),

            thumbnail_path=getattr(collection, 'thumbnail_path', None),

            created_at=getattr(collection, 'created_at', None) if isinstance(getattr(collection, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,

            updated_at=getattr(collection, 'updated_at', None) if isinstance(getattr(collection, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,

            total_clips=getattr(collection, 'clips_count', 0) or 0

        )

    except Exception as e:

        raise HTTPException(status_code=400, detail=str(e))





@router.get("/", response_model=CollectionListResponse)

async def get_collections(

    page: int = Query(1, ge=1, description="Page number"),

    size: int = Query(20, ge=1, le=100, description="Page size"),

    project_id: Optional[str] = Query(None, description="Filter by project ID"),

    collection_service: CollectionService = Depends(get_collection_service)

):

    """Get paginated collections."""

    try:

        from backend.schemas.base import PaginationParams

        from backend.schemas.collection import CollectionFilter

        

        pagination = PaginationParams(page=page, page_size=size)

        

        filters = None

        if project_id:

            filters = CollectionFilter(project_id=project_id)

        

        return collection_service.get_collections_paginated(pagination, filters)

    except Exception as e:

        raise HTTPException(status_code=400, detail=str(e))





@router.get("/{collection_id}", response_model=CollectionResponse)

async def get_collection(

    collection_id: str,

    include_content: bool = Query(False, description="是否包含完整内容"),

    collection_service: CollectionService = Depends(get_collection_service)

):

    """Get a collection by ID (优化存储模式)."""

    try:

        collection = collection_service.get(collection_id)

        if not collection:

            raise HTTPException(status_code=404, detail="Collection not found")

        

        # Convert to response schema

        status_obj = getattr(collection, 'status', None)

        status_value = status_obj.value if hasattr(status_obj, 'value') else 'created'

        

        # 获取clip_ids

        clip_ids = []

        metadata = getattr(collection, 'collection_metadata', {}) or {}

        if metadata and 'clip_ids' in metadata:

            clip_ids = metadata['clip_ids']

        

        # 如果需要完整内容，从文件系统获取
        full_content = None

        if include_content:

            from backend.repositories.collection_repository import CollectionRepository

            collection_repo = CollectionRepository(collection_service.db)

            full_content = collection_repo.get_collection_content(collection_id)

        

        # 构建响应数据

        response_data = {

            "id": str(getattr(collection, 'id', '')),

            "project_id": str(getattr(collection, 'project_id', '')),

            "name": str(getattr(collection, 'name', '')),

            "description": str(getattr(collection, 'description', '')) if getattr(collection, 'description', None) else None,

            "theme": getattr(collection, 'theme', None),

            "status": status_value,

            "tags": getattr(collection, 'tags', []) or [],

            "metadata": getattr(collection, 'collection_metadata', {}) or {},

            "video_path": getattr(collection, 'export_path', None),

            "thumbnail_path": getattr(collection, 'thumbnail_path', None),

            "created_at": getattr(collection, 'created_at', None) if isinstance(getattr(collection, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,

            "updated_at": getattr(collection, 'updated_at', None) if isinstance(getattr(collection, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,

            "total_clips": getattr(collection, 'clips_count', 0) or 0,

            "clip_ids": clip_ids

        }

        

        # 如果需要完整内容，添加到响应中

        if include_content and full_content:

            response_data["full_content"] = full_content

        

        return CollectionResponse(**response_data)

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=400, detail=str(e))





@router.put("/{collection_id}", response_model=CollectionResponse)

async def update_collection(

    collection_id: str,

    collection_data: CollectionUpdate,

    collection_service: CollectionService = Depends(get_collection_service)

):

    """Update a collection."""

    try:

        collection = collection_service.update_collection(collection_id, collection_data)

        if not collection:

            raise HTTPException(status_code=404, detail="Collection not found")

        

        # Convert to response schema

        status_obj = getattr(collection, 'status', None)

        status_value = status_obj.value if hasattr(status_obj, 'value') else 'created'

        

        # 获取clip_ids

        clip_ids = []

        metadata = getattr(collection, 'collection_metadata', {}) or {}

        if metadata and 'clip_ids' in metadata:

            clip_ids = metadata['clip_ids']

        

        return CollectionResponse(

            id=str(getattr(collection, 'id', '')),

            project_id=str(getattr(collection, 'project_id', '')),

            name=str(getattr(collection, 'name', '')),

            description=str(getattr(collection, 'description', '')) if getattr(collection, 'description', None) else None,

            theme=getattr(collection, 'theme', None),

            status=status_value,

            tags=getattr(collection, 'tags', []) or [],

            metadata=getattr(collection, 'collection_metadata', {}) or {},

            video_path=getattr(collection, 'export_path', None),

            thumbnail_path=getattr(collection, 'thumbnail_path', None),

            created_at=getattr(collection, 'created_at', None) if isinstance(getattr(collection, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,

            updated_at=getattr(collection, 'updated_at', None) if isinstance(getattr(collection, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,

            total_clips=getattr(collection, 'clips_count', 0) or 0,

            clip_ids=clip_ids

        )

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=400, detail=str(e))





@router.delete("/{collection_id}")

async def delete_collection(

    collection_id: str,

    collection_service: CollectionService = Depends(get_collection_service)

):

    """Delete a collection."""

    try:

        success = collection_service.delete_collection_with_filesystem_update(collection_id)

        if not success:

            raise HTTPException(status_code=404, detail="Collection not found")

        return {"message": "Collection deleted successfully"}

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=400, detail=str(e))





@router.patch("/{collection_id}/reorder", response_model=CollectionResponse)

async def reorder_collection_clips(

    collection_id: str,

    clip_ids: List[str],

    collection_service: CollectionService = Depends(get_collection_service)

):

    """Reorder clips in a collection."""

    try:

        # 获取合集

        collection = collection_service.get(collection_id)

        if not collection:

            raise HTTPException(status_code=404, detail="Collection not found")

        

        # 更新collection_metadata中的clip_ids

        metadata = getattr(collection, 'collection_metadata', {}) or {}

        metadata['clip_ids'] = clip_ids

        

        # 直接更新数据库中的collection_metadata字段

        from sqlalchemy import update

        from backend.models.collection import Collection

        

        stmt = update(Collection).where(Collection.id == collection_id).values(

            collection_metadata=metadata

        )

        collection_service.db.execute(stmt)

        collection_service.db.commit()

        

        # 重新获取更新后的合集

        updated_collection = collection_service.get(collection_id)

        if not updated_collection:

            raise HTTPException(status_code=404, detail="Collection not found")

        

        # Convert to response schema

        status_obj = getattr(updated_collection, 'status', None)

        status_value = status_obj.value if hasattr(status_obj, 'value') else 'created'

        

        return CollectionResponse(

            id=str(getattr(updated_collection, 'id', '')),

            project_id=str(getattr(updated_collection, 'project_id', '')),

            name=str(getattr(updated_collection, 'name', '')),

            description=str(getattr(updated_collection, 'description', '')) if getattr(updated_collection, 'description', None) else None,

            theme=getattr(updated_collection, 'theme', None),

            status=status_value,

            tags=getattr(updated_collection, 'tags', []) or [],

            metadata=getattr(updated_collection, 'collection_metadata', {}) or {},

            created_at=getattr(updated_collection, 'created_at', None) if isinstance(getattr(updated_collection, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,

            updated_at=getattr(updated_collection, 'updated_at', None) if isinstance(getattr(updated_collection, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,

            total_clips=getattr(updated_collection, 'clips_count', 0) or 0,

            clip_ids=clip_ids

        )

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(status_code=400, detail=str(e))





@router.post("/{collection_id}/generate-title", response_model=dict)

async def generate_collection_title(

    collection_id: str,

    collection_service: CollectionService = Depends(get_collection_service)

):

    """Generate a new title for a collection using LLM."""

    try:

        collection = collection_service.get(collection_id)

        if not collection:

            raise HTTPException(status_code=404, detail="合集不存在")



        # 获取合集元数据
        collection_metadata = getattr(collection, 'collection_metadata', {}) or {}

        

        if not collection_metadata:

            raise HTTPException(status_code=404, detail="合集元数据不存在")



        # 获取合集中的切片信息

        clip_ids = collection_metadata.get('clip_ids', [])

        if not clip_ids:

            raise HTTPException(status_code=404, detail="合集中没有切片")



        # 获取切片详细信息

        from backend.repositories.clip_repository import ClipRepository

        clip_repo = ClipRepository(collection_service.db)

        

        clips_data = []

        for clip_id in clip_ids:

            clip = clip_repo.get_by_id(clip_id)

            if clip:

                clip_metadata = getattr(clip, 'clip_metadata', {}) or {}

                clips_data.append({

                    "id": clip_id,

                    "title": clip_metadata.get('outline', '') or getattr(clip, 'title', ''),

                    "content": clip_metadata.get('content', []),

                    "recommend_reason": clip_metadata.get('recommend_reason', '')

                })



        if not clips_data:

            raise HTTPException(status_code=404, detail="无法获取切片内容")



        # 构建LLM输入

        llm_input = {

            "collection_id": collection_id,

            "collection_title": collection.name,

            "collection_description": collection.description or "",

            "clips": clips_data,

            "total_duration_minutes": collection_metadata.get('total_duration_minutes', 0),

            "target_audience": collection_metadata.get('target_audience', ''),

            "key_themes": collection_metadata.get('key_themes', [])

        }



        # 调用LLM生成标题

        from backend.utils.llm_client import LLMClient

        from backend.core.shared_config import PROMPT_FILES



        llm_client = LLMClient()



        with open(PROMPT_FILES['collection_title'], 'r', encoding='utf-8') as f:

            title_prompt = f.read()



        raw_response = llm_client.call_with_retry(title_prompt, llm_input)



        if not raw_response:

            raise HTTPException(status_code=500, detail="LLM调用失败")



        title_result = llm_client.parse_json_response(raw_response)



        if not isinstance(title_result, dict) or 'generated_title' not in title_result:

            raise HTTPException(status_code=500, detail="LLM返回格式错误")



        generated_title = title_result['generated_title']



        return {

            "collection_id": collection_id,

            "generated_title": generated_title,

            "success": True

        }



    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"生成合集标题失败: {e}")

        raise HTTPException(status_code=500, detail=f"生成合集标题失败: {str(e)}")





@router.put("/{collection_id}/title", response_model=dict)

async def update_collection_title(

    collection_id: str,

    title_data: dict,

    collection_service: CollectionService = Depends(get_collection_service)

):

    """Update collection title."""

    try:

        new_title = title_data.get('title')

        if not new_title:

            raise HTTPException(status_code=400, detail="标题不能为空")



        collection = collection_service.get(collection_id)

        if not collection:

            raise HTTPException(status_code=404, detail="合集不存在")



        # 更新合集标题

        collection.name = new_title

        collection_service.db.commit()



        return {

            "collection_id": collection_id,

            "title": new_title,

            "success": True

        }



    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"更新合集标题失败: {e}")

        raise HTTPException(status_code=500, detail=f"更新合集标题失败: {str(e)}")