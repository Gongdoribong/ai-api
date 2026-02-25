import os
import requests
import pydicom
import matplotlib.pyplot as plt

# ==========================================
# 1. API 서버에 예측 요청 보내기
# ==========================================
API_URL = "http://127.0.0.1:8000/predict/segmentation"
REQUEST_PAYLOAD = {
  "StudyUID": "31867493",
  "SeriesUID": "20141111",
  "image_index": 86,
  "ClassName": "Liver"
}

print("🚀 API 서버에 Segmentation 요청 중...")
response = requests.post(API_URL, json=REQUEST_PAYLOAD)

if response.status_code == 200 and response.json().get("status") == "success":
    results = response.json()["results"]
    
    if not results:
        print("⚠️ 해당 슬라이스에는 예측된 마스크(간)가 없습니다.")
        exit()

    # ==========================================
    # 2. API 응답에서 원본 DICOM 경로 자동 추출
    # ==========================================
    # 서버가 보내준 "/local_data/..." 경로 앞에 점(.)을 붙여 상대 경로로 만듭니다.
    ref_image_id = results[0]["metadata"]["referenceImageId"]
    dicom_file_path = "." + ref_image_id 
    
    print(f"✅ 타겟 DICOM 파일 자동 확인: {dicom_file_path}")

    if not os.path.exists(dicom_file_path):
        print(f"❌ 해당 위치에 DICOM 파일이 없습니다: {dicom_file_path}")
        exit()

    # ==========================================
    # 3. 원본 이미지 로드 및 시각화
    # ==========================================
    dcm = pydicom.dcmread(dicom_file_path)
    image = dcm.pixel_array

    plt.figure(figsize=(8, 8))
    plt.imshow(image, cmap='gray')
    
    for ann in results:
        polyline = ann["data"]["polyline"]
        if not polyline:
            continue
            
        # polyline은 [x, y, z] 형태이므로 화면에 그릴 x와 y만 추출
        xs = [point[0] for point in polyline]
        ys = [point[1] for point in polyline]
        
        # 다각형 선이 닫히도록 마지막 점과 첫 번째 점을 연결
        xs.append(xs[0])
        ys.append(ys[0])
        
        # ==========================================
        # 💡 수정: 서버가 보내준 고유 색상을 추출 (기본값은 빨간색)
        # ==========================================
        target_color = ann.get("color", "#FF0000")
        
        # 💡 수정: color='red' 대신 추출한 target_color 변수를 넣습니다!
        plt.plot(xs, ys, color=target_color, linewidth=2, label=ann["data"]["label"])
    
    # 제목에 슬라이스 인덱스와 추출해온 파일명 표시
    filename = os.path.basename(dicom_file_path)
    plt.title(f"nnU-Net 2D Result (Index: {REQUEST_PAYLOAD['image_index']})\nFile: {filename}")
    
    # 범례 깔끔하게 표시
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys())
    
    plt.axis('off') # 축 눈금 숨기기
    plt.show()

else:
    print("❌ API 에러 발생:", response.text)