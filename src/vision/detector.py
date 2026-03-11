import os
import cv2
from ultralytics import YOLO
from src.db.database import SessionLocal
from src.db.models import Listing, Card

RAW_DIR = "data/raw/listings"
CROP_DIR = "data/processed/cropped_cards"


def run_vision_pipeline():
    print("Bot: Initializing Vision Pipeline...")

    os.makedirs(CROP_DIR, exist_ok=True)
    model = YOLO("yolov8n.pt")
    db = SessionLocal()

    try:
        listings = db.query(Listing).filter(Listing.status == "IMAGES_DOWNLOADED").all()

        if not listings:
            print("Bot: No new images to process.")
            return

        print(f"Bot: Found {len(listings)} images to analyze.")

        for listing in listings:
            img_path = os.path.join(RAW_DIR, f"{listing.tutti_id}.jpg")

            if not os.path.exists(img_path):
                print(f"  -> File missing for {listing.tutti_id}, skipping...")
                listing.status = "IMAGE_MISSING"
                continue

            print(f"\nAnalyzing: {listing.title[:30]}...")
            img = cv2.imread(img_path)

            results = model(img, conf=0.20, verbose=False)
            result = results[0]
            boxes = result.boxes
            print(f"  -> AI found {len(boxes)} potential objects.")

            card_count = 0

            listing_crop_dir = os.path.join(CROP_DIR, str(listing.tutti_id))
            if len(boxes) > 0:
                os.makedirs(listing_crop_dir, exist_ok=True)

            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                cropped_img = img[y1:y2, x1:x2]

                if cropped_img.size == 0:
                    continue

                # We can simplify the filename since it's isolated in its own folder
                crop_filename = f"card_{i}.jpg"
                crop_filepath = os.path.join(listing_crop_dir, crop_filename)
                cv2.imwrite(crop_filepath, cropped_img)

                new_card = Card(
                    listing_id=listing.id,
                    cropped_image_path=crop_filepath,
                )
                db.add(new_card)
                card_count += 1

            listing.status = "PROCESSED_VISION"
            print(f"  -> Successfully cropped and saved {card_count} objects to DB.")

        db.commit()
        print("\nBot: Vision pipeline finished successfully.")

    except Exception as e:
        print(f"Error in vision pipeline: {e}")
        db.rollback()
    finally:
        db.close()
