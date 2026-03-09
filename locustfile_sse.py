# locustfile_sse.py
import json
from locust import HttpUser, task, constant

class SSEUser(HttpUser):
    # 폴링 때와 똑같이 다음 추론 전까지 2초 대기
    wait_time = constant(2)

    @task
    def test_sse_inference(self):
        study_uid = "31867493"
        series_uid = "20141111"
        
        # SSE는 GET 방식이므로 URL에 파라미터를 담습니다. (ClassName=Liver 포함)
        url = f"/api/sse/stream?StudyUID={study_uid}&SeriesUID={series_uid}&image_index=93&ClassName=Liver"

        # SSE 스트리밍 데이터를 받기 위해 stream=True 옵션을 켭니다.
        with self.client.get(url, stream=True, name="/api/sse/stream", catch_response=True) as res:
            if res.status_code != 200:
                res.failure(f"SSE 연결 실패: {res.status_code}")
                return

            try:
                # 서버가 보내는 이벤트(줄)를 실시간으로 하나씩 읽어 들입니다.
                for line in res.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        # 'data: ' 로 시작하는 SSE 규격 메시지만 파싱
                        if decoded_line.startswith("data: "):
                            data_str = decoded_line[6:] 
                            data = json.loads(data_str)

                            # 4단계 최종 결과를 받으면 성공 처리하고 스트림을 끊음
                            if data.get("status") == "success":
                                res.success()
                                break 
                            elif data.get("status") == "error":
                                res.failure(f"SSE 서버 내부 에러: {data.get('message')}")
                                break
                                
            except Exception as e:
                res.failure(f"스트림 읽기 실패: {str(e)}")