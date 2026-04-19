import os
from pathlib import Path
import random
import datetime
from typing import Optional

import requests
from urllib.parse import urlparse

from logger import logger

logging = logger.setup_logger()

def get_file_name() -> str:
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = f"{random.randint(0, 999999):06d}"
    return f"{now}_{rand}.PDF"

def get_file_name_by_original_name(original_name: str) -> str:
    """
    根据原始文件名确定新文件名，保持相同的文件扩展名
    
    Args:
        original_name (str): 原始文件名
        
    Returns:
        str: 新的文件名，包含时间戳和随机数，但保持相同的扩展名
    """
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = f"{random.randint(0, 999999):06d}"
    
    # 获取原始文件的扩展名
    if original_name and '.' in original_name:
        ext = original_name.split('.')[-1]
        # 限制扩展名长度，防止异常情况
        if len(ext) <= 10:  
            return f"{now}_{rand}.{ext}"
    
    # 如果没有有效的扩展名，使用默认的PDF扩展名
    return f"{now}_{rand}.PDF"

def get_file_name_csv() -> str:
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = f"{random.randint(0, 999):03d}"  # 修改这里，使得随机数范围变为0到999，并且总是3位
    return f"{now}_{rand}.csv"

def download_file(url: str, save_dir: str = "downloads", custom_filename: str = None) -> Optional[str]:
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    filename = custom_filename or os.path.basename(parsed.path)
    save_path = os.path.join(save_dir, filename)

    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            content_length = r.headers.get('Content-Length', '未知')
            logging.info(f"下载文件: {url}, 预期大小: {content_length} bytes")
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        actual_size = os.path.getsize(save_path)
        logging.info(f"文件已保存至：{save_path}, 实际大小: {actual_size} bytes")
        
        if actual_size == 0:
            logging.warning(f"下载的文件为空，URL: {url}")
        return save_path
    except Exception as e:
        logging.error(f"下载文件失败：{url}, 错误：{e}")
        return None


def cleanup_downloaded_files(save_dir: str = "downloads", keep_count: int = 50):
    """
    清理downloads目录中的旧文件，只保留最新的N个文件
    
    Args:
        save_dir: 目录路径
        keep_count: 保留的最新文件数量，默认50
    """
    try:
        dir_path = Path(save_dir)
        if not dir_path.exists():
            return
        
        # 获取所有文件，按修改时间排序
        files = sorted(dir_path.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        
        # 如果文件数量超过阈值，删除旧文件
        if len(files) > keep_count:
            for file in files[keep_count:]:
                try:
                    file.unlink()
                    logging.debug(f"已清理旧文件：{file.name}")
                except Exception as e:
                    logging.warning(f"清理文件失败：{file}, 错误：{e}")
            
            logging.info(f"清理完成，已删除 {len(files) - keep_count} 个旧文件")
    except Exception as e:
        logging.warning(f"清理downloads目录失败：{e}")