"""
数据库连接管理
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 获取数据库URL，默认为SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")

# 创建引擎
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型类
Base = declarative_base()


def get_db():
    """获取数据库会话（依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Ensure model modules are imported so SQLAlchemy's registry is populated.
# This avoids mapper initialization errors when individual modules import
# model classes before all related models have been defined.
try:
    import backend.models  # noqa: F401
except Exception:
    # Import failures here should not prevent the application from starting,
    # but may indicate a deeper issue that should be logged during runtime.
    pass
