"""Prompt 加载器：统一从 backend/prompt/ 读取模板文件。"""

from functools import lru_cache
from pathlib import Path
from typing import Dict

from backend.core.shared_config import PROMPT_FILES

FUNCLIP_PROMPT_KEYS: Dict[str, str] = {
    'clip_only': 'funclip_clip_only',
    'title': 'funclip_title',
    'step1_boundary': 'funclip_step1_boundary',
    'step1_5_gapfill': 'funclip_step1_5_gapfill',
    'step2_batch_score': 'funclip_step2_batch_score',
    'step3_batch_title': 'funclip_step3_batch_title',
    'merged': 'funclip_merged',
}


@lru_cache(maxsize=32)
def load_prompt_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    return path.read_text(encoding='utf-8')


def get_prompt(key: str) -> str:
    """按 PROMPT_FILES 键名加载 Prompt。"""
    path = PROMPT_FILES.get(key)
    if path is None:
        raise KeyError(f"未知 Prompt 键: {key}")
    return load_prompt_file(path)


def get_funclip_prompt(name: str) -> str:
    """按 FunClip 子名称加载 Prompt。"""
    prompt_key = FUNCLIP_PROMPT_KEYS.get(name)
    if prompt_key is None:
        raise KeyError(f"未知 FunClip Prompt: {name}")
    return get_prompt(prompt_key)
