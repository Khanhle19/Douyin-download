import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
import os
import io
import sys

class SafeConsoleHandler(logging.StreamHandler):
    """A console handler that avoids UnicodeEncodeError by replacing unencodable chars."""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                enc = getattr(stream, 'encoding', None) or 'utf-8'
                safe = (msg + self.terminator).encode(enc, errors='replace').decode(enc, errors='ignore')
                stream.write(safe)
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logger(name, log_file, level=logging.INFO):
    """Configure logging with UTF-8 file output and safe console output."""
    log_path = Path(log_file).parent
    log_path.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'  # UTF-8 for file log
    )
    file_handler.setFormatter(formatter)

    console_handler = SafeConsoleHandler(stream=sys.stdout)
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Avoid duplicate handlers if setup_logger is called multiple times
    if not any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', None) and str(h.baseFilename).endswith(os.path.basename(log_file)) for h in logger.handlers):
        logger.addHandler(file_handler)
    if not any(isinstance(h, SafeConsoleHandler) for h in logger.handlers):
        logger.addHandler(console_handler)

    return logger

# 创建全局logger实例
logger = setup_logger("douyin_downloader", "logs/douyin_downloader.log") 