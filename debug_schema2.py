import sys
sys.path.insert(0, '.')

from backend.core.database import get_db
from backend.models.project import Project
from backend.schemas.project import ProjectStatus, ProjectType

db = next(get_db())

try:
    # 查询再转schema
    p1 = db.query(Project).first()
    if p1:
        print(f'First project: {p1.id}, status=[{p1.status}], type=[{p1.project_type}]')
        
        # 手工转换验证
        new_type = ProjectType(p1.project_type)
        new_status = ProjectStatus(p1.status)
        print(f'转换成功: type={new_type}, status={new_status}')
        
        # 用schema
        from backend.schemas.project import ProjectResponse
        response = ProjectResponse(
            id=str(p1.id),
            name=str(p1.name),
            description=str(p1.description) if p1.description else None,
            project_type=new_type,
            status=new_status,
            source_url=None,
            source_file=None,
            settings={},
            created_at=p1.created_at,
            updated_at=p1.updated_at,
            completed_at=None,
            total_clips=0,
            total_collections=0,
            total_tasks=0
        )
        print('Schema validation通过，response可序列化')
        
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    
db.close()