import sys
sys.path.insert(0, 'e:/ClipProject/autoclip-main1/autoclip-main')
from backend.utils.llm_client import LLMClient
import json
from pathlib import Path

client = LLMClient()

prompt_path = 'e:/ClipProject/autoclip-main1/autoclip-main/backend/prompt/推荐理由.txt'
with open(prompt_path, 'r', encoding='utf-8') as f:
    prompt = f.read()

timeline_path = Path('e:/ClipProject/autoclip-main1/autoclip-main/data/projects/a9e1527c-13a2-496d-a06a-5a80b3c5648e/metadata/step2_timeline.json')
with open(timeline_path, 'r', encoding='utf-8') as f:
    timeline_data = json.load(f)

test_data = []
for item in timeline_data:
    test_data.append({
        'outline': item.get('outline'),
        'content': item.get('content'),
        'start_time': item.get('start_time'),
        'end_time': item.get('end_time'),
    })

print(f'Testing with {len(test_data)} items')
response = client.call_with_retry(prompt, test_data, max_retries=1)
if response:
    print('Response length:', len(response))
    print('Response:')
    print(response)