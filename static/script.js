let currentIdx = 0; 
let totalImages = 0; 
let currentStudyUID = "";
let currentSeriesUID = "";

const baseCanvas = document.getElementById('baseCanvas');
const drawCanvas = document.getElementById('drawCanvas');
const ctx = baseCanvas.getContext('2d');
const dCtx = drawCanvas.getContext('2d');

window.onload = checkHealth;

async function checkHealth() {
    try {
        const res = await fetch('/health');
        const data = await res.json();
        document.getElementById('serverStatus').innerHTML = "Online 🟢 (" + data.device + ")";
        document.getElementById('serverStatus').style.color = "#4caf50";
    } catch (e) { 
        document.getElementById('serverStatus').innerText = "Offline 🔴"; 
    }
}

// 1. 폴더 업로드
document.getElementById('folderInput').addEventListener('change', async function(e) {
    const files = e.target.files;
    if (files.length === 0) return;

    const loadingBox = document.getElementById('loadingBox');
    loadingBox.innerText = `Uploading ${files.length} files... ⏳`;
    loadingBox.style.display = 'block';

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        const name = files[i].name.toLowerCase();
        if (name.endsWith('.dcm') || name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg')) {
            formData.append('files', files[i]);
        }
    }

    try {
        const res = await fetch('/api/upload_folder', { 
            method: 'POST',
            body: formData 
        });

        const data = await res.json();
        
        if (res.ok && data.count > 0) {
            totalImages = data.count; 
            currentStudyUID = data.StudyUID;
            currentSeriesUID = data.SeriesUID;

            document.getElementById('sliceSlider').disabled = false;
            document.getElementById('btnPrev').disabled = false;
            document.getElementById('btnNext').disabled = false;
            document.getElementById('canvasContainer').style.display = 'block';
            document.getElementById('placeholder').style.display = 'none';
            loadImage(0);
        } else {
            alert("업로드된 유효한 이미지(DICOM/PNG 등)가 없습니다.");
        }
    } catch (err) {
        console.error("업로드 에러:", err);
        alert("파일 업로드 중 서버와 통신할 수 없습니다.");
    } finally {
        loadingBox.innerText = "Thinking... 🧠";
        loadingBox.style.display = 'none';
        this.value = ''; 
    }
});

// 2. 이미지 로드
async function loadImage(idx) {
    currentIdx = idx; 
    // 슬라이스가 바뀔 때마다 캔버스를 깨끗하게 비워줍니다.
    dCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    
    const res = await fetch(`/api/image/${idx}`);
    const data = await res.json();
    baseCanvas.width = data.width;
    baseCanvas.height = data.height;
    drawCanvas.width = data.width;
    drawCanvas.height = data.height;

    const img = new Image();
    img.onload = () => ctx.drawImage(img, 0, 0);
    img.src = "data:image/png;base64," + (data.image || data.image_b64);

    document.getElementById('sliceSlider').max = totalImages - 1;
    document.getElementById('sliceSlider').value = idx;
    document.getElementById('sliceInfo').innerText = `${idx + 1} / ${totalImages}`;
}

function changeSlice(d) { 
    let n = currentIdx + d; 
    if (n >= 0 && n < totalImages) loadImage(n); 
}

function onSliderChange(v) { 
    loadImage(parseInt(v)); 
}

// 3. 토글 및 클리어 기능
function toggleMask() {
    // 이제 img 태그가 없으므로 drawCanvas 자체의 투명도를 조절합니다.
    drawCanvas.style.opacity = (drawCanvas.style.opacity === "0") ? "1" : "0";
}

function clearMask() {
    dCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
}

window.addEventListener('keydown', e => {
    if (e.code === 'Space') { e.preventDefault(); toggleMask(); }
    if (e.key === 'ArrowLeft') changeSlice(-1);
    if (e.key === 'ArrowRight') changeSlice(1);
});

// ==========================================
// 🎨 공통 렌더링 함수: 어떤 통신 방식이든 좌표만 받아서 화면에 그립니다.
// ==========================================
function drawPolygons(results) {
    dCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
            
    results.forEach(ann => {
        const poly = ann.data.polyline;
        if (!poly || poly.length === 0) return;
        
        dCtx.beginPath();
        dCtx.moveTo(poly[0][0], poly[0][1]);
        
        for (let i = 1; i < poly.length; i++) {
            dCtx.lineTo(poly[i][0], poly[i][1]);
        }
        
        if (ann.data.contour.closed) dCtx.closePath();
        
        dCtx.strokeStyle = ann.color;
        dCtx.lineWidth = 2;
        dCtx.stroke();
        
        dCtx.fillStyle = ann.color + "40"; 
        dCtx.fill();
    });
}

// ==========================================
// 🔀 통신 모드 라우터 (버튼 클릭 시 실행됨) - 업데이트!
// ==========================================
function executeAutoSegment() {
    const selectedMode = document.querySelector('input[name="commMode"]:checked').value;
    
    if (selectedMode === 'polling') {
        console.log("🔄 Polling 모드로 실행합니다.");
        runAutoInferencePolling(); 
    } 
    else if (selectedMode === 'sse') {
        console.log("🌊 SSE 모드로 실행합니다.");
        runAutoInferenceSSE();
    }
    else if (selectedMode === 'websocket') {
        console.log("⚡ WebSocket 모드로 실행합니다.");
        runAutoInferenceWebSocket();
    }
}

