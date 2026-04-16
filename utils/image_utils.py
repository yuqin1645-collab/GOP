import base64
from typing import Optional
import io
import requests
from logger import logger

logging = logger.setup_logger()

# 10MB in bytes
MAX_IMAGE_SIZE = 10 * 1024 * 1024

AFTER_MAX_IMAGE_SIZE = 7 * 1024 * 1024

# 尝试导入PIL
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL库未安装，图片压缩功能将不可用")

def download_and_process_image(url: str) -> Optional[str]:
    """
    下载图片，如果大于10MB则压缩，并转换为BASE64格式的 data URL

    Args:
        url: 图片URL

    Returns:
        str: BASE64编码的图片数据，格式为 data:image/{type};base64,{base64_image}
              如果处理失败则返回None
    """
    try:
        # 下载图片
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, stream=True, headers=headers, timeout=30)
        response.raise_for_status()

        # 获取图片内容
        image_content = b""
        for chunk in response.iter_content(chunk_size=8192):
            image_content += chunk

        logging.info(f"图片下载完成，大小: {len(image_content)} bytes")

        # 检查图片是否太小（可能是占位图或错误内容）
        if len(image_content) < 500:
            logging.warning(f"图片内容过小，可能是无效图片: {url}, 大小: {len(image_content)}")
            return None

        # 检查是否是HTML内容（OSS错误页面）
        content_text = image_content[:200].decode('utf-8', errors='ignore').lower()
        if '<html' in content_text or '<!doctype' in content_text or '<body' in content_text:
            logging.warning(f"下载到的是HTML页面而非图片: {url}")
            return None

        # 验证文件头魔数，确保是有效的图片
        if not _validate_image_header(image_content):
            logging.warning(f"图片文件头验证失败，可能是无效图片: {url}")
            return None

        # 使用PIL验证并处理图片
        if PIL_AVAILABLE:
            try:
                img = Image.open(io.BytesIO(image_content))

                # 验证图片尺寸是否合理
                width, height = img.size
                if width < 10 or height < 10:
                    logging.warning(f"图片尺寸过小: {width}x{height}, 可能是无效图片")
                    return None

                # 转换为RGB（如果需要）
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')

                # 重新编码为标准JPEG格式，确保兼容性
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                image_content = output.getvalue()
                content_type = 'image/jpeg'

                logging.info(f"图片处理完成，尺寸: {width}x{height}，最终大小: {len(image_content)} bytes")

                # 检查图片大小并压缩（如果需要）
                if len(image_content) > MAX_IMAGE_SIZE:
                    logging.info("图片大于10MB，开始压缩")
                    image_content = compress_image_to_size(image_content, AFTER_MAX_IMAGE_SIZE)
                    logging.info(f"图片压缩完成，大小: {len(image_content)} bytes")
            except Exception as e:
                logging.error(f"PIL处理图片失败: {e}")
                return None
        else:
            logging.warning("PIL库不可用，使用原始图片数据")
            content_type = 'image/jpeg'

        # 转换为BASE64
        base64_image = base64.b64encode(image_content).decode('utf-8')
        data_url = f"data:{content_type};base64,{base64_image}"

        logging.info(f"图片转换为base64完成，data URL长度: {len(data_url)}")
        return data_url

    except Exception as e:
        logging.error(f"处理图片失败: {url}, 错误: {e}")
        return None


def _validate_image_header(image_content: bytes) -> bool:
    """
    验证图片文件头魔数，确保是有效的图片格式

    Args:
        image_content: 图片二进制内容

    Returns:
        bool: 是否为有效的图片格式
    """
    # 常见图片格式的魔数
    magic_numbers = {
        b'\xff\xd8\xff': 'JPEG',
        b'\x89PNG\r\n\x1a\n': 'PNG',
        b'GIF87a': 'GIF',
        b'GIF89a': 'GIF',
        b'RIFF': 'WEBP',  # WEBP以RIFF开头
        b'BM': 'BMP',
    }

    for magic, format_name in magic_numbers.items():
        if image_content.startswith(magic):
            logging.debug(f"检测到有效的图片格式: {format_name}")
            return True

    # 如果魔数不匹配，但PIL可用，尝试用PIL验证
    if PIL_AVAILABLE:
        try:
            img = Image.open(io.BytesIO(image_content))
            img.verify()  # 验证图片完整性
            return True
        except Exception:
            pass

    logging.warning(f"未识别的图片格式，文件头: {image_content[:20].hex()}")
    return False

def compress_image_to_size(image_content: bytes, max_size: int) -> bytes:
    """
    将图片压缩到指定大小以内
    
    Args:
        image_content: 原始图片内容
        max_size: 最大大小（字节）
        
    Returns:
        bytes: 压缩后的图片内容
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("PIL库不可用，无法执行图片压缩")
        
    # 尝试打开图片
    image = Image.open(io.BytesIO(image_content))
    
    # 获取原始格式
    format = image.format or 'JPEG'
    
    # 渐进式压缩，直到图片大小满足要求
    quality = 90
    while quality > 10:
        output = io.BytesIO()
        image.save(output, format=format, quality=quality, optimize=True)
        compressed_content = output.getvalue()
        
        if len(compressed_content) <= max_size:
            return compressed_content
            
        quality -= 10
        
    # 如果质量降低到最低仍然超过限制，则调整尺寸
    width, height = image.size
    while len(compressed_content) > max_size:
        # 每次缩小10%
        width = int(width * 0.9)
        height = int(height * 0.9)
        
        if width < 10 or height < 10:
            break
            
        resized_image = image.resize((width, height), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        resized_image.save(output, format=format, quality=quality, optimize=True)
        compressed_content = output.getvalue()
        
    return compressed_content if compressed_content else image_content