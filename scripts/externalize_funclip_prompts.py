"""将 funclip_style.py 内嵌 Prompt 替换为文件加载。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
target = ROOT / "backend/pipeline/funclip_style.py"
text = target.read_text(encoding="utf-8")

replacement = '''from backend.pipeline.prompt_loader import get_funclip_prompt

FUNCLIP_CLIP_ONLY_PROMPT = get_funclip_prompt('clip_only')
FUNCLIP_TITLE_PROMPT = get_funclip_prompt('title')
FUNCLIP_STEP1_BOUNDARY_PROMPT = get_funclip_prompt('step1_boundary')
FUNCLIP_STEP2_BATCH_SCORE_PROMPT = get_funclip_prompt('step2_batch_score')
FUNCLIP_STEP3_BATCH_TITLE_PROMPT = get_funclip_prompt('step3_batch_title')
FUNCLIP_MERGED_PROMPT = get_funclip_prompt('merged')

'''

start = text.index("# 第一阶段Prompt：仅识别片段边界")
end = text.index("# 填充词列表（预处理时剔除", start)
new_text = text[:start] + replacement + text[end:]
target.write_text(new_text, encoding="utf-8")
print("funclip_style.py prompts externalized")
