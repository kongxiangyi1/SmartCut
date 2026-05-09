import sys
sys.path.insert(0, '.')
from backend.core.database import get_db
from backend.services.project_service import ProjectService
from backend.schemas.base import PaginationParams

print('开始直接更新项目状态...')
db_session = next(get_db())
project_service = ProjectService(db_session)

try:
    # 使用分页获取方法读取所有项目
    pagination = PaginationParams(page=1, per_page=100)
    result = project_service.get_projects_paginated(pagination=pagination)
    
    projects = result.items if hasattr(result, 'items') else result['items']
        
    print(f'找到 {len(projects)} 个项目')
    for p in projects:
        print(f'项目: {p.id} 当前状态: {p.status}')
    
    # 直接设为processing
    for p in projects:
        if str(p.status) in ['pending']:
            print(f'更新项目 {p.id} 状态为 processing...')
            project_service.update_project_status(p.id, 'processing')
    
    print('所有项目状态更新完毕！')
except Exception as e:
    print(f'更新失败: {e}')
    import traceback
    traceback.print_exc()
finally:
    db_session.close()