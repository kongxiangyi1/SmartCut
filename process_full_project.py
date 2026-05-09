#!/usr/bin/env python3
"""
完整项目处理脚本：语音识别 + 流水线执行
自动处理上传的视频文件
"""

import sys
import json
import asyncio
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置日志
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def generate_subtitle(project_id: str):
    """使用语音识别生成字幕"""
    logger.info("\n🎙️ 开始语音识别生成字幕...")
    
    from backend.utils.speech_recognizer import SpeechRecognizer
    
    data_root = project_root / "data" / "projects" / project_id
    input_video_path = data_root / "raw" / "input.mp4"
    output_srt_path = data_root / "raw" / "input.srt"
    
    if not input_video_path.exists():
        raise FileNotFoundError(f"视频文件不存在: {input_video_path}")
    
    logger.info(f"📹 输入视频: {input_video_path}")
    logger.info(f"📝 输出字幕: {output_srt_path}")
    
    # 创建语音识别器
    recognizer = SpeechRecognizer()
    
    # 执行语音识别
    result_path = recognizer.generate_subtitle(
        video_path=input_video_path,
        output_path=output_srt_path
    )
    
    if result_path and result_path.exists():
        logger.info(f"✅ 语音识别成功，生成字幕文件: {result_path}")
        return True
    else:
        raise Exception("语音识别失败，未生成字幕文件")

async def process_project(project_id: str):
    """完整处理项目：语音识别 + 流水线执行"""
    print(f"\n{'='*60}")
    print(f"🚀 开始处理项目: {project_id}")
    print(f"📅 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    try:
        # Step 1: 语音识别生成字幕
        generate_subtitle(project_id)
        
        # Step 2: 创建数据库会话
        from backend.core.database import SessionLocal
        db = SessionLocal()
        
        try:
            # 验证项目是否存在
            from backend.models.project import Project
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"项目 {project_id} 不存在")
            
            logger.info(f"✅ 验证项目存在: {project.name}")
            
            # 检查文件
            data_root = project_root / "data" / "projects" / project_id
            input_video_path = data_root / "raw" / "input.mp4"
            input_srt_path = data_root / "raw" / "input.srt"
            
            logger.info(f"📹 视频文件: {input_video_path}")
            logger.info(f"📝 字幕文件: {input_srt_path}")
            
            # 创建任务记录
            from backend.models.task import Task, TaskStatus
            
            task = Task(
                name=f"完整流水线处理",
                description=f"语音识别+流水线处理项目 {project_id}",
                task_type="VIDEO_PROCESSING",
                project_id=project_id,
                status=TaskStatus.RUNNING,
                progress=0,
                current_step="语音识别完成",
                total_steps=6
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            
            logger.info(f"📋 任务记录已创建: {task.id}")
            
            # 创建Pipeline适配器
            from backend.services.pipeline_adapter import create_pipeline_adapter_sync
            pipeline_adapter = create_pipeline_adapter_sync(db, str(task.id), project_id)
            
            # 验证流水线前置条件
            logger.info("🔍 验证流水线前置条件...")
            errors = pipeline_adapter.validate_pipeline_prerequisites()
            if errors:
                error_msg = "; ".join(errors)
                logger.error(f"❌ 流水线前置条件验证失败: {error_msg}")
                raise ValueError(f"流水线前置条件验证失败: {error_msg}")
            
            logger.info("✅ 流水线前置条件验证通过")
            
            # 执行完整的流水线处理
            logger.info("\n🎬 开始执行完整流水线...")
            logger.info("-" * 40)
            
            result = await pipeline_adapter.process_project(
                input_video_path=str(input_video_path),
                input_srt_path=str(input_srt_path)
            )
            
            # 检查处理结果
            if result.get('status') == 'failed':
                error_msg = result.get('message', '处理失败')
                logger.error(f"\n❌ 流水线处理失败: {error_msg}")
                
                task.status = TaskStatus.FAILED
                task.error_message = error_msg
                db.commit()
                
                print(f"\n{'='*60}")
                print(f"❌ 项目执行失败")
                print(f"📅 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"❌ 错误信息: {error_msg}")
                print(f"{'='*60}")
                
                return {"success": False, "error": error_msg, "result": result}
            else:
                logger.info("\n🎉 流水线处理成功！")
                logger.info(f"📊 处理结果: {result}")
                
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.current_step = "处理完成"
                db.commit()
                
                print(f"\n{'='*60}")
                print(f"✅ 项目执行完成")
                print(f"📅 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"📊 处理结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
                print(f"{'='*60}")
                
                return {"success": True, "result": result, "message": "流水线处理完成"}
                
        finally:
            db.close()
            
    except Exception as e:
        error_msg = f"处理项目失败: {str(e)}"
        logger.error(f"\n❌ {error_msg}")
        import traceback
        traceback.print_exc()
        
        # 尝试更新任务状态
        try:
            from backend.core.database import SessionLocal
            db = SessionLocal()
            task = db.query(Task).filter(Task.project_id == project_id).order_by(Task.created_at.desc()).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = error_msg
                db.commit()
            db.close()
        except Exception as db_error:
            logger.error(f"更新任务状态失败: {db_error}")
        
        print(f"\n{'='*60}")
        print(f"❌ 项目执行失败")
        print(f"📅 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"❌ 错误信息: {error_msg}")
        print(f"{'='*60}")
        
        return {"success": False, "error": error_msg}

async def main():
    """主函数"""
    project_id = "0aed14ca-ca08-4241-a17d-cb9a98355c97"
    
    print(f"🎯 目标项目: {project_id}")
    print(f"⏳ 开始完整处理...\n")
    
    result = await process_project(project_id)
    
    if result["success"]:
        print(f"\n✅ 项目处理成功！")
    else:
        print(f"\n❌ 项目处理失败: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())