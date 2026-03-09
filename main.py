import os
import cv2
import base64
import numpy as np
import pydicom
import shutil
import torch

from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

from utils import mask_to_polyline, load_dicom_slice
from api_polling import router as polling_router
from api_sse import router as sse_router
from api_websocket import router as ws_router

# .env 파일에서 환경 변수 로드
load_dotenv()

# 전역 상태 저장 : UI 뷰어에서 파일 인덱스를 추적하기 위한 상태
dataset_state = {"files": [], "current_idx": 0}



# 서버 Lifespan: nnU-Net 모델 로드
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("==== 서버 시작 ====")
    
    app.state.models = {}
    base_dir = os.environ.get("nnUNet_results", "./weights")
    model_folder = os.path.join(base_dir, "Dataset501_LiverLocal", "nnUNetTrainer__nnUNetPlans__2d")
    
    # 모델 인스턴스화
    predictor = nnUNetPredictor(
        tile_step_size= 0.5,
        use_gaussian= True,
        use_mirroring= True,
        perform_everything_on_device= True,
        device= torch.device('cuda', 0),
        verbose= False,
        verbose_preprocessing= False,
        allow_tqdm= False
    )
    
    # 가중치 로드
    predictor.initialize_from_trained_model_folder(model_folder, use_folds=(0,), checkpoint_name='checkpoint_best.pth')
    
    app.state.models["predictor"] = predictor
    # app.state.models["predictor"] = "DUMMY_MODE"
    
    print("==== 모델 로드 완료 ====")
    
    yield
    
    print("==== 서버 종료 ====")
    
    app.state.models.clear()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    
app = FastAPI(title="nnU-Net API & Viewer", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(polling_router)
app.include_router(sse_router)
app.include_router(ws_router)


# 뷰어 UI 지원 API: 파일 전송 및 조회
@app.get("/health")
async def health():
    return {"status": "ok", "device": "cuda:0"}




@app.post("/api/upload_folder")
async def upload_folder(files: List[UploadFile] = File(...)):
    slice_info_list = []
    study_uid = "unknown_study"
    series_uid = "unknown_series"
    
    for file in files:
        temp_path = f"./temp_{file.filename}"
        
        # [[ 문제 ]]
        # " 파일 업로드 중 서버와 통신할 수 없습니다."
        #
        # [[ 설명 ]]
        # HTML5의 폴더 선택기(webkitdirectory)는 서버로 파일을 보낼 때,
        # 자신이 속해 있던 폴더 이름까지 포함된 경로(20141111/IN...dcm)를 통째로 file.filename에 담아서 보냄
        # 파일 이름에 20141111/이 섞여 들어오다 보니, 임시 파일 경로를 만드는
        # f"./temp_{file.filename}" 로직이 오작동하여 ./temp_20141111/라는 하위 폴더에 파일을 쓰려고 시도하다가 서버가 뻗음
        # 
        # [[ 해결책 ]]
        # 파일을 저장(open)하기 직전에, 파일이 들어갈 부모 폴더 경로를 먼저 생성
        # 

        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        try:
            ds = pydicom.dcmread(temp_path, stop_before_pixels=True)
            if hasattr(ds, 'StudyInstanceUID'): study_uid = str(ds.StudyInstanceUID)
            if hasattr(ds, 'SeriesInstanceUID'): series_uid = str(ds.SeriesInstanceUID)
            
            z_pos = float(ds.ImagePositionPatient[2]) if hasattr(ds, 'ImagePositionPatient') else 0.0
            
            final_dir = f"./local_data/{study_uid}/{series_uid}"
            os.makedirs(final_dir, exist_ok=True)
            
            filename = os.path.basename(file.filename)
            final_path = os.path.join(final_dir, filename)
            
            shutil.move(temp_path, final_path)
            slice_info_list.append((z_pos, final_path))
            
        except Exception as e:
            print(f"❌ 파일 처리 실패 ({file.filename}): {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
    slice_info_list.sort(key=lambda x: x[0])
    
    saved_files = [item[1] for item in slice_info_list]
    dataset_state["files"] = saved_files
    
    # 프론트앤드가 이 UID를 받아 /predict/segmentation에 사용
    return {"count": len(saved_files), "StudyUID": study_uid, "SeriesUID": series_uid}



@app.get("/api/image/{idx}")
async def get_image(idx: int):
    fpath = dataset_state["files"][idx]
    if fpath.lower().endswith(".dcm"):
        ds = pydicom.dcmread(fpath)
        img = ds.pixel_array
        img = ((img - img.min()) / (img.max() - img.min()) * 255).astype(np.uint8)
        if len(img.shape)==2: img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
    else:
        img = cv2.imdecode(np.fromfile(fpath, np.uint8), cv2.IMREAD_COLOR)
        
    _, buf = cv2.imencode('.png', img)
    return {"image": base64.b64encode(buf).decode('utf-8'), "width": img.shape[1], "height": img.shape[0], "index": idx}


# 모델 추론 API
class SegRequest(BaseModel):
    StudyUID: str
    SeriesUID: str
    image_index: int
    ClassName: str
    

@app.post("/predict/segmentation")
async def predict_segmentation(req: SegRequest, request: Request):
    try:
        predictor = request.app.state.models.get("predictor")
        if not predictor:
            raise HTTPException(status_code=500, detail="모델이 로드되지 않았습니다.")
        
        # DICOM 로드
        image_3d_box, spacing_3d, ref_dcm = load_dicom_slice(req.StudyUID, req.SeriesUID, req.image_index)
        props = {'spacing': spacing_3d}
        
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
            # # ==========================================
            # # 💡 [디버깅] 모델이 도화지에 무슨 색을 칠했는지 확인!
            # # ==========================================
            # unique_values = np.unique(target_mask)
            # print(f"▶ 🤖 AI 예측 결과 (픽셀 고유값): {unique_values}")
            # if len(unique_values) == 1 and unique_values[0] == 0:
            #     print("▶ 텅 빈 도화지입니다. (간/종양을 찾지 못함)")
            
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
    


# 정적 파일
if os.path.exists("app/static"):
    app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
elif os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)