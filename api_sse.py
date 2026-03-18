# api_sse.py
import os
import cv2
import numpy as np
import asyncio
import json

from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from utils import load_dicom_slice, mask_to_polyline

router = APIRouter(prefix="/api/sse", tags=["Server-Sent Events"])

async def inference_event_generator(StudyUID: str, SeriesUID: str, image_index: int, ClassName: str, predictor):
    try:
        #yield f"data: {json.dumps({'status': 'processing', 'message': '1/3: DICOM 데이터 로드 중...'})}\n\n"
        
        image_3d_box, spacing_3d, ref_dcm = load_dicom_slice(StudyUID, SeriesUID, image_index)
        props = {'spacing': spacing_3d}
        
        #yield f"data: {json.dumps({'status': 'processing', 'message': '2/3: AI 모델 추론 중...'})}\n\n"
        
        segmentation = predictor.predict_from_list_of_npy_arrays(
            [image_3d_box], None, [props], None, 1, save_probabilities=False, num_processes_segmentation_export=1
        )
        target_mask = segmentation[0][0]

        #yield f"data: {json.dumps({'status': 'processing', 'message': '3/3: 폴리라인 좌표 추출 중...'})}\n\n"

        CLASS_MAP = {1: {"name": "Liver", "color": "#FF0000"}, 2: {"name": "HCC", "color": "#00FF00"}}
        annotations = []
        InstanceUID = os.path.basename(ref_dcm.filename)
        
        for class_idx, class_info in CLASS_MAP.items():
            if ClassName != "All" and class_info["name"] != ClassName:
                continue
                
            binary_mask = (target_mask == class_idx).astype(np.uint8)
            if not np.any(binary_mask): continue
            
            polylines = mask_to_polyline(binary_mask, image_index)
            for poly in polylines:
                annotations.append({
                    "data": {"label": class_info["name"], "contour": {"closed": True}, "polyline": poly},
                    "type": 1, "color": class_info["color"],
                    "metadata": {"toolName": "PlanarFreehandROI", "referenceImageId": InstanceUID}
                })

        yield f"data: {json.dumps({'status': 'success', 'results': annotations})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"


@router.get("/stream")
async def sse_inference_stream(
    request: Request,
    StudyUID: str = Query(..., description="환자 ID"),
    SeriesUID: str = Query(..., description="시리즈 ID"),
    image_index: int = Query(..., description="이미지 인덱스"),
    ClassName: str = Query(..., description="클래스 이름")
):
    predictor = request.app.state.models.get("predictor")
    
    return StreamingResponse(
        inference_event_generator(StudyUID, SeriesUID, image_index, ClassName, predictor),
        media_type="text/event-stream"
    )