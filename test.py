import pandas as pd
import matplotlib.pyplot as plt

# 1. CSV 파일 불러오기
df = pd.read_csv('benchmark_results.csv')

# 그래프 스타일 설정
plt.style.use('seaborn-v0_8-muted')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

# --- 그래프 1: 평균 응답 시간 (오차 막대 포함) ---
methods = df['Method']
avg_times = df['Avg_Response_Time_ms']
std_devs = df['Std_Dev_ms']
colors = ['#ff9999', '#66b3ff', '#99ff99']

bars1 = ax1.bar(methods, avg_times, yerr=std_devs, color=colors, capsize=10, alpha=0.8)
ax1.set_title('Average Response Time per Request', fontsize=14, fontweight='bold', pad=15)
ax1.set_ylabel('Time (ms)', fontsize=12)
ax1.grid(axis='y', linestyle='--', alpha=0.6)

# 막대 위에 수치 표시
for bar in bars1:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2, yval + 1000, f'{yval:,.1f}', 
            ha='center', va='bottom', fontweight='bold')

# --- 그래프 2: 전체 테스트 소요 시간 ---
total_times = df['Total_Duration_ms']

bars2 = ax2.bar(methods, total_times, color=colors, alpha=0.8)
ax2.set_title('Total Test Duration (10 Requests)', fontsize=14, fontweight='bold', pad=15)
ax2.set_ylabel('Time (ms)', fontsize=12)
ax2.grid(axis='y', linestyle='--', alpha=0.6)

# 막대 위에 수치 표시
for bar in bars2:
    yval = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2, yval + 1000, f'{yval:,.1f}', 
            ha='center', va='bottom', fontweight='bold')

plt.tight_layout()
plt.show()