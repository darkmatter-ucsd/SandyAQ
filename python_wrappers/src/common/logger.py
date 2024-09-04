import logging
import os

# Configure the common logger
def setup_logger(name, console_level=logging.INFO, file_level = logging.DEBUG):
    logger = logging.getLogger(name)
    logger.setLevel(file_level)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Prevent the logger from propagating to the root logger
    logger.propagate = False
    
    # Create handlers if they don't exist
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)

        # File handler (optional)
        log_dir = os.path.join(current_dir,"../","logs/")
        os.makedirs(log_dir, exist_ok=True)  # Ensure log directory exists
        file_handler = logging.FileHandler(os.path.join(log_dir, f"{name}.log"), mode='w')
        file_handler.setLevel(file_level)
        
        # Formatter
        formatter = logging.Formatter(
            '%(levelname)s - %(name)s -  %(asctime)s - %(message)s')
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        # Add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    
    return logger
