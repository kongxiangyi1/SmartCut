"""一次性脚本：从 funclip_style.py 提取 Prompt 到 backend/prompt/"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "backend/pipeline/funclip_style.py").read_text(encoding="utf-8")
out_dir = ROOT / "backend/prompt"

mapping = {
    "FUNCLIP_CLIP_ONLY_PROMPT": "funclip_clip_only.txt",
    "FUNCLIP_TITLE_PROMPT": "funclip_title.txt",
    "FUNCLIP_STEP1_BOUNDARY_PROMPT": "funclip_step1_boundary.txt",
    "FUNCLIP_STEP2_BATCH_SCORE_PROMPT": "funclip_step2_batch_score.txt",
    "FUNCLIP_STEP3_BATCH_TITLE_PROMPT": "funclip_step3_batch_title.txt",
    "FUNCLIP_MERGED_PROMPT": "funclip_merged.txt",
}

for var, filename in mapping.items():
    pattern = rf'{var} = """(.*?)"""'
    match = re.search(pattern, src, re.DOTALL)
    if not match:
        raise SystemExit(f"missing {var}")
    out_dir.joinpath(filename).write_text(match.group(1), encoding="utf-8")
    print(f"wrote {filename} ({len(match.group(1))} chars)")
