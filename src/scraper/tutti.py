import asyncio
import json
import re
from playwright.async_api import async_playwright
from src.db.database import SessionLocal, init_db
from src.db.models import Listing


def parse_price(price_str: str) -> float:
    if not price_str or "gratis" in price_str.lower():
        return 0.0
    cleaned = re.sub(r'[^\d.,]', '', price_str).replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


async def run_hybrid_scraper():
    print("Bot: Starting stealth hybrid scraper...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # I manually pasted this search query in:
            await page.goto("https://www.tutti.ch/de/q/suche/Ak65wb2tlbW9uIGthcnRlbsCUwMDAwA?sorting=newest&page=1&query=pokemon+karten")    # We go to the page like a normal human
            await page.wait_for_load_state("domcontentloaded")      # Wait just a moment for the DOM to settle

            print("Bot: Extracting hidden Next.js data...")
            next_data_script = await page.locator('#__NEXT_DATA__').inner_text()

            data = json.loads(next_data_script)     # Convert the raw text into a Python dictionary

            # Navigate the JSON tree to find the listings
            try:
                queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
                listings = queries[0]["state"]["data"]["listings"]["edges"]
            except KeyError:
                print("Bot: Could not find the expected JSON structure. Tutti might have changed their setup.")
                return

            print(f"Bot: Successfully extracted {len(listings)} listings! Saving to database...\n")

            init_db()
            db = SessionLocal()
            new_listings_count = 0

            for edge in listings:
                node = edge.get("node", {})

                listing_id = node.get("listingID")
                title = node.get("title")
                price_str = node.get("formattedPrice", "0")
                asking_price = parse_price(price_str)

                # Extract the highest quality image available
                image_url = "NO_IMAGE"
                thumbnail = node.get("thumbnail")
                if thumbnail and "retinaRendition" in thumbnail:
                    image_url = thumbnail["retinaRendition"].get("src", "NO_IMAGE")

                full_url = f"https://www.tutti.ch/vi/{listing_id}"

                # Check for duplicates
                existing = db.query(Listing).filter(Listing.tutti_id == listing_id).first()
                if existing:
                    continue

                # Create database entry
                new_listing = Listing(
                    tutti_id=listing_id,
                    title=title,
                    url=full_url,
                    asking_price=asking_price,
                    image_url=image_url,
                    status="NEW"
                )

                db.add(new_listing)
                new_listings_count += 1
                print(f"Saved: {title[:40]}... | CHF {asking_price}")

            db.commit()
            print(f"\nBot: Successfully added {new_listings_count} new listings to the database.")

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            if 'db' in locals():
                db.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_hybrid_scraper())