from fastapi import FastAPI, HTTPException, Response
import time
import os
import sys
from overlay.generate_overlay import generate_overlay
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from PIL import Image
import io
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database import get_database

app = FastAPI()

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

class DonationUpdate(BaseModel):
    streamer_id: str
    donor: str
    amount: float
    currency: str
    message: str = ""

@app.on_event("startup")
async def startup_event():
    """Подключение к базе данных при запуске"""
    db = await get_database()
    await db.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """Отключение от базы данных при завершении"""
    db = await get_database()
    await db.disconnect()

@app.post("/overlay/update")
async def update_donation(donation: DonationUpdate):
    """Обновление информации о донате (для тестирования или внешних уведомлений)"""
    try:
        db = await get_database()
        streamer_id = int(donation.streamer_id)
        
        streamer = await db.get_streamer_by_id(streamer_id)
        if not streamer:
            raise HTTPException(status_code=404, detail="Стример не найден")
        
        assets = await db.get_all_assets()
        
        asset = None
        for a in assets:
            if a['symbol'].upper() == donation.currency.upper():
                asset = a
                break
        
        if not asset:
            for a in assets:
                if a['symbol'] == 'ETH':
                    asset = a
                    break
        
        if not asset:
            raise HTTPException(status_code=400, detail="Не найден подходящий актив")
        
        nonce = f"test_{int(time.time())}"
        payment_url = f"test://overlay_payment_{nonce}"
        
        donation_id = await db.create_donation(
            streamer_id=streamer_id,
            asset_id=asset['id'],
            donor_name=donation.donor,
            amount=donation.amount,
            message=donation.message,
            payment_url=payment_url,
            nonce=nonce
        )
        
        await db.update_donation_status(donation_id, "confirmed", f"test_tx_{nonce[:8]}")
        
        return {"status": "ok", "donation_id": donation_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/overlay/png/{streamer_id}")
async def overlay_png(streamer_id: str):
    """Получение PNG изображения оверлея для последнего доната стримера"""
    try:
        streamer_id_int = int(streamer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный ID стримера")
    
    db = await get_database()
    donations = await db.get_recent_donations(streamer_id_int, limit=1)
    
    if not donations:
        img = Image.new('RGBA', (800, 200), (0, 0, 0, 0))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        return Response(content=img_bytes.getvalue(), media_type="image/png")
    
    latest_donation = donations[0]
    img_bytes = generate_overlay(
        latest_donation['donor_name'], 
        float(latest_donation['amount']), 
        latest_donation.get('message', '')
    )
    return Response(content=img_bytes, media_type="image/png")

@app.get("/overlay/html/{streamer_id}")
async def overlay_html(streamer_id: str):
    """Получение HTML оверлея для стримера с автообновлением"""
    try:
        streamer_id_int = int(streamer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный ID стримера")
    
    db = await get_database()
    donations = await db.get_recent_donations(streamer_id_int, limit=1)
    
    now = time.time()
    
    if donations:
        latest_donation = donations[0]
        confirmed_timestamp = latest_donation['confirmed_at'].timestamp() if latest_donation['confirmed_at'] else 0
        
        if now - confirmed_timestamp <= 25:
            donor = latest_donation['donor_name']
            amount = float(latest_donation['amount'])
            asset_symbol = latest_donation.get('asset_symbol', 'USD') 
            message = latest_donation.get('message', '')
            
            html = f"""
            <html>
            <head>
              <meta http-equiv="refresh" content="5">
              <style>
                body {{
                  margin: 0; padding: 0;
                  background: #1f1f1f;
                  display: flex; flex-direction: column;
                  align-items: center; justify-content: center;
                  height: 100vh;
                  font-family: sans-serif;
                }}
                img.gif {{
                  width: 400px;
                  height: 400px;
                  object-fit: contain;
                  margin-bottom: 10px;
                }}
                .donation-text {{
                  color: #f3961c;
                  text-align: center;
                  line-height: 1.2;
                }}
                .donation-main {{
                  font-size: 38px;
                }}
                .donation-message {{
                  font-size: 24px;
                  margin-top: 8px;
                }}
              </style>
            </head>
            <body>
              <img src="/static/animation.gif" alt="Animation" class="gif" />
              <div class="donation-text">
                <div class="donation-main"><strong>{donor}</strong> - {amount:.4f} {asset_symbol}</div>
                <div class="donation-message">{message}</div>
              </div>
            </body>
            </html>
            """
        else:
            # Донат слишком старый, показываем пустую страницу
            html = f"""
            <html>
            <head>
              <meta http-equiv="refresh" content="5">
              <style>body {{margin:0; background:#1f1f1f;}}</style>
            </head>
            <body></body>
            </html>
            """
    else:
        # Нет донатов, показываем пустую страницу
        html = f"""
        <html>
        <head>
          <meta http-equiv="refresh" content="5">
          <style>body {{margin:0; background:#1f1f1f;}}</style>
        </head>
        <body></body>
        </html>
        """
    
    return Response(content=html, media_type="text/html")

@app.get("/overlay/donations/{streamer_id}")
async def get_streamer_donations(streamer_id: str, limit: int = 10):
    """API для получения списка донатов стримера"""
    try:
        streamer_id_int = int(streamer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный ID стримера")
    
    db = await get_database()
    streamer = await db.get_streamer_by_id(streamer_id_int)
    if not streamer:
        raise HTTPException(status_code=404, detail="Стример не найден")
    
    donations = await db.get_recent_donations(streamer_id_int, limit)
    
    return {
        "streamer": {
            "id": streamer["id"],
            "name": streamer["name"],
            "wallet": streamer["wallet_address"]
        },
        "donations": [
            {
                "id": donation["id"],
                "donor_name": donation["donor_name"],
                "amount": float(donation["amount"]),
                "asset_symbol": donation.get("asset_symbol", "USD"),
                "asset_name": donation.get("asset_name", "Unknown"),
                "network": donation.get("asset_network", "unknown"),
                "message": donation["message"],
                "status": donation["status"],
                "created_at": donation["created_at"].isoformat() if donation["created_at"] else None,
                "confirmed_at": donation["confirmed_at"].isoformat() if donation["confirmed_at"] else None
            }
            for donation in donations
        ]
    }

@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {"status": "healthy", "timestamp": time.time()} 