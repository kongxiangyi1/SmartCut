"""
数据库连接管理
"""

import os
from sqlalchemy import create_engine, text
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


def _upgrade_schema(engine):
    """升级旧数据库 schema（新增字段等）"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        with engine.connect() as conn:
            # 尝试添加 started_at 列（兼容已存在的场景）
            conn.execute(
                text("ALTER TABLE projects ADD COLUMN started_at DATETIME")
            )
            conn.commit()
            logger.info("[Schema] 已添加 started_at 列")
    except Exception as e:
        # 列已存在或表不存在，忽略
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            logger.debug("[Schema] started_at 列已存在，跳过")
        else:
            logger.warning(f"[Schema] ALTER TABLE 警告: {e}")
