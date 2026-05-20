"""
简化的流水线适配器 - 支持切换不同流水线方案
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import json
import asyncio

from backend.services.simple_progress import emit_progress, clear_progress

logger = logging.getLogger(__name__)


class SimplePipelineAdapter:
    """简化的流水线适配器，支持切换不同处理方案"""
    
    def __init__(self, project_id: str, task_id: str):
        self.project_id = project_id
        self.task_id = task_id
    
    async def process_project_sync(self, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        """
        同步处理项目 - 使用简化的进度系统
        
        Args:
            input_video_path: 输入视频路径
            input_srt_path: 输入SRT路径
            
        Returns:
            处理结果
        """
        logger.info(f"开始处理项目: {self.project_id}")
        
        try:
            # 清除之前的进度数据
            clear_progress(self.project_id)
            
            # 创建必要的目录结构
            from backend.core.path_utils import get_project_directory, ensure_project_dirs
            project_dir = ensure_project_dirs(self.project_id)
            metadata_dir = project_dir / "metadata"
            clips_output_dir = project_dir / "output" / "clips"
            collections_output_dir = project_dir / "output" / "collections"
            
            metadata_dir.mkdir(parents=True, exist_ok=True)
            clips_output_dir.mkdir(parents=True, exist_ok=True)
            collections_output_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取当前选择的流水线模式
            from backend.pipeline.pipeline_selector import get_pipeline_selector
            selector = get_pipeline_selector()
            pipeline_mode = selector.select_pipeline(self.project_id)
            
            logger.info(f"使用流水线模式: {pipeline_mode}")
            
            # 根据模式选择处理方式
            if pipeline_mode == "funclip":
                # 使用FunClip风格单步LLM处理
                result = await self._process_with_funclip(
                    input_video_path, 
                    input_srt_path, 
                    project_dir, 
                    metadata_dir, 
                    clips_output_dir, 
                    collections_output_dir
                )
            else:
                # 使用原6步流水线（默认）
                result = await self._process_with_legacy(
                    input_video_path, 
                    input_srt_path, 
                    project_dir, 
                    metadata_dir, 
                    clips_output_dir, 
                    collections_output_dir
                )
            
            return result
            
        except Exception as e:
            import traceback
            error_msg = f"流水线处理失败: {str(e)}"
            logger.error(error_msg)
            logger.error(f"堆栈: {traceback.format_exc()}")
            
            # 更新项目状态为失败
            try:
                from backend.core.database import SessionLocal
                from backend.models.project import Project
                
                db = SessionLocal()
                try:
                    from backend.services.project_service import ProjectService
                    project_service = ProjectService(db)
                    project = project_service.get(self.project_id)
                    if project:
                        project_service.update(
                            self.project_id,
                            status="failed",
                            error_message=str(e)
                        )
                        db.commit()
                        logger.info(f"项目 {self.project_id} 状态已更新为 failed")
                finally:
                    db.close()
            except Exception as update_e:
                logger.error(f"更新项目失败状态失败: {update_e}")
            
            # 发送失败状态
            emit_progress(self.project_id, "DONE", f"处理失败: {error_msg}")
            
            raise Exception(error_msg)
    
    async def _process_with_funclip(self, input_video_path: str, input_srt_path: str,
                                   project_dir: Path, metadata_dir: Path,
                                   clips_output_dir: Path, collections_output_dir: Path) -> Dict[str, Any]:
        """使用FunClip风格单步LLM处理"""
        logger.info("使用FunClip风格单步LLM流水线")
        
        try:
            from backend.pipeline.funclip_style import run_funclip_pipeline
            
            # 阶段1: 素材准备
            emit_progress(self.project_id, "INGEST", "素材准备完成")
            
            # 阶段2: 字幕处理
            emit_progress(self.project_id, "SUBTITLE", "开始字幕处理")
            
            srt_path = Path(input_srt_path) if input_srt_path else None
            
            # 如果没有字幕文件，尝试自动生成
            if not srt_path or not srt_path.exists():
                logger.info("未找到字幕文件，尝试自动生成...")
                emit_progress(self.project_id, "SUBTITLE", "正在生成字幕文件...")
                
                from backend.utils.speech_recognizer import generate_subtitle_for_video
                srt_path = project_dir / "raw" / "subtitle.srt"
                srt_path.parent.mkdir(parents=True, exist_ok=True)
                
                generated_srt = generate_subtitle_for_video(
                    video_path=Path(input_video_path),
                    output_path=srt_path,
                    method="auto",
                    language="auto"
                )
                
                if generated_srt and generated_srt.exists():
                    srt_path = generated_srt
                else:
                    raise Exception("字幕生成失败")
            
            emit_progress(self.project_id, "SUBTITLE", "字幕处理完成")
            
            # 阶段3: 单步LLM分析（这是FunClip的核心）
            emit_progress(self.project_id, "ANALYZE", "正在进行智能内容分析...", subpercent=50)
            
            clips, collections = run_funclip_pipeline(
                srt_path=srt_path,
                video_path=Path(input_video_path),
                metadata_dir=metadata_dir,
                clips_output_dir=clips_output_dir,
                collections_output_dir=collections_output_dir
            )
            
            emit_progress(self.project_id, "ANALYZE", "内容分析完成", subpercent=85)
            
            # 阶段4: 视频生成
            emit_progress(self.project_id, "EXPORT", "正在生成视频片段...", subpercent=100)
            
            # 阶段5: 处理完成
            emit_progress(self.project_id, "DONE", "处理完成")
            
            # 更新项目状态
            self._update_project_status("completed")
            
            # 同步数据
            self._sync_project_data(project_dir)
            
            logger.info(f"FunClip方案处理完成: {self.project_id}")
            
            return {
                "status": "success",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "pipeline_mode": "funclip",
                "clips_metadata": clips,
                "collections_metadata": collections
            }
            
        except Exception as e:
            logger.error(f"FunClip方案处理失败: {e}")
            raise
    
    async def _process_with_legacy(self, input_video_path: str, input_srt_path: str,
                                  project_dir: Path, metadata_dir: Path,
                                  clips_output_dir: Path, collections_output_dir: Path) -> Dict[str, Any]:
        """使用原6步流水线处理"""
        logger.info("使用原6步流水线")
        
        # 阶段1: 素材准备
        emit_progress(self.project_id, "INGEST", "素材准备完成")
        
        # 阶段2: 字幕处理
        emit_progress(self.project_id, "SUBTITLE", "开始字幕处理")
        
        # 导入流水线步骤
        try:
            from backend.pipeline.step1_outline import run_step1_outline
            from backend.pipeline.step2_timeline import run_step2_timeline
            from backend.pipeline.step3_scoring import run_step3_scoring
            from backend.pipeline.step4_title import run_step4_title
            from backend.pipeline.step5_clustering import run_step5_clustering
            from backend.pipeline.step6_video import run_step6_video
        except ImportError as e:
            logger.error(f"无法导入流水线模块: {e}")
            raise Exception(f"无法导入流水线模块: {e}")
        
        # Step 1: 大纲提取
        emit_progress(self.project_id, "SUBTITLE", "正在提取内容大纲...", subpercent=10)
        step1_output = metadata_dir / "step1_outline.json"
        try:
            srt_path = Path(input_srt_path) if input_srt_path else None
            
            # 如果没有字幕文件，尝试自动生成
            if not srt_path or not srt_path.exists():
                logger.info("未找到字幕文件，尝试自动生成...")
                emit_progress(self.project_id, "SUBTITLE", "正在生成字幕文件...", subpercent=5)
                
                try:
                    from backend.utils.speech_recognizer import generate_subtitle_for_video
                    
                    srt_path = project_dir / "raw" / "subtitle.srt"
                    srt_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    generated_srt = generate_subtitle_for_video(
                        video_path=Path(input_video_path),
                        output_path=srt_path,
                        method="auto",
                        language="auto"
                    )
                    
                    if generated_srt and generated_srt.exists():
                        logger.info(f"字幕文件生成成功: {generated_srt}")
                        srt_path = generated_srt
                    else:
                        raise Exception("字幕生成失败")
                        
                except Exception as asr_error:
                    logger.error(f"自动生成字幕失败: {asr_error}")
                    raise Exception(f"缺少字幕文件，且自动生成失败: {asr_error}")
            
            # 现在应该有字幕文件了，执行Step 1
            if srt_path and srt_path.exists():
                outlines = run_step1_outline(
                    srt_path=srt_path, 
                    metadata_dir=metadata_dir, 
                    output_path=step1_output
                )
            else:
                raise Exception("缺少字幕文件")
        except Exception as e:
            logger.error(f"Step1失败: {e}")
            raise Exception(f"大纲提取失败: {e}")
        
        # Step 2: 时间线分析
        emit_progress(self.project_id, "SUBTITLE", "正在分析时间线...", subpercent=30)
        step2_output = metadata_dir / "step2_timeline.json"
        try:
            timeline_data = run_step2_timeline(
                outline_path=step1_output, 
                metadata_dir=metadata_dir, 
                output_path=step2_output
            )
        except Exception as e:
            logger.error(f"Step2失败: {e}")
            raise Exception(f"时间线分析失败: {e}")
        
        # Step 3: 精彩评分
        emit_progress(self.project_id, "ANALYZE", "正在进行内容评分...", subpercent=50)
        step3_output = metadata_dir / "step3_high_score_clips.json"
        try:
            scored_clips = run_step3_scoring(
                timeline_path=step2_output, 
                metadata_dir=metadata_dir, 
                output_path=step3_output
            )
        except Exception as e:
            logger.error(f"Step3失败: {e}")
            raise Exception(f"精彩评分失败: {e}")
        
        # Step 4: 标题生成
        emit_progress(self.project_id, "ANALYZE", "正在生成片段标题...", subpercent=70)
        step4_output = metadata_dir / "step4_titles.json"
        try:
            clips_with_titles = run_step4_title(
                high_score_clips_path=step3_output,
                output_path=step4_output,
                metadata_dir=str(metadata_dir)
            )
        except Exception as e:
            logger.error(f"Step4失败: {e}")
            raise Exception(f"标题生成失败: {e}")
        
        # Step 5: 主题聚类
        emit_progress(self.project_id, "HIGHLIGHT", "正在进行主题聚类...", subpercent=85)
        step5_output = metadata_dir / "step5_clusters.json"
        try:
            collections = run_step5_clustering(
                clips_with_titles_path=step4_output,
                output_path=step5_output,
                metadata_dir=str(metadata_dir)
            )
        except Exception as e:
            logger.error(f"Step5失败: {e}")
            raise Exception(f"主题聚类失败: {e}")
        
        # Step 6: 视频生成
        emit_progress(self.project_id, "EXPORT", "正在生成视频片段...", subpercent=100)
        
        try:
            video_result = run_step6_video(
                clips_with_titles_path=step4_output,
                collections_path=step5_output,
                input_video=Path(input_video_path),
                output_dir=project_dir / "output",
                clips_dir=str(clips_output_dir),
                collections_dir=str(collections_output_dir),
                metadata_dir=str(metadata_dir)
            )
            
            logger.info(f"视频生成完成: {video_result}")
        except Exception as e:
            error_msg = f"视频生成失败: {e}"
            logger.error(error_msg)
            import traceback
            logger.error(f"详细错误信息:\n{traceback.format_exc()}")
            emit_progress(self.project_id, "EXPORT", error_msg, subpercent=0)
            raise Exception(error_msg)
        
        emit_progress(self.project_id, "EXPORT", "视频导出完成", subpercent=100)
        
        # 阶段6: 处理完成
        emit_progress(self.project_id, "DONE", "处理完成")
        
        # 更新项目状态
        self._update_project_status("completed")
        
        # 同步数据
        self._sync_project_data(project_dir)
        
        logger.info(f"项目处理完成: {self.project_id}")
        
        # 从生成结果中获取元数据
        clips_metadata_path = metadata_dir / "clips_metadata.json"
        clips_metadata = []
        if clips_metadata_path.exists():
            with open(clips_metadata_path, 'r', encoding='utf-8') as f:
                clips_metadata = json.load(f)
        
        collections_metadata_path = metadata_dir / "collections_metadata.json"
        collections_metadata = []
        if collections_metadata_path.exists():
            with open(collections_metadata_path, 'r', encoding='utf-8') as f:
                collections_metadata = json.load(f)
        
        return {
            "status": "success",
            "project_id": self.project_id,
            "task_id": self.task_id,
            "pipeline_mode": "legacy",
            "clips_metadata": clips_metadata,
            "collections_metadata": collections_metadata
        }
    
    def _update_project_status(self, status: str):
        """更新项目状态"""
        try:
            from backend.core.database import SessionLocal
            from backend.services.project_service import ProjectService
            
            db = SessionLocal()
            try:
                project_service = ProjectService(db)
                project_service.update(
                    self.project_id,
                    status=status,
                    progress=100.0,
                    current_step=6
                )
                db.commit()
                logger.info(f"项目 {self.project_id} 状态已更新为 {status}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"更新项目状态失败: {e}")
    
    def _sync_project_data(self, project_dir: Path):
        """同步项目数据到数据库"""
        try:
            from backend.core.database import SessionLocal
            from backend.services.data_sync_service import DataSyncService
            
            db = SessionLocal()
            try:
                sync_service = DataSyncService(db)
                sync_result = sync_service.sync_project_from_filesystem(self.project_id, project_dir)
                if sync_result.get("success"):
                    logger.info(f"项目 {self.project_id} 数据同步成功")
                else:
                    logger.error(f"项目 {self.project_id} 数据同步失败")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"同步项目数据失败: {e}")


def create_simple_pipeline_adapter(project_id: str, task_id: str) -> SimplePipelineAdapter:
    """创建简化的流水线适配器实例"""
    return SimplePipelineAdapter(project_id, task_id)
