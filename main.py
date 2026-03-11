import asyncio

from src.scraper.tutti import run_hybrid_scraper
from tests.db_simulated_test import db_simulated_test


def run_test(test: int):
    match test:
        case 0:
            db_simulated_test()
        case 1:
            asyncio.run(run_hybrid_scraper())


def main():
    run_test(1)


if __name__ == "__main__":
    main()