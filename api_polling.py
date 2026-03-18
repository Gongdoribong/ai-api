# api_polling.py
import uuid
import os
import cv2
import numpy as np
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from utils import load_dicom_slice, mask_to_polyline

# 라우터 생성 (주소가 /api/polling 으로 시작하게 됩니다)
router = APIRouter(prefix="/api/polling", tags=["Task Queue Polling"])

# Task ID와 작업 상태를 임시로 보관할 메모리 딕셔너리
TASKS = {}

class SegRequest(BaseModel):
    StudyUID: str
    SeriesUID: str
    image_index: int
    ClassName: str

def process_inference(task_id: str, req: SegRequest, predictor):
    """AI 추론 담당"""
    try:
        TASKS[task_id]["status"] = "processing"
        
        image_3d_box, spacing_3d, ref_dcm = load_dicom_slice(req.StudyUID, req.SeriesUID, req.image_index)
        props = {'spacing': spacing_3d}
        
        segmentation = predictor.predict_from_list_of_npy_arrays(
            [image_3d_box], None, [props], None, 1, save_probabilities=False, num_processes_segmentation_export=1
        )
        target_mask = segmentation[0][0]

        CLASS_MAP = {1: {"name": "Liver", "color": "#FF0000"}, 2: {"name": "HCC", "color": "#00FF00"}}
        annotations = []
        InstanceUID = os.path.basename(ref_dcm.filename)
        
        for class_idx, class_info in CLASS_MAP.items():
            if req.ClassName != "All" and class_info["name"] != req.ClassName:
                continue
                
            binary_mask = (target_mask == class_idx).astype(np.uint8)
            if not np.any(binary_mask): continue
            
            polylines = mask_to_polyline(binary_mask, req.image_index)
            for poly in polylines:
                annotations.append({
                    "data": {"label": class_info["name"], "contour": {"closed": True}, "polyline": poly},
                    "type": 1, "color": class_info["color"],
                    "metadata": {"toolName": "PlanarFreehandROI", "referenceImageId": InstanceUID}
                })
        
        TASKS[task_id]["status"] = "success"
        TASKS[task_id]["results"] = annotations

    except Exception as e:
        TASKS[task_id]["status"] = "error"
        TASKS[task_id]["message"] = str(e)


@router.post("/submit")
async def submit_task(req: SegRequest, request: Request, background_tasks: BackgroundTasks):
    predictor = request.app.state.models.get("predictor")
    if not predictor:
        raise HTTPException(status_code=500, detail="모델이 로드되지 않았습니다.")

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "pending"}

    background_tasks.add_task(process_inference, task_id, req, predictor)
    return {"task_id": task_id, "status": "pending"}


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="존재하지 않는 작업 번호입니다.")
    return task