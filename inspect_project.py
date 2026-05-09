import sqlite3
import json
from pathlib import Path

# 获取数据库路径
workspace_path = Path.cwd()
db_path = workspace_path / "data" / "autoclip.db"

print(f"检查数据库: {db_path}")
print(f"数据库存在: {db_path.exists()}")

if db_path.exists():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # 查询所有项目
    projects = conn.execute("SELECT * FROM projects LIMIT 10").fetchall()
    print(f"\n项目总数: {len(projects)}")
    
    for i, project in enumerate(projects[:2]):  # 只检查前2个项目
        print(f"\n--- 项目 {i+1} ---")
        print(f"ID: {project['id']}")
        print(f"名称: {project['name'][:100]}..." if len(project['name']) > 100 else f"名称: {project['name']}")
        
        # 检查description长度
        desc = project['description']
        print(f"描述长度: {len(desc) if desc else 0} 字符")
        if desc and len(desc) > 200:
            print(f"描述预览: {desc[:200]}...")
        
        # 检查project_metadata长度
        metadata = project['project_metadata']
        if metadata:
            print(f"metadata长度: {len(metadata)} 字符")
            try:
                meta_data = json.loads(metadata)
                print(f"metadata类型: {type(meta_data)}")
                if isinstance(meta_data, dict):
                    print(f"metadata键: {list(meta_data.keys())[:10]}")
            except:
                print("metadata不是有效的JSON")
        
        # 检查processing_config长度
        config = project['processing_config']
        if config:
            print(f"config长度: {len(config)} 字符")
    
    conn.close()