from PIL import Image, ImageDraw, ImageFont
import io

def generate_overlay(donor: str, amount: float, message: str = "") -> bytes:
    width, height = 800, 200
    background_color = (30, 30, 30)
    text_color = (255, 255, 255)

    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        font = ImageFont.load_default()

    text = f"Donor: {donor}  Amount: {amount:.4f} ETH"
    draw.text((10, 10), text, font=font, fill=text_color)
    if message:
        draw.text((10, 50), f'Message: {message}', font=font, fill=text_color)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue() 