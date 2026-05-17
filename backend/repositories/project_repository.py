"""
项目仓库模块
"""

from sqlalchemy.orm import Session
from backend.models.project import Project
from backend.schemas.project import ProjectCreate, ProjectUpdate


class ProjectRepository:
    """项目数据访问层"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, project_id: str) -> Project:
        """根据ID获取项目"""
        return self.db.query(Project).filter(Project.id == project_id).first()

    def get_all(self) -> list:
        """获取所有项目"""
        return self.db.query(Project).all()

    def create(self, project_create: ProjectCreate) -> Project:
        """创建新项目"""
        project = Project(**project_create.dict())
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update(self, project: Project, project_update: ProjectUpdate) -> Project:
        """更新项目"""
        for key, value in project_update.dict(exclude_unset=True).items():
            setattr(project, key, value)
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete(self, project_id: str) -> bool:
        """删除项目"""
        project = self.get_by_id(project_id)
        if project:
            self.db.delete(project)
            self.db.commit()
            return True
        return False

    def get_by_status(self, status: str) -> list:
        """根据状态获取项目"""
        return self.db.query(Project).filter(Project.status == status).all()
