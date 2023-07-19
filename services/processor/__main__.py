import sys

from .processor import SyncSketchProcessor


if __name__ == "__main__":
    syncsketch_processor = SyncSketchProcessor()
    sys.exit(syncsketch_processor.start_processing())

