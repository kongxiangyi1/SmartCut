"""修复被破坏的 clips.py 文件"""
import re

# 读取文件
with open('backend/api/v1/clips.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复被破坏的导入部分
# 查找并替换错误的导入块
broken_imports = """from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
    from backend.schemas.clip import ClipCreate, ClipUpdate, ClipResponse, ClipListResponse, ClipStatus, ClipFilter
    from backend.schemas.base import PaginationParams
    from backend.models.clip import Clip
except ImportError:
    from backend.core.database import get_db
    from backend.services.clip_service import ClipService
    from backend.schemas.clip import ClipCreate, ClipUpdate, ClipResponse, ClipListResponse, ClipStatus, ClipFilter
    from backend.schemas.base import PaginationParams
    from backend.models.clip import Clip
import logging"""

fixed_imports = """from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.services.clip_service import ClipService
from backend.schemas.clip import ClipCreate, ClipUpdate, ClipResponse, ClipListResponse, ClipStatus, ClipFilter
from backend.schemas.base import PaginationParams
from backend.models.clip import Clip
import logging"""

content = content.replace(broken_imports, fixed_imports)

# 写回文件
with open('backend/api/v1/clips.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("clips.py 修复完成！")