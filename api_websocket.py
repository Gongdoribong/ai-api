# api_websocket.py
import os
import cv2
import numpy as np
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from utils import load_dicom_slice, mask_to_polyline

router = APIRouter(prefix="/api/websocket", tags=["WebSockets"])

@router.websocket("/ws")
async def websocket_inference(websocket: WebSocket):
    await websocket.accept()
    
    try:
        # 클라이언트가 나갈 때까지 방을 유지 (while True)
        while True:
            # 2. 클라이언트가 보내는 JSON 데이터를 기다립니다.
            data = await websocket.receive_json()
            
            StudyUID = data.get("StudyUID", "")
            SeriesUID = data.get("SeriesUID", "")
            image_index = data.get("image_index", 0)
            ClassName = data.get("ClassName", "All")
            
            predictor = websocket.app.state.models.get("predictor")
            
            await websocket.send_json({"status": "processing", "message": "1/3: 데이터 로드 중..."})
            await asyncio.sleep(0.2)
            
            image_3d_box, spacing_3d, ref_dcm = load_dicom_slice(StudyUID, SeriesUID, image_index)
            props = {'spacing': spacing_3d}
            
            await websocket.send_json({"status": "processing", "message": "2/3: AI 모델 추론 중 ..."})
            
            if predictor == "DUMMY_MODE":
                await asyncio.sleep(2)
                h, w = image_3d_box.shape[2], image_3d_box.shape[3]
                target_mask = np.zeros((h, w), dtype=np.uint8)
                cv2.circle(target_mask, (w//2, h//2), 100, 1, -1)
                cv2.circle(target_mask, (w//2 + 40, h//2 - 40), 30, 2, -1)
            else:
                segmentation = predictor.predict_from_list_of_npy_arrays(
                    [image_3d_box], None, [props], None, 1, save_probabilities=False, num_processes_segmentation_export=1
                )
                target_mask = segmentation[0][0]

            await websocket.send_json({"status": "processing", "message": "3/3: 폴리라인 좌표 추출 중..."})
            
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

            await websocket.send_json({"status": "success", "results": annotations})
        
    except WebSocketDisconnect:
        print("클라이언트가 소켓 연결을 끊었습니다.")
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass