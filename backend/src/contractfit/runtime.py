from pathlib import Path

from contractfit.config import Settings
from contractfit.file_storage import LocalFileStorage
from contractfit.job_queue import InMemoryJobQueue, ProcessingJobQueue, RedisJobQueue
from contractfit.ocr import DocumentOcrProcessor, TesseractOcrEngine
from contractfit.processing import DocumentProcessor
from contractfit.store import ContractFitStore


def build_processing_queue(settings: Settings) -> ProcessingJobQueue:
    if settings.processing_mode == "redis":
        return RedisJobQueue.from_url(
            settings.redis_url, queue_key=settings.processing_queue_name
        )
    return InMemoryJobQueue()


def build_document_processor(
    settings: Settings, store: ContractFitStore
) -> DocumentProcessor:
    ocr = None
    if settings.ocr_backend == "tesseract":
        ocr = DocumentOcrProcessor(TesseractOcrEngine(settings.tesseract_command))
    return DocumentProcessor(
        store,
        LocalFileStorage(
            Path(settings.upload_directory), max_bytes=settings.upload_max_bytes
        ),
        ocr=ocr,
    )
