import matplotlib.pyplot as plt
import numpy as np

# 1. 데이터 설정
methods = ['Polling', 'SSE', 'WebSocket']
avg_times = [10603.0, 12044.6, 10455.6]
std_devs = [1425.4, 2985.8, 316.5]
colors = ['#ff4d4d', '#9b59b6', '#2ecc71'] # Polling(빨강), SSE(보라), WS(초록)

# 2. 그래프 스타일 설정
plt.style.use('seaborn-v0_8-whitegrid')
fig, ax = plt.subplots(figsize=(10, 7))

# 3. 막대 그래프 그리기 (yerr에 편차 데이터 입력)
bars = ax.bar(methods, avg_times, yerr=std_devs, color=colors, 
                capsize=10, edgecolor='black', alpha=0.8, error_kw={'elinewidth':2, 'ecolor':'#333333'})

# 4. 수치 표시 (막대 위 평균값)
for bar in bars:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 100,
            f'{height:.1f}ms', ha='center', va='bottom', fontsize=12, fontweight='bold')

# 5. 그래프 정보 설정
ax.set_title('Inference Latency & Stability Comparison (Slice #93)', fontsize=16, pad=20)
ax.set_ylabel('Response Time (ms)', fontsize=13)
ax.set_xlabel('Communication Protocol', fontsize=13)

# Y축 범위 조정 (데이터가 잘 보이도록)
ax.set_ylim(0, max(avg_times) + max(std_devs) + 2000)

# 6. 결과 저장
plt.tight_layout()
image_name = 'stability_comparison_result.png'
plt.savefig(image_name, dpi=300)
print(f"✅ 그래프가 '{image_name}'로 저장되었습니다. 수치를 확인해 보세요!")