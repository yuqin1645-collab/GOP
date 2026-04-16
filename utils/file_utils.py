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
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        logging.info(f"文件已保存至：{save_path}")
        return save_path
    except Exception as e:
        logging.error(f"下载文件失败：{url}, 错误：{e}")
        return None