// 웹 개발자 도구에서 console 창에 입력하여 테스트하였습니다.
(function runWSTest() {
    console.clear();
    console.log("%c [WebSocket] 테스트 시작!", "color: red; font-weight: bold; font-size: 14px;");
    
    const ws = new WebSocket("ws://127.0.0.1:8000/api/websocket/ws");
    const payload = JSON.stringify({ StudyUID: "31867493", SeriesUID: "20141111", image_index: 93, ClassName: "Liver" });
    const MAX_REQUESTS = 10;
    
    let times = [];
    let startTimes = []; // 📍 각 요청의 시작 시간을 순서대로 기억할 대기열(Queue)
    let completedCount = 0;
    let globalStartTime;

    // 1. 소켓 연결이 완벽하게 뚫렸을 때 테스트를 시작합니다.
    ws.onopen = async () => {
        globalStartTime = performance.now(); // ⏱️ 전체 타이머 ON!

        for (let i = 1; i <= MAX_REQUESTS; i++) {
            console.log(`요청 보냄: [${i}/${MAX_REQUESTS}]`);

            startTimes.push(performance.now())
            ws.send(payload); // 📍 새 연결 없이 기존 ws 통로로 데이터만 슛!

            if (i < MAX_REQUESTS) {
                await new Promise(r => setTimeout(r, 2000)); // 2초 뒤 다음 요청 발사
            }
        }
    };

    // 2. 서버에서 진행 상황이나 결과가 파이프를 타고 들어올 때 반응합니다.
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.status === "success" || data.status === "error") {
            completedCount++;
            
            // 📍 대기열에서 가장 오래된(먼저 보냈던) 요청의 시작 시간을 꺼냅니다.
            const startTime = startTimes.shift(); 

            // 화면에 polygon 그리기
            if (data.status === "success" && typeof drawPolygons === "function") {
                drawPolygons(data.results); // 📍 (script.js에 있는 함수 호출)
            }

            const elapsed = performance.now() - startTime;
            times.push(elapsed);
            
            console.log(`✅ [${completedCount}/${MAX_REQUESTS}] 완료: ${elapsed.toFixed(1)} ms`);

            // 10개의 결과가 모두 무사히 도착했을 때
            if (completedCount === MAX_REQUESTS) {
                let totalElapsed = performance.now() - globalStartTime; // ⏱️ 전체 타이머 OFF!
                printStats("Concurrent WebSocket", times, "green", totalElapsed);
                ws.close(); // 모든 작업이 끝났으니 마지막에 통로를 닫습니다.
            }
        }
    };

    ws.onerror = (err) => {
        console.error("❌ WebSocket 통신 에러 발생", err);
        ws.close();
    };
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