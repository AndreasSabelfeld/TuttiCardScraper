import asyncio

from src.scraper.image_downloader import run_downloader
from src.scraper.tutti import run_hybrid_scraper
from src.vision.classifier import run_classifier
from src.vision.detector import run_vision_pipeline
from src.vision.gemini_classifier import analyze_card_sequential, analyze_card_parallel
from tests.db_simulated_test import db_simulated_test


def run_test(test: int):
    match test:
        case 0:
            db_simulated_test()


def main():
    asyncio.run(run_hybrid_scraper(max_listings=150))
    asyncio.run(run_downloader())
    run_vision_pipeline()
    asyncio.run(analyze_card_parallel())


if __name__ == "__main__":
    main()