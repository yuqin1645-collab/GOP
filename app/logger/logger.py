# logger.py
import logging
import logging.handlers
import os
from dotenv import load_dotenv

from pathlib import Path

load_dotenv()

# 使用 GOP_LOG_DIR 环境变量，默认使用项目下的 logs 目录
# Path().resolve() 确保路径标准化，自动清理双斜杠等不规范写法
_log_dir_str = os.getenv("GOP_LOG_DIR", "").strip()
if _log_dir_str:
    LOG_DIR = Path(_log_dir_str)
else:
    LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = str(LOG_DIR / "app.log")

def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 多进程环境（Gunicorn）：Worker 被 OOM kill 后新 Worker 会继承旧的 handler 引用，
    # 但旧 handler 的文件句柄已失效。因此每次 setup_logger 都先清除已有 handler，
    # 确保新 Worker 能创建全新的、可用的 handler。
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    # 使用 TimedRotatingFileHandler 处理多进程环境
    # 添加 delay=True 参数以避免在初始化时打开文件
    # 使用 utc=False 确保使用本地时间进行轮转
    file_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE, when="midnight", backupCount=30, encoding="utf-8", delay=True, utc=False
    )
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger