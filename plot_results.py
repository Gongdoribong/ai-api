import pandas as pd
import matplotlib.pyplot as plt
import os

# 1. 분석할 CSV 파일 이름 세팅 (지영님이 돌리신 결과 파일명으로 맞춰주세요)
files = {
    "Polling": "stress_real_polling_stats.csv",
    "SSE": "stress_real_sse_stats.csv",
    "WebSocket": "stress_real_ws_stats.csv"
}

# 2. 데이터 추출을 위한 리스트
protocols = []
avg_response_times = []
total_requests = []

# CSV 파일을 읽어서 마지막 'Aggregated(총합)' 행의 데이터를 가져옵니다.
for name, filepath in files.items():
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        # Locust 통계의 가장 마지막 줄인 'Aggregated' 데이터 추출
        agg_row = df[df['Name'] == 'Aggregated'].iloc[0]
        
        protocols.append(name)
        avg_response_times.append(agg_row['Average Response Time'])
        total_requests.append(agg_row['Request Count'])
    else:
        print(f"⚠️ 경고: '{filepath}' 파일을 찾을 수 없습니다.")

# 3. 데이터가 정상적으로 로드되었다면 막대 그래프 2개 그리기
if protocols:
    # 폰트 및 스타일 설정 (논문용으로 깔끔하게)
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    colors = ['#FF9999', '#66B2FF', '#99FF99'] # Polling(빨강), SSE(파랑), WS(초록)

    # 📈 첫 번째 그래프: 평균 응답 시간 (Latency)
    bars1 = ax1.bar(protocols, avg_response_times, color=colors, edgecolor='black', linewidth=1)
    ax1.set_title('Average Response Time (ms)\n[Lower is Better]', fontsize=14, pad=15)
    ax1.set_ylabel('Milliseconds (ms)', fontsize=12)
    ax1.tick_params(axis='x', labelsize=12)
    
    # 막대 위에 정확한 수치 적어주기
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + (max(avg_response_times)*0.02), 
                f"{yval:.1f} ms", ha='center', va='bottom', fontweight='bold')

    # 📈 두 번째 그래프: 총 네트워크 요청 횟수 (서버 부하)
    bars2 = ax2.bar(protocols, total_requests, color=colors, edgecolor='black', linewidth=1)
    ax2.set_title('Total Network Requests (3 mins)\n[Lower is Better for Server]', fontsize=14, pad=15)
    ax2.set_ylabel('Request Count', fontsize=12)
    ax2.tick_params(axis='x', labelsize=12)

    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, yval + (max(total_requests)*0.02), 
                f"{int(yval):,} reqs", ha='center', va='bottom', fontweight='bold')

    # 여백 조정 및 이미지 저장
    plt.tight_layout()
    image_name = 'protocol_comparison_chart.png'
    plt.savefig(image_name, dpi=300, bbox_inches='tight') # 논문용 고해상도(300dpi) 저장
    print(f"✅ 성공! 그래프가 '{image_name}' 파일로 저장되었습니다.")