import logging
import os
from pathlib import Path

def setup_logging(config):
    log_dir = Path(config.get('log_dir', 'logs'))
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    # File handler
    fh = logging.FileHandler(log_dir / 'application.log')
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    # Error file
    eh = logging.FileHandler(log_dir / 'errors.log')
    eh.setLevel(logging.ERROR)
    eh.setFormatter(formatter)
    logger.addHandler(eh)