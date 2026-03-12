import asyncio

from src.notifications.reporter import generate_and_send_report
from src.pricing.calculator import calculate_arbitrage
from src.pricing.pricecharting import run_parallel_pricer
from src.scraper.image_downloader import run_downloader
from src.scraper.tutti import run_hybrid_scraper
from src.vision.detector import run_vision_pipeline
from src.vision.gemini_classifier import analyze_card_sequential, analyze_card_parallel
from tests.db_simulated_test import db_simulated_test
from tests.test_local_roboflow import test_local_inference


def main():
    asyncio.run(run_hybrid_scraper(max_listings=50))
    asyncio.run(run_downloader())
    run_vision_pipeline()
    asyncio.run(analyze_card_sequential())
    asyncio.run(run_parallel_pricer())
    calculate_arbitrage()
    generate_and_send_report()

if __name__ == "__main__":
    main()