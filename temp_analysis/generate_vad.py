"""
生成 VAD 数据 (绕过 torchaudio 版本问题)
"""
import sys, json
from pathlib import Path
sys.path.insert(0, r"E:\ClipProject\autoclip-main1\autoclip-main")

import soundfile as sf
import torch
from silero_vad import load_silero_vad, get_speech_timestamps

PROJECT_DIR = Path(r"E:\ClipProject\autoclip-main1\autoclip-main\data\projects\2628320e-1808-449c-a01d-98f80b505870")
INPUT_AUDIO = PROJECT_DIR / "raw" / "input_audio.wav"
VAD_PATH = PROJECT_DIR / "metadata" / "vad.json"

print("读取音频...")
data, sr = sf.read(str(INPUT_AUDIO), dtype='float32')
if data.ndim > 1:
    data = data.mean(axis=1)
tensor = torch.from_numpy(data)
print(f"音频: {len(data)/sr:.1f}s, {sr}Hz, shape={data.shape}")

print("加载 VAD 模型...")
model = load_silero_vad(onnx=True)
print("VAD 检测中...")
timestamps = get_speech_timestamps(
    tensor, model,
    threshold=0.5,
    min_speech_duration_ms=300,
    min_silence_duration_ms=500,
    return_seconds=True,
)
segments = [(t['start'], t['end']) for t in timestamps]
print(f"检测到 {len(segments)} 段语音, 总时长 {sum(e-s for s,e in segments):.1f}s")

# 保存
VAD_PATH.parent.mkdir(parents=True, exist_ok=True)
data_out = [{"start": round(s, 3), "end": round(e, 3)} for s, e in segments]
with open(VAD_PATH, 'w', encoding='utf-8') as f:
    json.dump(data_out, f, ensure_ascii=False, indent=2)
print(f"已保存: {VAD_PATH}")