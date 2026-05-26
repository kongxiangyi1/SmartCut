"""检查API返回的项目数据格式"""
from backend.core.database import SessionLocal
from backend.services.project_service import ProjectService
from backend.schemas.project import PaginationParams, ProjectResponse

db = SessionLocal()
try:
    service = ProjectService(db)
    result = service.get_projects_paginated(PaginationParams(page=1, page_size=50))
    
    print("=" * 80)
    print("项目列表API返回数据:")
    print("=" * 80)
    print()
    print(f"Total: {result.total}")
    print()
    
    for i, project in enumerate(result.items, 1):
        print(f"项目 {i}:")
        print(f"  ID: {project.id}")
        print(f"  名称: {project.name}")
        print(f"  状态: {project.status}")
        print(f"  创建时间: {project.created_at}")
        print(f"  创建时间类型: {type(project.created_at)}")
        if hasattr(project.created_at, 'isoformat'):
            print(f"  ISO格式: {project.created_at.isoformat()}")
        print()

finally:
    db.close()
