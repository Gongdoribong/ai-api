import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

# 1. 4가지 테스트 시나리오와 파일명 매핑
scenarios = ["Dummy\n(20 Users)", "Dummy Stress\n(100 Users)", "Real Model\n(10 Users)", "Real Stress\n(30 Users)"]
protocols = ["Polling", "SSE", "WebSocket"]
colors = ['#FF9999', '#66B2FF', '#99FF99'] # Polling(빨강), SSE(파랑), WS(초록)

# 지영님이 돌리셨던 명령어를 기반으로 예상되는 CSV 파일명들입니다.
# 만약 파일명이 다르다면 이 부분을 수정해 주세요!
file_map = {
    ("Dummy\n(20 Users)", "Polling"): "polling_result_stats.csv",
    ("Dummy\n(20 Users)", "SSE"): "sse_result_stats.csv",
    ("Dummy\n(20 Users)", "WebSocket"): "ws_result_stats.csv",
    
    ("Dummy Stress\n(100 Users)", "Polling"): "stress_polling_stats.csv",
    ("Dummy Stress\n(100 Users)", "SSE"): "stress_sse_stats.csv",
    ("Dummy Stress\n(100 Users)", "WebSocket"): "stress_ws_stats.csv",
    
    ("Real Model\n(10 Users)", "Polling"): "real_polling_stats.csv",
    ("Real Model\n(10 Users)", "SSE"): "real_sse_stats.csv",
    ("Real Model\n(10 Users)", "WebSocket"): "real_ws_stats.csv",
    
    ("Real Stress\n(30 Users)", "Polling"): "stress_real_polling_stats.csv",
    ("Real Stress\n(30 Users)", "SSE"): "stress_real_sse_stats.csv",
    ("Real Stress\n(30 Users)", "WebSocket"): "stress_real_ws_stats.csv"
}

# 2. 데이터 추출
avg_response_data = {proto: [] for proto in protocols}
total_req_data = {proto: [] for proto in protocols}

for scenario in scenarios:
    for proto in protocols:
        filepath = file_map[(scenario, proto)]
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            agg_row = df[df['Name'] == 'Aggregated'].iloc[0]
            avg_response_data[proto].append(agg_row['Average Response Time'])
            total_req_data[proto].append(agg_row['Request Count'])
        else:
            print(f"⚠️ '{filepath}' 파일을 찾을 수 없어 0으로 처리합니다.")
            avg_response_data[proto].append(0)
            total_req_data[proto].append(0)

# 3. 그룹형 막대 그래프 그리기
plt.style.use('seaborn-v0_8-whitegrid')
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))

x = np.arange(len(scenarios))  # 시나리오별 x축 위치
width = 0.25  # 막대 두께

# 📈 첫 번째 그래프: 평균 응답 시간 (Latency)
for i, proto in enumerate(protocols):
    offset = (i - 1) * width
    bars = ax1.bar(x + offset, avg_response_data[proto], width, label=proto, color=colors[i], edgecolor='black')
    
    # 막대 위에 수치 표시
    for bar in bars:
        yval = bar.get_height()
        if yval > 0:
            ax1.text(bar.get_x() + bar.get_width()/2, yval + (max([max(v) for v in avg_response_data.values()]) * 0.02),
                    f"{yval:.0f}ms", ha='center', va='bottom', fontsize=10, fontweight='bold')

ax1.set_title('Average Response Time Across 4 Test Scenarios', fontsize=16, pad=15)
ax1.set_ylabel('Milliseconds (ms)', fontsize=14)
ax1.set_xticks(x)
ax1.set_xticklabels(scenarios, fontsize=12)
ax1.legend(fontsize=12)

# 📈 두 번째 그래프: 총 네트워크 요청 횟수 (서버 부하)
for i, proto in enumerate(protocols):
    offset = (i - 1) * width
    bars = ax2.bar(x + offset, total_req_data[proto], width, label=proto, color=colors[i], edgecolor='black')
    
    # 막대 위에 수치 표시
    for bar in bars:
        yval = bar.get_height()
        if yval > 0:
            ax2.text(bar.get_x() + bar.get_width()/2, yval + (max([max(v) for v in total_req_data.values()]) * 0.02),
                    f"{int(yval):,} reqs", ha='center', va='bottom', fontsize=10, fontweight='bold')

ax2.set_title('Total Network Requests (Server Load) Across 4 Test Scenarios', fontsize=16, pad=15)
ax2.set_ylabel('Request Count', fontsize=14)
ax2.set_xticks(x)
ax2.set_xticklabels(scenarios, fontsize=12)
ax2.legend(fontsize=12)

# 여백 조정 및 이미지 저장
plt.tight_layout()
image_name = 'all_scenarios_comparison.png'
plt.savefig(image_name, dpi=300, bbox_inches='tight')
print(f"\n✅ 성공! 4가지 환경을 모두 비교한 그래프가 '{image_name}'로 저장되었습니다.")