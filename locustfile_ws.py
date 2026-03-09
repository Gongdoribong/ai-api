import json
import time
from locust import User, task, events
import websocket

class TrueWebSocketUser(User):
    study_uid = "31867493"
    series_uid = "20141111"
    image_index = 93 

    def on_start(self):
        """가상 유저가 처음 생성될 때(방에 입장할 때) 딱 한 번만 실행됩니다."""
        ws_url = "ws://127.0.0.1:8000/api/websocket/ws"
        # 1. 여기서 소켓 연결을 맺고 방을 파둡니다.
        self.ws = websocket.create_connection(ws_url)

    def on_stop(self):
        """가상 유저가 테스트를 마치고 소멸할 때 실행됩니다."""
        # 3. 테스트가 끝나면 방을 나갑니다.
        self.ws.close()

    @task
    def continuous_inference(self):
        """방에 들어온 상태에서 10번 연속으로 데이터를 던지고 받습니다."""
        for i in range(10):
            start_time = time.time()
            try:
                payload = {
                    "StudyUID": self.study_uid,
                    "SeriesUID": self.series_uid,
                    "image_index": self.image_index,
                    "ClassName": "Liver"
                }
                # 2. 이미 연결된 통로(self.ws)로 텍스트만 휙 던집니다!
                self.ws.send(json.dumps(payload))
                
                # 결과 수신 대기
                while True:
                    result = self.ws.recv()
                    data = json.loads(result)
                    
                    if data.get("status") == "success":
                        total_time = int((time.time() - start_time) * 1000)
                        events.request.fire(
                            request_type="True_WS",
                            name="10_Continuous_Inference",
                            response_time=total_time,
                            response_length=len(result),
                            exception=None,
                        )
                        break
                    elif data.get("status") == "error":
                        total_time = int((time.time() - start_time) * 1000)
                        events.request.fire(
                            request_type="True_WS",
                            name="10_Continuous_Inference",
                            response_time=total_time,
                            response_length=len(result),
                            exception=Exception(data.get("message")),
                        )
                        break
                        
            except Exception as e:
                total_time = int((time.time() - start_time) * 1000)
                events.request.fire(
                    request_type="True_WS",
                    name="10_Continuous_Inference",
                    response_time=total_time,
                    response_length=0,
                    exception=e,
                )
        
        self.environment.runner.quit()