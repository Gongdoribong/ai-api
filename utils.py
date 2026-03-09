import os
import cv2
import base64
import numpy as np
import pydicom
import shutil
import torch

def mask_to_polyline(mask: np.ndarray, z_index: int = 0):
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polylines = []
    for cnt in contours:
        points = [[float(pt[0][0]), float(pt[0][1]), float(z_index)] for pt in cnt]
        polylines.append(points)
    return polylines

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
                slice_info.append((z_pos,filepath))
                
        except Exception:
            continue
        
    if not slice_info: raise ValueError("유효한 DICOM 파일이 없습니다.")
    slice_info.sort(key=lambda x: x[0])
    
    if image_index < 0 or image_index >= len(slice_info):
        raise IndexError(f"요청한 image_index({image_index})가 범위를 벗어났습니다. (총 {len(slice_info)}장)")
    
    target_filepath = slice_info[image_index][1]
    target_dcm = pydicom.dcmread(target_filepath)
    img = target_dcm.pixel_array.astype(np.float32)
    
    intercept = getattr(target_dcm, 'RescaleIntercept', 0.0)
    slope = getattr(target_dcm, 'RescaleSlope', 1.0)
    img = img * slope + intercept
    
    image_3d_box = img[np.newaxis, np.newaxis, ...]
    spacing_3d = [999.0, float(target_dcm.PixelSpacing[0]), float(target_dcm.PixelSpacing[1])]
    
    return image_3d_box, spacing_3d, target_dcm