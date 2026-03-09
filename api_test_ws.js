// 웹 개발자 도구에서 console 창에 입력하여 테스트하였습니다.
(function runWSTest() {
    console.clear();
    console.log("%c🚀 [WebSocket] 2초 대기 포함 10회 연속 테스트 시작!", "color: green; font-weight: bold; font-size: 14px;");
    
    const ws = new WebSocket("ws://127.0.0.1:8000/api/websocket/ws");
    const payload = JSON.stringify({ StudyUID: "31867493", SeriesUID: "20141111", image_index: 93, ClassName: "Liver" });
    const MAX_REQUESTS = 10;
    
    let times = [];
    let count = 0;
    let startTime;

    ws.onopen = () => sendNextRequest();

    function sendNextRequest() {
        if (count >= MAX_REQUESTS) {
            ws.close();
            printStats("WebSocket", times, "green");
            return;
        }
        count++;
        startTime = performance.now();
        ws.send(payload);
    }

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.status === "success" || data.status === "error") {
            const elapsed = performance.now() - startTime;
            times.push(elapsed);
            
            if (count < MAX_REQUESTS) {
                console.log(`[${count}/${MAX_REQUESTS}] 완료: ${elapsed.toFixed(1)} ms ⏳ (2초 대기 중...)`);
                // 💡 AI 연산 완료 후 2초(2000ms) 대기!
                setTimeout(sendNextRequest, 2000); 
            } else {
                console.log(`[${count}/${MAX_REQUESTS}] 완료: ${elapsed.toFixed(1)} ms`);
                sendNextRequest(); // 종료 로직으로 이동
            }
        }
    };
})();

// 통계 출력용 공통 함수 (복사 시 함께 포함해주세요)
function printStats(name, timesArray, color) {
    const avg = timesArray.reduce((a, b) => a + b, 0) / timesArray.length;
    const stdDev = Math.sqrt(timesArray.reduce((a, b) => a + Math.pow(b - avg, 2), 0) / timesArray.length);
    console.log(`%c========================================`, `color: ${color};`);
    console.log(`%c📊 [${name} 테스트 결과 요약]`, `color: ${color}; font-weight: bold;`);
    console.log(`▶ 평균 응답 시간 : ${avg.toFixed(1)} ms`);
    console.log(`▶ 연산 시간 편차 : ±${stdDev.toFixed(1)} ms`);
    console.log(`%c========================================`, `color: ${color};`);
}