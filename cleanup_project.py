import sys
sys.path.insert(0, 'E:\\ClipProject\\autoclip-main1\\autoclip-main')

from backend.core.database import SessionLocal
from backend.models.project import Project
from backend.models.clip import Clip
from backend.models.collection import Collection
import shutil
from pathlib import Path

project_id = "6cffed8c-53fd-4e2a-9ea4-843d5111f79f"

# 清理数据库
db = SessionLocal()
try:
    print("清理数据库数据...")
    db.query(Clip).filter(Clip.project_id == project_id).delete()
    db.query(Collection).filter(Collection.project_id == project_id).delete()
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        project.status = "pending"
    db.commit()
    print("✅ 数据库清理成功！")
except Exception as e:
    print(f"❌ 数据库清理失败: {e}")
    db.rollback()
finally:
    db.close()

# 清理项目文件夹
project_dir = Path("E:\\ClipProject\\autoclip-main1\\autoclip-main\\data\\projects") / project_id
if project_dir.exists():
    print(f"删除项目文件夹: {project_dir}")
    shutil.rmtree(project_dir)

print("✅ 清理完成！")
