# logger.py
import logging
import logging.handlers
import os
from dotenv import load_dotenv

load_dotenv()

LOG_DIR = os.getenv("GOP_LOG_FILE")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "app.log")

def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # 使用 TimedRotatingFileHandler 处理多进程环境
        # 添加 delay=True 参数以避免在初始化时打开文件
        # 使用 utc=False 确保使用本地时间进行轮转
        file_handler = logging.handlers.TimedRotatingFileHandler(
            LOG_FILE, when="midnight", backupCount=30, encoding="utf-8", delay=True, utc=False
        )
        file_handler.setLevel(logging.INFO)

        # 添加处理程序获取/释放锁的函数以支持多进程
        def emit_and_release_lock(self, record):
            """
            在写入日志后释放文件锁，以支持多进程环境
            """
            try:
                logging.handlers.TimedRotatingFileHandler.emit(self, record)
            finally:
                self.stream.flush()
                os.fsync(self.stream.fileno())
        
        # 将自定义方法绑定到file_handler
        import types
        file_handler.emit = types.MethodType(emit_and_release_lock, file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger