import logging
import os

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
