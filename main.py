import os
import cv2
import numpy as np
import torch
import pydicom

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

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
models = {}

# Lifespan : 서버 켜질 때와 꺼질 때의 동작을 정의 (startup 대신)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("===== 서버 시작 =====")
    
    # 환경 변수에서 경로 가져오기
    base_dir = os.environ.get("nnUNet_results", "./weights")
    model_folder = os.path.join(base_dir, "Dataset001_Liver", "nnUNetTrainer__nnUNetPlans__2d")
    
    predictor = nnUNetPredictor(
        tile_step_size = 0.5,
        use_gaussian = True,
        use_mirroring = True,
        perform_everything_on_gpu = True,
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
    
    models["predictor"] = predictor
    print("===== 모델 로드 완료 =====")
    
    yield   # 서버가 정상적으로 동작 시작
    
    print("===== 서버 종료 =====")
    models.clear()
    

app = FastAPI(title="nnU-Net API", lifespan=lifespan)

# 요청 스키마
#✅ 입력 파라미터는 StudyUID, SeriesUID, image index, Class Name 4가지를 받도록 합니다.
class SegRequest(BaseModel):
    StudyUID: str
    SeriesUID: str
    image_index: int
    ClassName: str
    

# 유틸리티: 마스크를 Polyline으로 변환
def mask_to_polyline(mask: np.ndarray, z_index: int):
    # mask에서 외곽선 추출
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)   #❔❔❔
    
    polylines = []
    for cnt in contours:
        # [x, y, z] 형식의 리스트 생성 ( [532.5, 780.5, 0], [531.5, 781.5, 0], [528.5, 781.5, 0], ...)
        points = [[float(pt[0][0]), float(pt[0][1]), float(z_index)] for pt in cnt]
        polylines.append(points)
    return polylines

# z축 정렬 후 요청받은 슬라이스 로드
def load_dicom_slice(StudyUID: str, SeriesUID: str, image_index: int):
    base_dir = f"./local_data/{StudyUID}/{SeriesUID}"
    if not os.path.exists(base_dir):
        raise FileNotFoundError(f"DICOM 경로를 찾을 수 없습니다: {base_dir}")
    
    slice_info = []
    for filename in os.listdir(base_dir):
        filepath = os.path.join(base_dir, filename)
        try:
            dcm_meta = pydicom.dcmread(filepath, stop_before_pixels=True)
            if hasattr(dcm_meta, 'ImagePositionPatient'):
                z_pos = float(dcm_meta.ImagePositionPatient[2])
                slice_info.append((z_pos, filepath))
                
        except Exception:
            continue
    
    if not slice_info:
        raise ValueError("유효한 DICOM 파일이 없습니다.")
    
    # z축 기준으로 정렬
    slice_info.sort(key=lambda x: x[0])
    
    if image_index < 0 or image_index >= len(slice_info):
        raise IndexError(f"요청한 image_index({image_index})가 범위를 벗어났습니다. (총 {len(slice_info)}장)")
    
    target_filepath = slice_info[image_index][1]
    
    # 타겟 슬라이스 영상 데이터를 포함해 로드
    target_dcm = pydicom.dcmread(target_filepath)
    img = target_dcm.pixel_array.astype(np.float32)
    
    # ct의 경우 실제 밀도 값(HU)으로 복원
    intercept = getattr(target_dcm, 'RescaleIntercept', 0.0)
    slope = getattr(target_dcm, 'RescaleSlope', 1.0)
    img = img * slope + intercept
    
    # nnU-Net 2D 입력 형태 맞추기: [C, H, W]
    image_2d = img[np.newaxis, ...]
    
    # 2D Spacing 정보 추출 [Y Spacing, X Spacing]
    spacing_2d = [
        float(target_dcm.PixelSpacing[0]),
        float(target_dcm.PixelSpacing[1])
    ]
    
    return image_2d, spacing_2d, target_dcm



# API 엔드포인트
@app.post("/predict/segmentation")
async def predict_segmentation(req: SegRequest):
    try:
        # 모델 불러오기
        predictor = models.get("predictor")
        if not predictor:
            raise HTTPException(status_code=500, detail="모델이 아직 로드되지 않았습니다.")
        
        # 로컬 DICOM 로드 (실제 환경에서는 DICOM 파일들을 ImagePositionPatient[2] 기준으로 정렬하여 3D로 쌓아야 함)
        #✅ StudyUID, SeriesUID를 통해서 원래는 PACS에서 가져오지만, 현재는 로컬에서 해당 DICOM 파일을 가져옵니다.
        image_2d, spacing_2d, ref_dcm = load_dicom_slice(
            req.StudyUID, req.SeriesUID, req.image_index
        )
        
        # 2D 모델 추론 진행 (props에 2D spacing 전달)
        props = {'spacing': spacing_2d}
        segmentation = predictor.predict_from_numpy(
            image_2d,
            props=props,
            save_probabilities=False,
            num_processes_segmentation_export=1
        )
        
        target_mask = segmentation
        
        # 4. JSON 포맷팅
        #✅ Segmentation MASK는 Class Name에 맞춰 JSON 파일로 형식화 하여 저장합니다.
        polylines = mask_to_polyline(target_mask, req.image_index)
        
        annotations = []
        for poly in polylines:
            annotation_node = {
                "data": {
                    "label": req.ClassName,
                    "contour": {"closed":""}, # ❔❔❔ 이거 뭐임
                    "handles": {
                        "points": [],   # ❔❔❔
                        "textBox": {
                            "hasMoved": False,
                            "worldPosition": [0, 0, 0]
                        },
                    "activeHandleIndex": None
                    },
                    "polyline": poly,
                    "cachedStats": {}
                },
                "type": 1,
                "color": "#FF0000", #################
                "metadata": {
                    "toolName": "PlanarFreehandROI", ###########
                    "referenceImageId": f"/studies/{req.study_uid}/series/{req.series_uid}/instances/..." #########
                }
            }
            annotations.append(annotation_node)
            
        return {"status": "success", "results": annotations}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
if __name__ = "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)