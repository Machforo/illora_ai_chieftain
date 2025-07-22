import logging
import os

LOG_PATH_TXT = 'C:\\Users\\Atharv\\Documents\\AI_chieftain_bot_AtharvKumar\\logs\\bot.log'

#-- function to initialize a logger that writes log to a file
def setup_logger(name: str, log_file: str = LOG_PATH_TXT, level=logging.INFO):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.hasHandlers():
        logger.addHandler(handler)

    return logger

logger = setup_logger("web")

def log_chat(source: str, session_id: str, user_input: str, response: str, intent: str = None):
    # Build intent string only if intent is provided
    intent_str = f" | Intent: {intent}" if intent else ""
    
    message = f"{source} | {session_id} | {user_input} | {response}{intent_str}"
    logger.info(message)
