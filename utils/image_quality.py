import cv2
import numpy as np
import requests


# 下载图片函数
def download_image(url):
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Failed to download image")
    img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
    return cv2.imdecode(img_array, cv2.IMREAD_COLOR)


# 图像模糊检测
def estimate_blur(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    fm = cv2.Laplacian(gray, cv2.CV_64F).var()
    # 返回原始值，更高的fm表示更清晰
    return fm


# 对比度计算
def calculate_contrast(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    contrast = gray.std()
    return contrast


# 噪声水平评估
def estimate_noise(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude_spectrum = 20 * np.log(np.abs(fshift))
    high_freq_energy = np.sum(magnitude_spectrum > 150) / magnitude_spectrum.size
    return high_freq_energy


# 综合评估函数
def evaluate_image_quality(image_url):
    try:
        image = download_image(image_url)

        blur_score = estimate_blur(image)
        contrast_value = calculate_contrast(image)
        noise_level = estimate_noise(image)

        # 标准化处理，使用更合理的范围
        # 模糊度：通常清晰图像的模糊度值较高，假设合理范围是[0, 2000]
        blur_score_normalized = min(blur_score / 2000.0, 1.0)
        
        # 对比度：假设合理范围是[0, 100]
        contrast_value_normalized = min(contrast_value / 100.0, 1.0)
        
        # 噪声：假设合理范围是[0, 1]，值越小越好，所以用1减去噪声值得到质量分
        noise_level_normalized = max(1.0 - noise_level, 0.0)

        # 使用加权方法计算综合得分，考虑不同因素对图像质量的影响程度
        # 模糊度权重: 0.5 (清晰度对质量影响最大)
        # 对比度权重: 0.3 
        # 噪声权重: 0.2
        weights = [0.5, 0.3, 0.2]
        scores = [blur_score_normalized, contrast_value_normalized, noise_level_normalized]
        
        overall_quality = sum(w * s for w, s in zip(weights, scores))

        # 确保结果在0-1范围内
        overall_quality = max(0.0, min(1.0, overall_quality))

        # 转换为百分比并保留两位小数
        overall_quality_percentage = round(overall_quality * 100, 2)

        print(f"Blur Score: {blur_score}")
        print(f"Contrast Value: {contrast_value}")
        print(f"Noise Level: {noise_level}")
        print(f"Normalized Blur Score: {blur_score_normalized:.4f}")
        print(f"Normalized Contrast Value: {contrast_value_normalized:.4f}")
        print(f"Normalized Noise Level: {noise_level_normalized:.4f}")
        print(f"Overall Quality Score: {overall_quality_percentage}%")
        
        # 正确地将数值转换为字符串
        overall_quality_percentage_str = f"{overall_quality_percentage}%"
        return overall_quality_percentage_str
    except Exception as e:
        print(e)
        return None

if __name__ == '__main__':
    result = evaluate_image_quality("https://mdlcnpro.oss-cn-beijing.aliyuncs.com/medilink/mdlcnpro/ClaimsDocument/202507/31965891/319658911.PNG?Expires=1755432039&OSSAccessKeyId=LTAI4Fis4PMghRuRmGsRrGRx&Signature=6y59LL1JP2rFy5%2B6b6pGt6%2Fn%2ByM%3D")
    print(result)