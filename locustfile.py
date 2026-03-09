# locustfile.py
import time
from locust import HttpUser, task, constant

class PollingUser(HttpUser):
    # 💡 모든 가상 사용자가 이전 추론이 끝나면 '정확히 2초' 대기 후 다음 추론을 요청합니다.
    wait_time = constant(2)

    @task
    def test_polling_inference(self):
        payload = {
            "StudyUID": "31867493",
            "SeriesUID": "20141111",
            "image_index": 93,
            "ClassName": "Liver"
        }

        # 1단계: Task ID 발급 요청
        with self.client.post("/api/polling/submit", json=payload, catch_response=True) as res:
            if res.status_code != 200:
                res.failure(f"Submit 에러: {res.status_code}")
                return
            task_id = res.json().get("task_id")

        # 2단계: 상태 확인 (프론트엔드의 1초 간격 setInterval 완벽 모사)
        while True:
            with self.client.get(f"/api/polling/status/{task_id}", name="/api/polling/status/[task_id]", catch_response=True) as status_res:
                if status_res.status_code == 200:
                    data = status_res.json()
                    
                    if data.get("status") == "success":
                        status_res.success()
                        break 
                    elif data.get("status") == "error":
                        status_res.failure("백그라운드 에러")
                        break
            
            time.sleep(1) # 프론트엔드와 동일하게 1초 대기