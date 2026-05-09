#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from backend.core.database import get_db
from backend.models.project import Project
from backend.schemas.project import ProjectStatus, ProjectType

try:
    db = next(get_db())
    
    print("尝试SQLAlchemy查询...")
    
    # 基本直接ORM查询
    projects = db.query(Project).all()
    
    for p in projects:
        print(f'项目 {p.id}: status={p.status}, type={p.project_type}')
        
        # 检查字符串转换
        print(f'  status 值: [{p.status}], 类型: {type(p.status)}')
        print(f'  project_type 值: [{p.project_type}], 类型: {type(p.project_type)}')
        
        # 测试与schema enum兼容性
        try:
            converted_status = ProjectStatus(p.status.value)
            print(f'  status schema转换成功: {converted_status}')
        except Exception as s_e:
            print(f'  status ERROR: {s_e}')
    
    db.close()
    print("查询完毕")

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
    
print("脚本完毕")