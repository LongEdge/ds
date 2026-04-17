"""
公共函数-基础图像处理函数
"""

import os
import whatimage
import pyheif
import shutil
import cv2
import numpy as np
import io
import json
from PIL import Image

def imagetobase64(self, image_path):
    """
    将图片文件转换为base64编码字符串
    :param image_path: 图片文件路径（支持绝对路径和相对路径）
    :return: base64编码字符串（转换失败返回空字符串）
    """
    if not image_path:
        print("错误：图片路径不能为空")
        return ""

    # 处理相对路径
    if not os.path.isabs(image_path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(current_dir, image_path)

    # 检查文件是否存在
    if not os.path.exists(image_path):
        print(f"错误：图片文件不存在 - {image_path}")
        return ""

    # 检查是否为文件
    if not os.path.isfile(image_path):
        print(f"错误：路径不是文件 - {image_path}")
        return ""

    try:
        # 读取图片文件并转换为base64
        with open(image_path, 'rb') as img_file:
            # 读取文件内容并进行base64编码
            base64_data = base64.b64encode(img_file.read())
            # 转换为字符串并返回
            return base64_data.decode('utf-8')
    except Exception as e:
        print(f"图片转换失败: {str(e)}")
        return ""  

"""
heic2jpg转换 把source目录下的所有heic转换成jpg
"""
def heic2jpg(source, destination):
    # TODO: 如果jpg存在了, 就别转了
    """
    params: source          "<report_id>"目录
    params: destination     "<report_id>"目录
    """

    onlyfiles =[f for f in os.listdir(source) if os.path.isfile(os.path.join(source, f))]
    if not os.path.exists(destination):
        os.makedirs(destination)
    else:
        print("Output dir already exists")
    for file in onlyfiles:
        (name, ext) = os.path.basename(file).split('.')
        if ext == 'heic' or ext == 'HEIC':
            dest = os.path.join(destination, name) + '.jpg'
            sour= os.path.join(source, file)
            f=open(sour,"rb")
            bytesIo=f.read()
            fmt = whatimage.identify_image(bytesIo)
            print("fmt: ", fmt)
            if fmt in ['heic', 'avif']:
                try:
                    i = pyheif.read_heif(bytesIo)
                except pyheif.error.HeifError as e:
                    #raise TypeError from e
                    print("heic 2 jpg error")
            # Extract metadata etc
                for metadata in i.metadata or []:
                    if metadata['type']=='Exif':
                        # do whatever
                        print("EXif")
                # Convert to other file format like jpeg
                s = io.BytesIO()
                print("i.mode: ", i.mode)
                pi = Image.frombytes(
                        mode=i.mode, size=i.size, data=i.data)
                pi1 = pi.convert("RGB")
                pi1.save(dest,quality=95)
            elif fmt == 'jpeg':
                dest = os.path.join(destination, name) + '.jpg'
                sour= os.path.join(source, file)
                shutil.copyfile(sour,dest)
        elif ext == 'jpg' or ext == 'jpeg':
            dest = os.path.join(destination, name) + '.jpg'
            sour= os.path.join(source, file)
            shutil.copyfile(sour,dest)

# 给人脸图像的眼睛部分盖上椭圆形的黑色块，用于眼睛脱敏
def drawImgCoverEys(img,points):
    """
    @params:
        img: 输入图像
        points: 68个点的二维坐标
    """
    # 左右眼关键点列表
    eye_points_list = [
        [points[45], points[47], points[49], points[46], points[50], points[48]],  # 左眼
        [points[51], points[53], points[55], points[52], points[56], points[54]]   # 右眼
    ]
     # 放大比例
    width_scale = 1.5   # 控制宽度（长轴）
    height_scale = 4  # 控制高度（短轴）

    print("width_scale: ", width_scale)
    print("height_scale: ", height_scale)

    for eye_points in eye_points_list:
        eye_points = np.array(eye_points, dtype=np.float32)

        # 计算几何中心
        center = np.mean(eye_points, axis=0)
        

        # 估算宽高：计算所有点的x、y范围
        xs = eye_points[:, 0]
        ys = eye_points[:, 1]

        width = (np.max(xs) - np.min(xs)) * width_scale
        height = (np.max(ys) - np.min(ys)) * height_scale

        print(width)
        print(height)

        # 椭圆参数：(中心坐标)、(宽、高)、角度
        ellipse = (tuple(center), (width, height), 0)

        # 画椭圆
        cv2.ellipse(img, ellipse, (0, 0, 0), -1)

    return img

def eyes_masking(img_names, img, point_path):
    # 读取图片
    # 假设你有68个关键点，示例格式如下：
    # points = [[x1, y1], [x2, y2], ..., [x68, y68]]
    # 你需要替换成你实际的68点坐标
    with open(point_path, 'r', encoding='utf-8') as f:
        data = json.loads(f.read())
    points = np.array(data)
    # 左右眼关键点列表
    eye_points_list = [
        [points[45], points[47], points[49], points[46], points[50], points[48]],  # 左眼
        [points[51], points[53], points[55], points[52], points[56], points[54]]   # 右眼
    ]

    print("img_names: ", img_names)
    # 放大比例
    width_scale = 1.5   # 控制宽度（长轴）
    height_scale = 4  # 控制高度（短轴）

    print("width_scale: ", width_scale)
    print("height_scale: ", height_scale)
    
    for eye_points in eye_points_list:
        eye_points = np.array(eye_points, dtype=np.float32)

        # 计算几何中心
        center = np.mean(eye_points, axis=0)
        

        # 估算宽高：计算所有点的x、y范围
        xs = eye_points[:, 0]
        ys = eye_points[:, 1]

        width = (np.max(xs) - np.min(xs)) * width_scale
        height = (np.max(ys) - np.min(ys)) * height_scale

        print(width)
        print(height)

        # 椭圆参数：(中心坐标)、(宽、高)、角度
        ellipse = (tuple(center), (width, height), 0)

        # 画椭圆
        cv2.ellipse(img, ellipse, (0, 0, 0), -1)

    return img
"""
加载矢量五官点-1
"""
def loadVector(report_id, direction):
    """
    @res:
        result_face: True/False
        points: 二维数组
        lm: 格式化的点
    """
    detector = FaceDetectorDelib()
    result_face = False
    lm = []
    points = []
    try:
        with open("{}/vector/{}.txt".format(report_id, direction), 'r') as f:
            points = json.load(f)
        if 0 != len(points):
            result_face = True
        lm = detector.formatDlib(points)
    except Exception as e:
        print("linux下矢量文件{}结果为空! --{}".format(direction, e))
    return result_face, lm, points

# 将多个二值掩码图像合并成一个掩码图像。
def combineMasks(maskImgs):
    """
    将多个二值掩码图像合并成一个掩码图像。

    :param maskImgs: 多个二值掩码图像的列表，格式 [maskimg1, maskimg2, maskimg3]
    :return: 合并之后的掩码图像
    """
    # 检查输入列表是否为空
    if not maskImgs:
        raise ValueError("maskImgs 列表不能为空")
    
    # 获取第一个掩码图像的大小
    first_mask = maskImgs[0]
    if len(first_mask.shape) != 2:
        raise ValueError("所有掩码图像必须是单通道的二值图")
    
    height, width = first_mask.shape
    
    # 创建一个与第一个掩码图像大小相同的空白掩码图像
    combined_mask = np.zeros((height, width), dtype=np.uint8)
    
    # 遍历所有掩码图像并合并
    for mask in maskImgs:
        if mask.shape != (height, width):
            raise ValueError("所有掩码图像的大小必须一致")
        combined_mask = cv2.bitwise_or(combined_mask, mask)
    
    return combined_mask

# 在图像上合并一个mask图
def combineImgWithMask(img,maskimg,color):
    """
    在图像对象 img 上合并一个 maskimg 图像（二值图）。

    :param img: 图像对象 (numpy array)
    :param maskimg: mask 图像对象 (numpy array，单通道二值图)
    :param color: mask 叠加用的颜色 (B, G, R)
    :return: 合并后的图像
    """
    # 确保 img 和 maskimg 是 numpy 数组
    img = np.array(img)
    maskimg = np.array(maskimg)
    
    # 确保 maskimg 是一个单通道的二值图
    if len(maskimg.shape) != 2:
        raise ValueError("maskimg 必须是一个单通道的二值图")
    
    # 创建一个与 img 大小相同的彩色 mask 图像
    mask_color = np.full_like(img, color)
    
    # 使用 maskimg 作为掩码，将指定颜色应用到 img 上
    combined_img = np.where(maskimg[:, :, np.newaxis] > 0, mask_color, img)
    
    return combined_img

def drawMaskCombineMask(mask,maskimg):
    """
    在二值图mask上合并一个二值图maskimg。

    :param mask: 二值图mask
    :param maskimg: 二值图maskimg
    :return: 合并后的二值图mask
    """
    # 确保 mask 和 maskimg 都是 numpy 数组
    mask = np.array(mask)
    maskimg = np.array(maskimg)
    
    # 确保 mask 和 maskimg 都是单通道的二值图
    if len(mask.shape) != 2 or len(maskimg.shape) != 2:
        raise ValueError("mask 和 maskimg 必须是单通道的二值图")
    
    # 使用 bitwise_or 进行合并
    combined_mask = cv2.bitwise_or(mask, maskimg)
    
    return combined_mask

def drawMaskByContours(mask,contours,thickness=10):
    """
    在二值图mask上绘制多个轮廓。
    
    :param mask 二值图mask
    :param countors 多个轮廓
                    格式: [[[x,y],[x,y],[x,y],[x,y]],[[x,y],[x,y],[x,y],[x,y]]]
    :param thickness: 轮廓的线宽
    :return: 二值图mask
    """
    # 在空白图上绘制轮廓
    cv2.drawContours(mask, contours, -1, 255, thickness)
    
    return mask

def drawNewMaskByContours(contours,mask_width,mask_height,thickness=10):
    """
    生成一个二值图，并在上面绘制多个轮廓。
    
    :param countors 多个轮廓
                    格式: [[[x,y],[x,y],[x,y],[x,y]],[[x,y],[x,y],[x,y],[x,y]]]
    :mask_width 二值图的宽度
    :mask_height 二值图的高度
    :param thickness: 轮廓的线宽
    :return: 二值图mask
    """
    # 创建一个空白的二值图
    mask = np.zeros((mask_height, mask_width), dtype=np.uint8)
    
    # 在空白图上绘制轮廓
    cv2.drawContours(mask, contours, -1, 255, thickness)
    
    return mask

# 在一个二值图上绘制多个轮廓。
def drawContours2Mask(maskimg, contours, thickness=10):
    """
    在一个二值图上绘制多个轮廓的边缘。

    :param maskimg: 二值图
    :param contours: 轮廓组，包含多个轮廓，每个轮廓是一个x、y坐标数组。
                     格式: [[[x,y],[x,y],[x,y],[x,y]],[[x,y],[x,y],[x,y],[x,y]]]
    :param thickness: 轮廓的线宽
    :return: 绘制了轮廓边缘的二值图
    """
    # 确保 maskimg 是一个二值图
    if len(maskimg.shape) != 2:
        raise ValueError("maskimg 必须是一个二值图（单通道灰度图）")
    
    # 创建一个与 maskimg 大小相同的二值图副本
    result_mask = maskimg.copy()
    
    # 绘制轮廓的边缘
    cv2.drawContours(result_mask, contours, -1, 255, thickness)
    
    return result_mask

# 在图像上叠加二值图mask
def drawImgWithMask(img, mask, color):
    """
    在图像上叠加二值图mask。

    :param img: 图像对象 (numpy array)
    :param mask: 二值图 (numpy array，单通道灰度图)
    :param color: 二值图绘制到img上的颜色 (B, G, R)
    :return: 叠加后的图像
    """
    # 确保 img 和 mask 是 numpy 数组
    img = np.array(img)
    mask = np.array(mask)
    
    # 确保 mask 是一个单通道的二值图
    if len(mask.shape) != 2:
        raise ValueError("mask 必须是一个单通道的二值图")
    
    # 创建一个与 img 大小相同的彩色 mask 图像
    mask_color = np.full_like(img, color)
    
    # 使用 mask 作为掩码，将指定颜色应用到 img 上
    combined_img = np.where(mask[:, :, np.newaxis] > 0, mask_color, img)
    
    return combined_img

# 在图像上绘制轮廓(填充)
def drawImgWithContours(img, contours, color, thickness=10):
    """
    在图像上绘制多个轮廓。

    :param img: 图像对象 (numpy array)
    :param contours: 轮廓组，包含多个轮廓，每个轮廓是一个x、y坐标数组。
                     格式: [[[x,y],[x,y],[x,y],[x,y]],[[x,y],[x,y],[x,y],[x,y]]]
    :param color: 绘制轮廓的颜色 (B, G, R)
    :param thickness: 轮廓的线宽
    :return: 绘制了轮廓的图像
    """
    # 确保 img 是一个 numpy 数组
    img = np.array(img)
    
    # 创建一个与 img 大小相同的副本，用于绘制轮廓
    result_img = img.copy()
    
    # 绘制轮廓
    cv2.drawContours(result_img, contours, -1, color, thickness)
    
    return result_img

# 读取png图成为mask对象，透明部分黑色（0）其他部分白色（255）
def readMaskFromPng(pngfilename):
    """
    读取png图成为mask对象，透明部分黑色（0）其他部分白色（255）
    :param pngfilename: png文件路径
    :return: mask对象
    """
    # 读取包含Alpha通道的图像
    img = cv2.imread(pngfilename, cv2.IMREAD_UNCHANGED)
    
    # 检查是否包含Alpha通道(通道数为4)
    if img is not None and img.shape[2] == 4:
        # 分离Alpha通道
        _, _, _, alpha = cv2.split(img)
        # 创建二值掩码: 透明区域(alpha=0)设为0，不透明区域设为255
        mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
    else:
        # 若无Alpha通道，使用灰度读取并强制二值化
        mask = cv2.imread(pngfilename, cv2.IMREAD_GRAYSCALE)
        _, mask = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
    return mask

# 画轮廓为合成图
# TODO：该函数可以删掉（函数名称不能这么简单，参数也应该详细的说明）
def draw(img, contours, result_mask, pointLists, color, thickness=10):
    """
    生成并保存结果图与导出json结果
    @pramas: img         输入图
    @pramas: contours    轮廓    
    @pramas: result_mask 结果mask        
    @pramas: pointLists  轮廓的点    
    @pramas: color       颜色(255,255,255)
    @pramas: thickness   线粗
    """
    result_c = cv2.drawContours(img.copy(), contours, contourIdx=-1, color=(255,255,255), thickness=-1)
    # 发布代码
    for pointList in pointLists:
        cv2.polylines(result_c, [np.array(pointList)], True, (0,255,0), thickness)  # 勾勒检测区域
        cv2.polylines(result_mask, [np.array(pointList)], True, (0,255,0), thickness)
    result_merge = cv2.addWeighted(img, 0, result_c, 1, 0)

    return result_merge, result_mask
