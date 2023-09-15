import sys
import os

from .processor import SyncSketchProcessor

from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    syncsketch_processor = SyncSketchProcessor()
    sys.exit(syncsketch_processor.start_processing())
