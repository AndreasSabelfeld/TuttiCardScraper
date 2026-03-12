import os
import smtplib
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from dotenv import load_dotenv
from PIL import Image
from src.db.database import SessionLocal
from src.db.models import Listing, Card


def generate_and_send_report():
    print("Bot: Generating Arbitrage Email Report...")
    load_dotenv()

    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")

    if not all([smtp_server, sender_email, sender_password, receiver_email]):
        print("Bot: Missing email configuration in .env file!")
        return

    db = SessionLocal()

    try:
        listings = db.query(Listing).filter(Listing.total_estimated_value > 0).all()

        profitable_listings = []
        for listing in listings:
            profit = listing.total_estimated_value - listing.asking_price

            if profit > 0 and listing.asking_price > 0:
                profitable_listings.append((listing, listing.asking_price, profit))

        if not profitable_listings:
            print("Bot: No profitable listings found today. Skipping email.")
            return

        print(f"Bot: Found {len(profitable_listings)} profitable listings. Formatting email...")

        msg = MIMEMultipart('related')
        msg['Subject'] = f"🚨 Pokemon Arbitrage Alert: {len(profitable_listings)} Profitable Listings Found!"
        msg['From'] = sender_email
        msg['To'] = receiver_email

        html_content = """
        <html>
          <head>
            <style>
              body { font-family: Arial, sans-serif; }
              .listing-box { border: 2px solid #333; margin-bottom: 30px; padding: 15px; border-radius: 8px; background-color: #fafafa; }
              .profit { color: green; font-size: 1.2em; font-weight: bold; }
              table { width: 100%; border-collapse: collapse; margin-top: 15px; background-color: white; }
              th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
              th { background-color: #f2f2f2; }
              .card-img { max-width: 150px; max-height: 200px; border-radius: 5px; }
              details { margin-top: 15px; }
              summary {
                background-color: #007bff; color: white; padding: 12px; border-radius: 5px;
                cursor: pointer; font-weight: bold; list-style: none;
              }
              summary::-webkit-details-marker { display: none; }
              summary:hover { background-color: #0056b3; }
            </style>
          </head>
          <body>
            <h2>Your Daily Pokemon TCG Arbitrage Report</h2>
        """

        embedded_images = []

        for listing, asking_price, profit in profitable_listings:
            tutti_link = f"https://www.tutti.ch/vi/{listing.tutti_id}"

            html_content += f"""
            <div class="listing-box">
                <h3>{listing.title}</h3>
                <p>
                    <strong>Tutti Price:</strong> CHF {asking_price:.2f} | 
                    <strong>Estimated Value:</strong> CHF {listing.total_estimated_value:.2f}
                </p>
                <p class="profit">Net Profit: CHF {profit:.2f}</p>
                <a href="{tutti_link}" target="_blank">View Listing on Tutti</a>

                <table>
                    <tr>
                        <th>Tutti Crop</th>
                        <th>PriceCharting Ref</th>
                        <th>Card Details</th>
                    </tr>
            """

            for card in listing.cards:
                if not card.estimated_price or card.estimated_price == 0:
                    continue

                cid = f"image_{card.id}"

                local_img_html = "<i>Image Missing</i>"
                if os.path.exists(card.cropped_image_path):
                    local_img_html = f'<img src="cid:{cid}" class="card-img" alt="Cropped Card">'
                    embedded_images.append((cid, card.cropped_image_path))

                pc_img_html = "<i>No Ref Image</i>"
                if card.pricecharting_image_url:
                    pc_img_html = f'<img src="{card.pricecharting_image_url}" class="card-img" alt="Reference Card">'

                pc_link = card.pricecharting_url if card.pricecharting_url else "#"

                html_content += f"""
                        <tr>
                            <td>{local_img_html}</td>
                            <td>{pc_img_html}</td>
                            <td style="text-align: left;">
                                <strong>{card.detected_name}</strong><br>
                                Set: {card.set_info}<br>
                                Value: <strong>CHF {card.estimated_price:.2f}</strong><br>
                                <a href="{pc_link}" target="_blank">View on PriceCharting</a>
                            </td>
                        </tr>
                """

            html_content += """
                </table>
            </div>
            """

        html_content += """
          </body>
        </html>
        """

        msg.attach(MIMEText(html_content, 'html'))

        for cid, img_path in embedded_images:
            try:
                # Open the image using Pillow
                with Image.open(img_path) as img:
                    # Convert PNGs (RGBA) to standard JPEGs (RGB) if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    # .thumbnail resizes the image while maintaining the aspect ratio
                    # 150x200 is exactly what our CSS asks for
                    img.thumbnail((150, 200))

                    # Save the new image to an in-memory buffer instead of the hard drive
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=65)  # 65% quality is plenty for emails

                    # Extract the raw bytes
                    img_data = img_byte_arr.getvalue()

                # Attach the compressed bytes instead of the original file
                image = MIMEImage(img_data, name=f"{cid}.jpg")
                image.add_header('Content-ID', f'<{cid}>')
                image.add_header('Content-Disposition', 'inline')
                msg.attach(image)

            except Exception as e:
                print(f"  -> Could not compress and attach image {img_path}: {e}")

        print("Bot: Connecting to email server...")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        print("Bot: Success! Arbitrage report sent to your inbox.")

    except Exception as e:
        print(f"Fatal error in email reporter: {e}")
    finally:
        db.close()