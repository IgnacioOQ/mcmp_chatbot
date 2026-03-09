import logging
import os
import time
from contextlib import contextmanager

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mcmp_chatbot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("MCMPChatbot")

def log_info(message: str):
    logger.info(message)

def log_error(message: str):
    logger.error(message)

@contextmanager
def log_latency(stage: str):
    start = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"[LATENCY] {stage}: {elapsed_ms:.1f}ms")
