"""
重新运行step6视频生成
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def regenerate_videos(project_id: str):
    project_dir = Path(f"d:/Download/autoclip-main1/autoclip-main/data/projects/{project_id}")
    metadata_dir = project_dir / "metadata"
    output_dir = project_dir / "output"
    raw_dir = project_dir / "raw"

    input_video = raw_dir / "input.mp4"
    if not input_video.exists():
        logger.error(f"输入视频不存在: {input_video}")
        return False

    from backend.pipeline.step6_video import run_step6_video

    clips_output_dir = output_dir / "clips"
    collections_output_dir = output_dir / "collections"
    clips_output_dir.mkdir(parents=True, exist_ok=True)
    collections_output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("开始重新生成视频切片...")
    video_result = run_step6_video(
        metadata_dir / "step4_titles.json",
        metadata_dir / "step5_collections.json",
        input_video,
        output_dir=output_dir,
        clips_dir=str(clips_output_dir),
        collections_dir=str(collections_output_dir),
        metadata_dir=str(metadata_dir)
    )

    logger.info(f"视频生成结果: {video_result}")
    return True

if __name__ == "__main__":
    project_id = "2716cdeb-fb3e-461d-87a8-312dcf077b9f"
    regenerate_videos(project_id)
