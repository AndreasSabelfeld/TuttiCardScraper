import asyncio

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from src.db.database import SessionLocal
from src.db.models import Card
from src.pricing.pricecharting import format_search_query, fetch_card_price, get_live_exchange_rate, CONCURRENCY_LIMIT
from src.vision.gemini_classifier import analyze_card_free_tier_generator


async def background_pricing_task(context, card_data, semaphore, exchange_rate):
    """Background task that runs while Gemini is sleeping."""
    query = format_search_query(card_data["name"], card_data["set_info"])

    card_id, price_val_chf, pc_url, img_url, status = await fetch_card_price(
        context, card_data["card_id"], query, semaphore, exchange_rate
    )

    db = SessionLocal()
    try:
        db_card = db.query(Card).filter(Card.id == card_id).first()
        if db_card:
            db_card.estimated_price = price_val_chf
            db_card.pricecharting_url = pc_url
            db_card.pricecharting_image_url = img_url
            db.commit()

            status_text = f"[{price_val_chf} CHF]" if status == "FOUND" else f"[{status}]"
            print(f"  [Pricer] Finished Card {card_id}: {status_text}")
    finally:
        db.close()


async def run_smart_pipeline():
    """Orchestrates Gemini and Playwright to run concurrently for Cards."""
    print("Bot: Initializing Concurrent Vision & Pricing Pipeline for Cards...")
    usd_to_chf_rate = get_live_exchange_rate()
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    pricing_tasks = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        await Stealth().apply_stealth_async(context)

        # Start the Generator loop
        async for identified_card in analyze_card_free_tier_generator():
            task = asyncio.create_task(
                background_pricing_task(context, identified_card, semaphore, usd_to_chf_rate)
            )
            pricing_tasks.append(task)

        if pricing_tasks:
            print("\nBot: Vision complete. Waiting for final pricing tasks to finish...")
            await asyncio.gather(*pricing_tasks)

        await browser.close()
        print("Bot: Pipeline fully complete!")