// ==========================================
// 📡 4. Task Queue (Polling) 방식의 추론 요청 함수
// ==========================================
async function runAutoInferencePolling() { 
    const loadingBox = document.getElementById('loadingBox');
    loadingBox.style.display = 'block';
    loadingBox.innerText = '서버에 작업 지시 중... 🚀';

    try {
        // 💡 만약 변수가 비어있다면 아예 누락되지 않도록 빈 문자열("")로 보호합니다.
        const payload = {
            "StudyUID": currentStudyUID || "",
            "SeriesUID": currentSeriesUID || "",
            "image_index": currentIdx,
            "ClassName": "Liver"
        };

        // 1단계: 서버에 요청하고 진동벨(Task ID) 받기
        const submitRes = await fetch('/api/polling/submit', {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        const submitData = await submitRes.json();
        
        // 🚨 [방어 코드] 422 에러 등이 발생하면 무한루프를 돌지 않고 멈춥니다!
        if (!submitRes.ok) {
            console.error("서버 에러 상세:", submitData);
            alert("서버가 요청을 거절했습니다(422): \n" + JSON.stringify(submitData.detail || submitData));
            loadingBox.style.display = 'none';
            return; // 여기서 함수 완전 종료!
        }

        const taskId = submitData.task_id;
        let elapsedSeconds = 0;
        loadingBox.innerText = `추론 진행 중... (0초 경과) ⏳`;

        // 2단계: status 확인
        const pollInterval = setInterval(async () => {
            elapsedSeconds++;
            loadingBox.innerText = `추론 진행 중... (${elapsedSeconds}초 경과) ⏳`;

            // 서버에 상태 물어보기
            const statusRes = await fetch(`/api/polling/status/${taskId}`);
            const taskData = await statusRes.json();

            // 3단계: 상태에 따른 분기 처리
            if (taskData.status === 'success') {
                clearInterval(pollInterval); 
                drawPolygons(taskData.results); 
                loadingBox.style.display = 'none'; 
                
            } else if (taskData.status === 'error') {
                clearInterval(pollInterval); 
                alert("백그라운드 추론 에러: " + taskData.message);
                loadingBox.style.display = 'none';
            }
        }, 1000); 

    } catch (e) {
        console.error("통신 에러:", e);
        alert("서버와 통신할 수 없습니다.");
        loadingBox.style.display = 'none';
    }
}

// ==========================================
// 📡 5. Server-Sent Events (SSE) 방식의 추론 요청 함수
// ==========================================
function runAutoInferenceSSE() {
    const loadingBox = document.getElementById('loadingBox');
    loadingBox.style.display = 'block';
    loadingBox.innerText = '서버와 스트리밍 연결 중... 🔌';

    // SSE는 GET 요청을 사용하므로 URL 파라미터로 데이터를 넘깁니다.
    const url = `/api/sse/stream?StudyUID=${currentStudyUID || ""}&SeriesUID=${currentSeriesUID || ""}&image_index=${currentIdx}`;
    
    // 브라우저 내장 SSE 수신기 객체 생성
    const evtSource = new EventSource(url);

    // 💡 서버에서 yield 할 때마다 이 onmessage 함수가 자동으로 실행됩니다!
    evtSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        if (data.status === 'processing') {
            // 서버가 보내주는 진행 상황 텍스트를 그대로 화면에 표시
            loadingBox.innerText = `⏳ ${data.message}`;
        } 
        else if (data.status === 'success') {
            drawPolygons(data.results);
            loadingBox.style.display = 'none';
            evtSource.close(); // 🚀 작업이 끝났으므로 소켓(수신기)을 닫아줍니다!
        } 
        else if (data.status === 'error') {
            alert("SSE 추론 에러: " + data.message);
            loadingBox.style.display = 'none';
            evtSource.close(); // 에러 시에도 반드시 수신기를 닫아야 합니다.
        }
    };

    // 통신 오류 발생 시
    evtSource.onerror = function(err) {
        console.error("EventSource failed:", err);
        alert("SSE 연결이 끊어졌거나 서버에 문제가 발생했습니다.");
        loadingBox.style.display = 'none';
        evtSource.close();
    };
}

// ==========================================
// ⚡ 6. WebSocket 방식의 추론 요청 함수
// ==========================================
function runAutoInferenceWebSocket() {
    const loadingBox = document.getElementById('loadingBox');
    loadingBox.style.display = 'block';
    loadingBox.innerText = '웹소켓 연결 중... 🔌';

    // 💡 HTTP 주소가 아니라 ws:// 로 시작하는 주소를 만듭니다.
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const wsUrl = protocol + window.location.host + '/api/websocket/ws';
    
    // 소켓 객체 생성
    const ws = new WebSocket(wsUrl);

    // 1. 소켓 연결이 성공하면(onopen), 원하는 데이터를 서버로 보냄
    ws.onopen = function() {
        const payload = {
            "StudyUID": currentStudyUID || "",
            "SeriesUID": currentSeriesUID || "",
            "image_index": currentIdx,
            "ClassName": "Liver"
        };
        // JSON을 문자열로 바꿔서 전송
        ws.send(JSON.stringify(payload)); 
    };

    // 2. 서버가 데이터를 보낼 때마다(onmessage) 실행됩니다.
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        if (data.status === 'processing') {
            loadingBox.innerText = `⏳ ${data.message}`;
        } 
        else if (data.status === 'success') {
            drawPolygons(data.results);
            loadingBox.style.display = 'none';
            ws.close(); // 다 그렸으면 소켓 해제
        } 
        else if (data.status === 'error') {
            alert("WebSocket 추론 에러: " + data.message);
            loadingBox.style.display = 'none';
            ws.close();
        }
    };

    // 3. 통신 에러 발생 시
    ws.onerror = function(error) {
        console.error("WebSocket Error: ", error);
        alert("웹소켓 연결에 실패했습니다.");
        loadingBox.style.display = 'none';
    };
}

