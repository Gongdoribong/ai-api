// 웹 개발자 도구에서 console 창에 입력하여 테스트하였습니다.
(async function runSSETest() {
    console.clear();
    console.log("%c [SSE] 테스트 시작!", "color: red; font-weight: bold; font-size: 14px;");
    
    const payload = JSON.stringify({ StudyUID: "31867493", SeriesUID: "20141111", image_index: 93, ClassName: "Liver" });
    const MAX_REQUESTS = 10;
    let times = [];
    let globalStartTime = performance.now();

    async function task(requestIndex) {
        let startTime = performance.now();

        // URL 쿼리 파라미터로 데이터를 보냄
        const url = `http://127.0.0.1:8000/api/sse/stream?StudyUID=31867493&SeriesUID=20141111&image_index=93&ClassName=Liver`;
        
        await new Promise((resolve) => {
            const eventSource = new EventSource(url);

            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.status === "success" || data.status === "error") {
                    // 화면에 polygon 그리기
                    if (data.status === "success" && typeof drawPolygons === "function") {
                        drawPolygons(data.results); // 📍 (script.js에 있는 함수 호출)
                    }
                    let elapsed = performance.now() - startTime;
                    times.push(elapsed);
                    console.log(`✅ [${requestIndex}/${MAX_REQUESTS}] 완료: ${elapsed.toFixed(1)} ms`);
                    if (times.length === MAX_REQUESTS) {
                        let totalElapsed = performance.now() - globalStartTime;
                        printStats("Concurrent SSE", times, "purple", totalElapsed);
                    }
                    eventSource.close();
                    resolve();
                }
            };
            eventSource.onerror = (err) => {
                console.error(`❌ [${requestIndex}/${MAX_REQUESTS}] SSE 통신 에러 발생`);
                eventSource.close();
                resolve();
            };

        });
    }

    for (let i = 1; i <= MAX_REQUESTS; i++) {
        console.log(`요청 보냄: [${i}/${MAX_REQUESTS}]`);
        task(i);
        if (i < MAX_REQUESTS) {
            await new Promise(r => setTimeout(r, 2000));    // 2초마다 요청 보내기 (총 10번)
        }
    }
})();

function printStats(name, timesArray, color, totalElapsed) { // 📍 파라미터 추가
    if (!timesArray || timesArray.length === 0) return;

    const avg = timesArray.reduce((a, b) => a + b, 0) / timesArray.length;
    const stdDev = Math.sqrt(timesArray.reduce((a, b) => a + Math.pow(b - avg, 2), 0) / timesArray.length);
    
    console.log(`%c========================================`, `color: ${color};`);
    console.log(`%c📊 [${name} 테스트 결과 요약]`, `color: ${color}; font-weight: bold;`);
    console.log(`▶ 1회 평균 응답 시간 : ${avg.toFixed(1)} ms`);
    console.log(`▶ 연산 시간 편차   : ±${stdDev.toFixed(1)} ms`);
    
    // 📍 총 소요 시간 출력 로직 추가
    if (totalElapsed) {
        console.log(`▶ 전체 테스트 총 소요 시간 : ${totalElapsed.toFixed(1)} ms`);
    }
    console.log(`%c========================================`, `color: ${color};`);
}