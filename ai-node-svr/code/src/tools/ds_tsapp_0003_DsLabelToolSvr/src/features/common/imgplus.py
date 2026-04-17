import cv2
import dlib
import numpy as np
"""
公共函数-高级图像处理函数
"""



def find_facial_moles(image_path, threshold=120):
    """
    查找人脸图像中的痣
    
    参数:
    image_path (str): 图像文件的路径
    threshold (int): 用于二值化处理的阈值，默认值为120
    
    返回:
    list: 包含痣位置的坐标列表，每个元素为 (x, y) 元组
    """
    # 加载图像
    image = cv2.imread(image_path)
    if image is None:
        print("无法加载图像，请检查路径")
        return []
    
    # 转换为灰度图像
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 初始化人脸检测器和特征点检测器
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
    
    # 检测人脸
    faces = detector(gray)
    moles = []
    
    for face in faces:
        # 检测人脸特征点
        shape = predictor(gray, face)
        
        # 提取人脸区域
        x1, y1 = face.left(), face.top()
        x2, y2 = face.right(), face.bottom()
        face_roi = gray[y1:y2, x1:x2]
        
        # 图像预处理：高斯模糊
        blurred = cv2.GaussianBlur(face_roi, (5, 5), 0)
        
        # 二值化处理
        _, binary = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY_INV)
        
        # 查找轮廓
        contours, _ = cv2.findContours(binary.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 筛选可能的痣
        for contour in contours:
            # 计算轮廓的矩
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"]) + x1
                cY = int(M["m01"] / M["m00"]) + y1
                # 简单过滤，筛选小区域作为痣
                area = cv2.contourArea(contour)
                if 2 < area < 50:
                    moles.append((cX, cY))
    
    return moles
