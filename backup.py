import os
import cv2
import base64
import numpy as np
import pydicom
import shutil
import torch
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

# 💡 핵심: 분리해둔 뷰어 라우터를 가져옵니다.
from viewer_api import router as viewer_router

'''
https://github.com/MIC-DKFZ/nnUNet/blob/master/nnunetv2/inference/predict_from_raw_data.py
class nnUNetPredictor(object):
    def __init__(self,
                tile_step_size: float = 0.5,
                use_gaussian: bool = True,
                use_mirroring: bool = True,
                perform_everything_on_device: bool = True,
                device: torch.device = torch.device('cuda'),
                verbose: bool = False,
                verbose_preprocessing: bool = False,
                allow_tqdm: bool = True):
                
                
    def initialize_from_trained_model_folder(self, model_training_output_dir: str,
                                            use_folds: Union[Tuple[Union[int, str]], None],
                                            checkpoint_name: str = 'checkpoint_final.pth'):
        """
        This is used when making predictions with a trained model
        """
'''

# .env 파일에서 환경 변수 로드
load_dotenv()

# 모델을 저장할 딕셔너리
# models = {}

# Lifespan : 서버 켜질 때와 꺼질 때의 동작을 정의 (startup 대신)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("===== 서버 시작 [테스트] =====")
    
    app.state.models = {}
    
    # 환경 변수에서 경로 가져오기
    base_dir = os.environ.get("nnUNet_results", "./weights")
    model_folder = os.path.join(base_dir, "Dataset501_LiverLocal", "nnUNetTrainer__nnUNetPlans__2d")
    
    predictor = nnUNetPredictor(
        tile_step_size = 0.5,
        use_gaussian = True,
        use_mirroring = True,
        perform_everything_on_device = True,
        device = torch.device('cuda', 0),
        verbose = False,
        verbose_preprocessing = False,
        allow_tqdm = False
    )
    
    # 가중치 GPU에 올리기
    predictor.initialize_from_trained_model_folder(
        model_folder,
        use_folds = (0,),
        checkpoint_name = 'checkpoint_best.pth'
    )
    
    #-----------------------------------
    #   테스트 코드
    #-----------------------------------
    # # 1. 차원(Dimension) 확인: 2D인지 3D인지 확실하게 판별
    # patch_size = predictor.configuration_manager.patch_size
    # print(f"▶ 1. 패치 사이즈 (공간 차원): {patch_size} -> 공간 차원이 {len(patch_size)}개이므로 {len(patch_size)}D 모델입니다.")
    
    # # 2. 채널(Channel) 수 확인: 모달리티(CT, MRI 등)가 몇 개 들어와야 하는지
    # channels = predictor.dataset_json.get('channel_names', {})
    # num_channels = len(channels)
    # print(f"▶ 2. 필요 채널 수: {num_channels}개 (상세: {channels})")
    
    # # 종합 결론
    # expected_shape = [num_channels] + list(patch_size)
    # print(f"▶ 💡 최종 결론: 이 모델은 Numpy 배열이 {expected_shape} 형태(또는 이와 유사한 비율)로 들어오기를 기다리고 있습니다!")
    # print("="*40 + "\n")
    
    
    app.state.models["predictor"] = predictor
    #-----------------------------------
    #   테스트 코드
    #-----------------------------------
    # models["predictor"] = "DUMMY_MODE"
    
    print("===== 모델 로드 완료 =====")
    
    yield   # 서버가 정상적으로 동작 시작
    
    print("===== 서버 종료 =====")
    app.state.models.clear()
    

