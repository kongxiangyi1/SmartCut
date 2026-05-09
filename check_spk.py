"""
检查 CAM++ 说话人检测结果
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

audio_path = r"E:\直播切片项目\output\20260420_新录制\test_output\clip_001_product_0s-708s_audio.wav"

print("="*60)
print("检查 CAM++ 说话人检测结果")
print("="*60)

from funasr import AutoModel

model = AutoModel(
    model="paraformer-zh",
    vad_model="fsmn-vad",
    vad_kwargs={"max_single_segment_time": 60000},
    punc_model="ct-punc",
    spk_model="cam++",
    device="cpu"
)

print("\n执行识别 (return_spk=True)...")
result = model.generate(input=audio_path, batch_size_s=30, return_spk=True)

if result:
    first = result[0]
    sentence_info = first.get('sentence_info', [])

    print(f"\n句子总数: {len(sentence_info)}")

    # 统计说话人
    spk_count = {}
    for sent in sentence_info:
        spk = sent.get('spk', 'N/A')
        spk_count[spk] = spk_count.get(spk, 0) + 1

    print(f"\n说话人统计: {spk_count}")

    # 显示前10个句子的说话人
    print("\n前10个句子的说话人:")
    for i, sent in enumerate(sentence_info[:10]):
        spk = sent.get('spk', 'N/A')
        text = sent.get('text', '')[:20]
        start = sent.get('start', 0)
        end = sent.get('end', 0)
        print(f"  [{i+1}] spk={spk}, time={start}-{end}ms, text='{text}...'")
