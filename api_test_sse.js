// 웹 개발자 도구에서 console 창에 입력하여 테스트하였습니다.
(async function runSSETest() {
    console.clear();
    console.log("%c🚀 [SSE] 2초 대기 포함 10회 연속 테스트 시작!", "color: purple; font-weight: bold; font-size: 14px;");
    
    const url = `http://127.0.0.1:8000/api/sse/stream?StudyUID=31867493&SeriesUID=20141111&image_index=93&ClassName=Liver`;
    const MAX_REQUESTS = 10;
    let times = [];

    for (let i = 1; i <= MAX_REQUESTS; i++) {
        let startTime = performance.now();
        
        await new Promise((resolve) => {
            const eventSource = new EventSource(url);
            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.status === "success" || data.status === "error") {
                    let elapsed = performance.now() - startTime;
                    times.push(elapsed);
                    
                    if (i < MAX_REQUESTS) {
                        console.log(`[${i}/${MAX_REQUESTS}] 완료: ${elapsed.toFixed(1)} ms ⏳ (2초 대기 중...)`);
                    } else {
                        console.log(`[${i}/${MAX_REQUESTS}] 완료: ${elapsed.toFixed(1)} ms`);
                    }
                    eventSource.close();
                    resolve();
                }
            };
        });
        
        // 💡 완료 후 2초(2000ms) 대기!
        if (i < MAX_REQUESTS) {
            await new Promise(r => setTimeout(r, 2000));
        }
    }
    printStats("SSE", times, "purple");
})();

function printStats(name, timesArray, color) {
    const avg = timesArray.reduce((a, b) => a + b, 0) / timesArray.length;
    const stdDev = Math.sqrt(timesArray.reduce((a, b) => a + Math.pow(b - avg, 2), 0) / timesArray.length);
    console.log(`%c========================================`, `color: ${color};`);
    console.log(`%c📊 [${name} 테스트 결과 요약]`, `color: ${color}; font-weight: bold;`);
    console.log(`▶ 평균 응답 시간 : ${avg.toFixed(1)} ms`);
    console.log(`▶ 연산 시간 편차 : ±${stdDev.toFixed(1)} ms`);
    console.log(`%c========================================`, `color: ${color};`);
}