app = FastAPI(title="nnU-Net API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods={"*"}, allow_headers={"*"})

app.include_router(viewer_router)

# 💡 뷰어 UI 헬스체크용 엔드포인트 추가
@app.get("/health")
async def health():
    return {"status": "ok", "device": "cuda:0"}

# 요청 스키마
#✅ 입력 파라미터는 StudyUID, SeriesUID, image index, Class Name 4가지를 받도록 합니다.
class SegRequest(BaseModel):
    StudyUID: str
    SeriesUID: str
    image_index: int
    ClassName: str
    

@app.post("/predict/segmentation")
async def predict_segmentation(req: SegRequest):
    # 여기에 원래 지영님이 작성하셨던 UID 기반 핵심 로직이 들어갑니다.
    return {"status": "success", "message": "Core API is running."}



# # 유틸리티: 마스크를 Polyline으로 변환
# def mask_to_polyline(mask: np.ndarray, z_index: int):
#     # mask에서 외곽선 추출
#     contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)   #❔❔❔
    
#     polylines = []
#     for cnt in contours:
#         # [x, y, z] 형식의 리스트 생성 ( [532.5, 780.5, 0], [531.5, 781.5, 0], [528.5, 781.5, 0], ...)
#         points = [[float(pt[0][0]), float(pt[0][1]), float(z_index)] for pt in cnt]
#         polylines.append(points)
#     return polylines






# # z축 정렬 후 요청받은 슬라이스 로드
# def load_dicom_slice(StudyUID: str, SeriesUID: str, image_index: int):
#     base_dir = f"./local_data/{StudyUID}/{SeriesUID}"
#     if not os.path.exists(base_dir):
#         raise FileNotFoundError(f"DICOM 경로를 찾을 수 없습니다: {base_dir}")
    
#     slice_info = []
#     for filename in os.listdir(base_dir):
#         filepath = os.path.join(base_dir, filename)
#         try:
#             dcm_meta = pydicom.dcmread(filepath, stop_before_pixels=True)
#             if hasattr(dcm_meta, 'ImagePositionPatient'):
#                 z_pos = float(dcm_meta.ImagePositionPatient[2])
#                 slice_info.append((z_pos, filepath))
                
#         except Exception:
#             continue
    
#     if not slice_info:
#         raise ValueError("유효한 DICOM 파일이 없습니다.")
    
#     # z축 기준으로 정렬
#     slice_info.sort(key=lambda x: x[0])
    
#     if image_index < 0 or image_index >= len(slice_info):
#         raise IndexError(f"요청한 image_index({image_index})가 범위를 벗어났습니다. (총 {len(slice_info)}장)")
    
#     target_filepath = slice_info[image_index][1]
    
#     # 타겟 슬라이스 영상 데이터를 포함해 로드
#     target_dcm = pydicom.dcmread(target_filepath)
#     img = target_dcm.pixel_array.astype(np.float32)
    
#     # ct의 경우 실제 밀도 값(HU)으로 복원
#     intercept = getattr(target_dcm, 'RescaleIntercept', 0.0)
#     slope = getattr(target_dcm, 'RescaleSlope', 1.0)
#     img = img * slope + intercept
    
#     # nnU-Net 2D 입력 형태 맞추기: [C, H, W]
#     image_3d_box = img[np.newaxis, np.newaxis, ...]
    
#     # 2D Spacing 정보 추출 [Y Spacing, X Spacing]
#     spacing_3d = [
#         999.0,
#         float(target_dcm.PixelSpacing[0]),
#         float(target_dcm.PixelSpacing[1])
#     ]
    
#     return image_3d_box, spacing_3d, target_dcm



# # API 엔드포인트
@app.post("/predict/segmentation")
async def predict_segmentation(req: SegRequest, request: Request):
    try:
        # 1. 상태 저장소에서 모델 가져오기
        predictor = request.app.state.models.get("predictor")
        if not predictor:
            raise HTTPException(status_code=500, detail="모델이 로드되지 않았습니다.")

        # 2. 기존 로컬 DICOM 로드 로직 (load_dicom_slice 함수가 main.py 상단에 있어야 합니다)
        image_3d_box, spacing_3d, ref_dcm = load_dicom_slice(
            req.StudyUID, req.SeriesUID, req.image_index
        )
        
        props = {'spacing': spacing_3d}
        
        # 3. 모델 추론
        if predictor == "DUMMY_MODE":
            h, w = image_3d_box.shape[2], image_3d_box.shape[3]
            target_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(target_mask, (w//2, h//2), 100, 1, -1)
            cv2.circle(target_mask, (w//2 + 40, h//2 - 40), 30, 2, -1)
        else:
            segmentation = predictor.predict_from_list_of_npy_arrays(
                [image_3d_box], None, [props], None, 1, save_probabilities=False, num_processes_segmentation_export=1
            )
            target_mask = segmentation[0][0]
        
        ##-----------------------------------
        ##  테스트 코드
        ##-----------------------------------
        # h, w = image_2d.shape[1], image_2d.shape[2]
        # target_mask = np.zeros((h, w), dtype=np.uint8)
        # cv2.circle(target_mask, (w//2, h//2), 50, 1, -1)
        
        # # ==========================================
        # # 🛠️ [더미 테스트 코드] 가짜 다중 클래스 마스크 생성
        # # ==========================================
        # # 1. 원본 이미지와 똑같은 크기의 빈 까만 도화지(0)를 만듭니다.
        # h, w = image_3d_box.shape[2], image_3d_box.shape[3]
        # dummy_mask = np.zeros((h, w), dtype=np.uint8)

        # # 2. 간(Liver, 라벨 1) 생성: 정중앙에 반지름 100짜리 큰 원을 그립니다.
        # cv2.circle(dummy_mask, (w//2, h//2), 100, 1, -1)

        # # 3. 종양(HCC, 라벨 2): 간 내부 우측 상단에 반지름 30짜리 작은 원을 그립니다.
        # cv2.circle(dummy_mask, (w//2 + 40, h//2 - 40), 30, 2, -1)

        # # 4. 가짜 도화지를 파이프라인에 넘겨줍니다!
        # target_mask = dummy_mask
        
        
        # 4. JSON 포맷팅
        #✅ Segmentation MASK는 Class Name에 맞춰 JSON 파일로 형식화 하여 저장합니다.
        # polylines = mask_to_polyline(target_mask, req.image_index)
        
        CLASS_MAP = {
            1: {"name": "Liver", "color": "#FF0000"},
            2: {"name": "HCC", "color": "#00FF00"}
        }
        
        annotations = []
        InstanceUID = os.path.basename(ref_dcm.filename)
        
        for class_idx, class_info in CLASS_MAP.items():
            binary_mask = (target_mask == class_idx).astype(np.uint8)
            if not np.any(binary_mask):
                continue
                
            polylines = mask_to_polyline(binary_mask, req.image_index)
            for poly in polylines:
                annotations.append({
                    "data": {
                        "label": class_info["name"],
                        "contour": {"closed": True},
                        "handles": {
                            "points": [],
                            "textBox": {"hasMoved": False, "worldPosition": [0, 0, 0]},
                            "activeHandleIndex": None
                        },
                        "polyline": poly,
                        "cachedStats": {}
                    },
                    "type": 1,
                    "color": class_info["color"],
                    "metadata": {
                        "toolName": "PlanarFreehandROI",
                        "referenceImageId": f"/local_data/{req.StudyUID}/{req.SeriesUID}/{InstanceUID}"
                    }
                })
                
        return {"status": "success", "results": annotations}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    
if os.path.exists("app/static"):
    app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
elif os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)