import asyncio
import time
import random
import hashlib
import uuid
import threading
import logging
import sys
import os
from concurrent import futures
from typing import Dict, Optional
import grpc
import qrcode
import io
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse
import uvicorn

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import donation_pb2
import donation_pb2_grpc

from database import get_database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# В памяти храним данные о платежах: nonce -> запись
payments: Dict[str, dict] = {}

# Для предотвращения коллизий nonce
used_nonces: set = set()
nonce_counter = 0
nonce_lock = threading.Lock()

# Конфигурация
PAYMENT_TIMEOUT_MINUTES = 15
MONITORING_INTERVAL_SECONDS = 30
OVERLAY_SERVICE_URL = "http://overlay:8001"

# FastAPI приложение для HTTP API
app = FastAPI(title="Payment Service API")

@app.get("/")
async def root():
    """Главная страница с информацией о сервисе"""
    return {
        "service": "Payment Service",
        "version": "1.0.0",
        "active_payments": len([p for p in payments.values() if p['status'] == donation_pb2.PENDING_PAYMENT]),
        "total_payments": len(payments)
    }

@app.get("/qr/{nonce}")
async def get_qr_code(nonce: str):
    """Возвращает QR код для платежа в формате PNG"""
    payment_data = payments.get(nonce)
    
    if not payment_data:
        raise HTTPException(status_code=404, detail="Платеж не найден")
    
    try:
        # Генерируем QR код
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(payment_data["payment_url"])
        qr.make(fit=True)
        
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Конвертируем в bytes
        img_buffer = io.BytesIO()
        qr_image.save(img_buffer, format='PNG')
        qr_code_bytes = img_buffer.getvalue()
        
        return Response(content=qr_code_bytes, media_type="image/png")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации QR кода: {str(e)}")

@app.get("/payment/{nonce}", response_class=HTMLResponse)
async def get_payment_page(nonce: str):
    """Возвращает веб-страницу для оплаты"""
    payment_data = payments.get(nonce)
    
    if not payment_data:
        raise HTTPException(status_code=404, detail="Платеж не найден")
    
    # Проверяем не истек ли платеж
    if time.time() > payment_data.get('expires_at', 0):
        status_text = "❌ Время оплаты истекло"
        status_color = "#ff4444"
    elif payment_data['status'] == donation_pb2.PAYMENT_CONFIRMED:
        status_text = "✅ Платеж подтвержден"
        status_color = "#44ff44"
    elif payment_data['status'] == donation_pb2.PENDING_PAYMENT:
        status_text = "⏳ Ожидает оплаты"
        status_color = "#ffaa44"
    else:
        status_text = "❌ Платеж отменен"
        status_color = "#ff4444"
    
    expires_time = datetime.fromtimestamp(payment_data.get('expires_at', 0)).strftime('%H:%M:%S')
    
    # Получаем информацию об активе
    asset_info = payment_data.get('asset_info', {})
    decimals = asset_info.get('decimals', 6)
    asset_name = asset_info.get('name', payment_data['asset_symbol'])
    contract_address = asset_info.get('contract_address', 'Нативный токен')
    
    # Форматируем сумму с учетом decimals
    amount_display = f"{payment_data['amount']:.{min(decimals, 8)}f}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Оплата доната - {amount_display} {payment_data['asset_symbol']}</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .card {{
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                text-align: center;
            }}
            .status {{
                color: {status_color};
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 20px;
                padding: 10px;
                border-radius: 8px;
                background: rgba(0,0,0,0.05);
            }}
            .amount {{
                font-size: 28px;
                font-weight: bold;
                color: #333;
                margin: 20px 0;
                background: linear-gradient(45deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}
            .qr-code {{
                margin: 20px 0;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 10px;
            }}
            .qr-code img {{
                max-width: 250px;
                width: 100%;
                border-radius: 8px;
            }}
            .payment-url {{
                background: #f0f0f0;
                padding: 15px;
                border-radius: 8px;
                word-break: break-all;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                margin: 20px 0;
                border: 1px solid #ddd;
            }}
            .info {{
                text-align: left;
                margin-top: 20px;
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
            }}
            .info-item {{
                margin: 8px 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 5px 0;
                border-bottom: 1px solid #eee;
            }}
            .info-item:last-child {{
                border-bottom: none;
            }}
            .info-label {{
                font-weight: bold;
                color: #555;
            }}
            .info-value {{
                color: #333;
                font-family: monospace;
            }}
            .refresh-btn {{
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 25px;
                cursor: pointer;
                margin: 15px 5px;
                font-weight: bold;
                transition: transform 0.2s;
            }}
            .refresh-btn:hover {{
                transform: translateY(-2px);
            }}
            .copy-btn {{
                background: #28a745;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 15px;
                cursor: pointer;
                font-size: 12px;
                margin-left: 10px;
            }}
            .footer-note {{
                margin-top: 20px;
                font-size: 14px;
                color: #666;
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
            }}
        </style>
        <script>
            function refreshStatus() {{
                location.reload();
            }}
            
            function copyToClipboard(text) {{
                navigator.clipboard.writeText(text).then(function() {{
                    alert('Скопировано в буфер обмена!');
                }}, function() {{
                    // Fallback для старых браузеров
                    const textArea = document.createElement('textarea');
                    textArea.value = text;
                    document.body.appendChild(textArea);
                    textArea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textArea);
                    alert('Скопировано в буфер обмена!');
                }});
            }}
            
            // Автообновление каждые 10 секунд
            setInterval(refreshStatus, 10000);
        </script>
    </head>
    <body>
        <div class="card">
            <h1>💰 Оплата доната</h1>
            <div class="status">{status_text}</div>
            
            <div class="amount">{amount_display} {payment_data['asset_symbol']}</div>
            
            <div class="info">
                <div class="info-item">
                    <span class="info-label">Стример:</span>
                    <span class="info-value">{payment_data.get('donor_name', 'Неизвестно')}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Актив:</span>
                    <span class="info-value">{asset_name} ({payment_data['asset_symbol']})</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Сеть:</span>
                    <span class="info-value">{payment_data['network'].upper()}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Decimals:</span>
                    <span class="info-value">{decimals}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Контракт:</span>
                    <span class="info-value">{contract_address[:20]}{'...' if len(str(contract_address)) > 20 else ''}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Истекает:</span>
                    <span class="info-value">{expires_time}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Nonce:</span>
                    <span class="info-value">{nonce[:15]}...</span>
                </div>
            </div>
            
            <div class="qr-code">
                <img src="/qr/{nonce}" alt="QR код для оплаты">
                <p><strong>📱 Отсканируйте QR код кошельком</strong></p>
            </div>
            
            <div class="payment-url">
                {payment_data['payment_url']}
                <button class="copy-btn" onclick="copyToClipboard('{payment_data['payment_url']}')">📋 Копировать</button>
            </div>
            
            <button class="refresh-btn" onclick="refreshStatus()">🔄 Обновить статус</button>
            
            <div class="footer-note">
                <p><strong>💡 Как оплатить:</strong></p>
                <p>1. Отсканируйте QR код кошельком (MetaMask, Trust Wallet, etc.)</p>
                <p>2. Или скопируйте ссылку и откройте в кошельке</p>
                <p>3. Подтвердите транзакцию точно на указанную сумму</p>
                <p><strong>⏰ Страница автоматически обновляется каждые 10 секунд</strong></p>
                <p><strong>⚠️ Точная сумма важна для идентификации платежа!</strong></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

@app.get("/payments")
async def list_payments():
    """Возвращает список всех платежей для отладки"""
    return {
        "payments": [
            {
                "nonce": nonce,
                "amount": data['amount'],
                "asset_symbol": data['asset_symbol'],
                "status": data['status'],
                "created_at": data.get('created_at', 0),
                "expires_at": data.get('expires_at', 0)
            }
            for nonce, data in payments.items()
        ]
    }

class PaymentMonitor:
    """Класс для мониторинга блокчейн транзакций"""
    
    def __init__(self):
        self.running = True
    
    async def start_monitoring(self):
        """Запускает мониторинг всех активных платежей"""
        while self.running:
            try:
                await self.check_all_payments()
                await asyncio.sleep(MONITORING_INTERVAL_SECONDS)
            except Exception as e:
                print(f"Ошибка мониторинга: {e}")
                await asyncio.sleep(5)
    
    async def check_all_payments(self):
        """Проверяет все активные платежи"""
        current_time = time.time()
        expired_payments = []
        
        for nonce, payment_data in payments.items():
            if current_time > payment_data.get('expires_at', 0):
                if payment_data['status'] == donation_pb2.PENDING_PAYMENT:
                    payment_data['status'] = donation_pb2.CANCELLED
                    expired_payments.append(nonce)
                continue
            
            if payment_data['status'] == donation_pb2.PENDING_PAYMENT:
                await self.check_blockchain_transaction(nonce, payment_data)
        
        for nonce in expired_payments:
            await self.notify_payment_cancelled(nonce)
    
    async def check_blockchain_transaction(self, nonce: str, payment_data: dict):
        """Проверяет транзакцию в блокчейне (симуляция)"""
        
        created_time = payment_data.get('created_at', time.time())
        if time.time() - created_time > 60:
            if random.random() < 0.8:
                await self.confirm_payment(nonce, f"0x{hashlib.md5(nonce.encode()).hexdigest()}")
    
    async def confirm_payment(self, nonce: str, transaction_hash: str):
        """Подтверждает платеж и уведомляет overlay"""
        if nonce in payments:
            payments[nonce]['status'] = donation_pb2.PAYMENT_CONFIRMED
            payments[nonce]['transaction_hash'] = transaction_hash
            payments[nonce]['confirmed_at'] = time.time()
            
            await self.notify_overlay_service(nonce)
    
    async def notify_overlay_service(self, nonce: str):
        """Уведомляет overlay сервис о подтверждении платежа"""
        try:
            payment_data = payments[nonce]
            
            overlay_data = {
                "donation_id": payment_data['donation_id'],
                "nonce": nonce,
                "status": "confirmed",
                "transaction_hash": payment_data.get('transaction_hash', ''),
                "donor_name": payment_data['donor_name'],
                "amount": payment_data['amount'],
                "asset_symbol": payment_data['asset_symbol'],
                "message": payment_data.get('message', '')
            }
            
            print(f"📡 Уведомляем overlay о подтверждении доната: {overlay_data}")
            
            payments[nonce]['status'] = donation_pb2.SHOWING_IN_OVERLAY
            
        except Exception as e:
            print(f"Ошибка уведомления overlay: {e}")
    
    async def notify_payment_cancelled(self, nonce: str):
        """Уведомляет об отмене платежа"""
        if nonce in payments:
            payment_data = payments[nonce]
            print(f"⏰ Платеж отменен по таймауту: {payment_data['donation_id']}")

class DonationService(donation_pb2_grpc.DonationServiceServicer):
    
    def __init__(self):
        self.monitor = PaymentMonitor()
        self.db = None

    async def start_services(self):
        """Запускает async сервисы"""
        await self._init_database()
        asyncio.create_task(self.monitor.start_monitoring())
    
    async def _init_database(self):
        """Инициализация подключения к базе данных"""
        try:
            self.db = await get_database()
            await self.db.connect()
            print("📊 Подключение к базе данных установлено")
        except Exception as e:
            print(f"⚠️ Ошибка подключения к базе данных: {e}")
            self.db = None
    
    async def get_asset_info(self, asset_symbol: str, network: str) -> Optional[dict]:
        """Получает информацию об активе из базы данных"""
        if not self.db:
            print("⚠️ База данных недоступна, используем значения по умолчанию")
            default_decimals = {
                'ETH': 18, 'BTC': 8, 'USDT': 6, 'USDC': 6, 
                'BNB': 18, 'MATIC': 18, 'TRX': 6
            }
            return {
                'decimals': default_decimals.get(asset_symbol, 6),
                'symbol': asset_symbol,
                'network': network
            }
        
        try:
            assets = await self.db.get_all_assets()
            for asset in assets:
                if (asset['symbol'].upper() == asset_symbol.upper() and 
                    asset['network'].lower() == network.lower()):
                    return {
                        'decimals': asset['decimals'],
                        'symbol': asset['symbol'],
                        'network': asset['network'],
                        'contract_address': asset.get('contract_address'),
                        'name': asset.get('name', asset_symbol)
                    }
            
            print(f"⚠️ Актив {asset_symbol} на сети {network} не найден в базе данных")
            # Возвращаем дефолтные значения
            default_decimals = {
                'ETH': 18, 'BTC': 8, 'USDT': 6, 'USDC': 6, 
                'BNB': 18, 'MATIC': 18, 'TRX': 6
            }
            return {
                'decimals': default_decimals.get(asset_symbol, 6),
                'symbol': asset_symbol,
                'network': network
            }
        except Exception as e:
            print(f"❌ Ошибка получения информации об активе: {e}")
            return None
    
    def generate_unique_nonce(self, amount: float, asset_info: dict) -> tuple[str, float]:
        """Генерирует уникальный nonce без коллизий"""
        global nonce_counter
        
        with nonce_lock:
            nonce_counter += 1
            
            timestamp_ns = int(time.time() * 1_000_000)
            process_id = os.getpid()
            thread_id = threading.get_ident()
            random_part = random.randint(100000, 999999)
            
            # Создаем уникальный nonce
            nonce_base = f"{timestamp_ns}_{process_id}_{thread_id}_{nonce_counter}_{random_part}"
            
            # Проверяем на коллизии (хотя вероятность крайне мала)
            attempts = 0
            while nonce_base in used_nonces and attempts < 100:
                random_part = random.randint(100000, 999999)
                nonce_base = f"{timestamp_ns}_{process_id}_{thread_id}_{nonce_counter}_{random_part}"
                attempts += 1
            
            if attempts >= 100:
                # Крайне маловероятная ситуация - используем UUID
                nonce_base = f"uuid_{uuid.uuid4().hex}"
            
            # Добавляем в использованные
            used_nonces.add(nonce_base)
            
            # Очищаем старые nonce (старше 20 минут для надежности)
            self._cleanup_old_nonces()
            
            # Для уникальной суммы добавляем микро-количество в зависимости от decimals
            decimals = asset_info.get('decimals', 6)
            
            # Добавляем случайную сумму в последние разряды
            # Чем больше decimals, тем меньше добавка относительно основной суммы
            if decimals >= 6:
                # Для токенов с большим количеством decimals добавляем очень маленькую сумму
                random_addition = random.randint(1, 999999) / (10 ** (decimals + 3))
            else:
                # Для токенов с малым количеством decimals добавляем еще меньше
                random_addition = random.randint(1, 99999) / (10 ** (decimals + 5))
            
            final_amount = amount + random_addition
            
            print(f"💎 Сгенерирован уникальный nonce: {nonce_base[:20]}...")
            print(f"   Оригинальная сумма: {amount}")
            print(f"   Финальная сумма: {final_amount}")
            print(f"   Разница: {random_addition:.10f}")
            print(f"   Decimals актива: {decimals}")
            
            return nonce_base, final_amount
    
    def _cleanup_old_nonces(self):
        """Очищает старые nonce для предотвращения бесконечного роста"""
        current_time = time.time()
        cutoff_time = current_time - (PAYMENT_TIMEOUT_MINUTES + 5) * 60  # +5 минут для надежности
        
        # Удаляем старые платежи и их nonce
        expired_nonces = []
        for nonce, payment_data in payments.items():
            if payment_data.get('created_at', 0) < cutoff_time:
                expired_nonces.append(nonce)
        
        for nonce in expired_nonces:
            if nonce in payments:
                del payments[nonce]
            if nonce in used_nonces:
                used_nonces.discard(nonce)
        
        if expired_nonces:
            print(f"🧹 Очищено {len(expired_nonces)} старых nonce")
    
    def CreatePaymentLink(self, request, context):
        """Создает ссылку для оплаты с уникальным nonce"""
        try:
            # Получаем информацию об активе асинхронно
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                asset_info = loop.run_until_complete(
                    self.get_asset_info(request.asset_symbol, request.network)
                )
            finally:
                loop.close()
            
            if not asset_info:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(f"Актив {request.asset_symbol} на сети {request.network} не поддерживается")
                return donation_pb2.CreatePaymentResponse()
            
            # Генерируем уникальный nonce и финальную сумму
            nonce, final_amount = self.generate_unique_nonce(request.amount, asset_info)
            
            # Создаем URL для оплаты (поддержка MetaMask и других кошельков)
            payment_url = self.generate_payment_url(
                request.streamer_wallet_address,
                final_amount,
                request.asset_symbol,
                request.network,
                nonce,
                asset_info
            )
            
            # Создаем QR код
            qr_code_url = f"http://payment-service:50052/qr/{nonce}"
            
            # Время истечения (15 минут)
            expires_at = int(time.time()) + (PAYMENT_TIMEOUT_MINUTES * 60)
            
            # Сохраняем данные о платеже
            payments[nonce] = {
                "donation_id": request.donation_id,
                "streamer_wallet": request.streamer_wallet_address,
                "amount": final_amount,
                "original_amount": request.amount,
                "asset_symbol": request.asset_symbol,
                "asset_info": asset_info,
                "network": request.network,
                "donor_name": request.donor_name,
                "message": request.message,
                "payment_url": payment_url,
                "transaction_hash": "",
                "status": donation_pb2.PENDING_PAYMENT,
                "created_at": time.time(),
                "expires_at": expires_at
            }
            
            print(f"💰 Создан платеж: {nonce[:15]}..., сумма: {final_amount:.8f} {request.asset_symbol}")
            print(f"   📊 Decimals: {asset_info['decimals']}, Сеть: {request.network}")
            
            return donation_pb2.CreatePaymentResponse(
                payment_url=payment_url,
                qr_code_url=qr_code_url,
                nonce=nonce,
                status=donation_pb2.PENDING_PAYMENT,
                expires_at=expires_at
            )
            
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Ошибка создания платежа: {str(e)}")
            return donation_pb2.CreatePaymentResponse()
    
    def generate_payment_url(self, wallet_address: str, amount: float, asset_symbol: str, 
                           network: str, nonce: str, asset_info: dict) -> str:
        """Генерирует URL для оплаты, совместимый с MetaMask"""
        
        # Конфигурация контрактов токенов для разных сетей
        token_contracts = {
            'ethereum': {
                'USDT': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
                'USDC': '0xA0b86a33E6417c1Bec9FB6C7b0D88c11b426Bb67'
            },
            'bsc': {
                'USDT': '0x55d398326f99059fF775485246999027B3197955',
                'USDC': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d'
            },
            'polygon': {
                'USDT': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',
                'USDC': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
            }
        }
        
        # Получаем decimals из asset_info
        decimals = asset_info.get('decimals', 6)
        contract_address = asset_info.get('contract_address')
        
        if asset_symbol.upper() in ['ETH', 'BNB', 'MATIC'] and not contract_address:
            # Нативные токены
            value = int(amount * (10 ** decimals))
            return f"ethereum:{wallet_address}@{self.get_chain_id(network)}?value={value}&gas=21000&nonce={nonce}"
        else:
            # ERC-20 токены - используем адрес контракта из базы данных или fallback
            if contract_address:
                final_contract = contract_address
            else:
                final_contract = token_contracts.get(network.lower(), {}).get(asset_symbol.upper())
            
            if final_contract:
                # Для ERC-20 используем стандартный transfer
                value = int(amount * (10 ** decimals))
                return f"ethereum:{final_contract}/transfer?address={wallet_address}&uint256={value}&nonce={nonce}"
            else:
                # Fallback URL
                print(f"⚠️ Контракт для {asset_symbol} на {network} не найден, используем fallback")
                return f"pay://{wallet_address}?amount={amount}&currency={asset_symbol}&nonce={nonce}"
    
    def get_chain_id(self, network: str) -> int:
        """Возвращает chain ID для сети"""
        chain_ids = {
            'ethereum': 1,
            'bsc': 56,
            'polygon': 137,
            'tron': 728126428  # Tron
        }
        return chain_ids.get(network, 1)
    
    def CheckTransactionStatus(self, request, context):
        """Проверяет статус транзакции"""
        try:
            # Извлекаем nonce из URL
            nonce = self.extract_nonce_from_url(request.payment_url)
            record = payments.get(nonce)
            
            if not record:
                return donation_pb2.CheckTransactionStatusResponse(
                    confirmed=False,
                    transaction_hash="",
                    status=donation_pb2.CANCELLED,
                    error_message="Платеж не найден"
                )
            
            return donation_pb2.CheckTransactionStatusResponse(
                confirmed=record["status"] >= donation_pb2.PAYMENT_CONFIRMED,
                transaction_hash=record["transaction_hash"],
                status=record["status"],
                error_message=""
            )
            
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Ошибка проверки статуса: {str(e)}")
            return donation_pb2.CheckTransactionStatusResponse(
                confirmed=False,
                error_message=str(e)
            )
    
    def extract_nonce_from_url(self, payment_url: str) -> str:
        """Извлекает nonce из URL платежа"""
        if 'nonce=' in payment_url:
            return payment_url.split('nonce=')[1].split('&')[0]
        return payment_url.rsplit('/', 1)[-1]
    
    def GetPaymentQRCode(self, request, context):
        """Генерирует QR код для платежа"""
        try:
            nonce = self.extract_nonce_from_url(request.payment_url)
            record = payments.get(nonce)
            
            if not record:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Платеж не найден")
                return donation_pb2.GetQRCodeResponse()
            
            # Генерируем QR код
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(record["payment_url"])
            qr.make(fit=True)
            
            qr_image = qr.make_image(fill_color="black", back_color="white")
            
            # Конвертируем в bytes
            img_buffer = io.BytesIO()
            qr_image.save(img_buffer, format='PNG')
            qr_code_bytes = img_buffer.getvalue()
            
            return donation_pb2.GetQRCodeResponse(
                qr_code_image=qr_code_bytes,
                qr_code_url=f"http://payment-service:50052/qr/{nonce}"
            )
            
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Ошибка генерации QR кода: {str(e)}")
            return donation_pb2.GetQRCodeResponse()
    
    def UpdateDonationStatus(self, request, context):
        """Обновляет статус доната (для внешних уведомлений)"""
        try:
            record = payments.get(request.nonce)
            
            if not record:
                return donation_pb2.UpdateDonationStatusResponse(
                    success=False,
                    message="Платеж не найден"
                )
            
            record["status"] = request.status
            if request.transaction_hash:
                record["transaction_hash"] = request.transaction_hash
            
            return donation_pb2.UpdateDonationStatusResponse(
                success=True,
                message="Статус обновлен"
            )
            
        except Exception as e:
            return donation_pb2.UpdateDonationStatusResponse(
                success=False,
                message=f"Ошибка: {str(e)}"
            )

def serve():
    """Запускает gRPC и HTTP серверы"""
    # Запускаем gRPC сервер
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    donation_service = DonationService()
    donation_pb2_grpc.add_DonationServiceServicer_to_server(donation_service, grpc_server)
    grpc_server.add_insecure_port("[::]:50051")
    
    print("🚀 Payment Service запущен...")
    print("📡 gRPC сервер: порт 50051")
    print("🌐 HTTP API: порт 50052")
    print("📱 QR коды доступны по адресу: http://localhost:50052/qr/{nonce}")
    print("💻 Веб-интерфейс: http://localhost:50052/payment/{nonce}")
    print("📊 Мониторинг блокчейн транзакций активен")
    
    grpc_server.start()
    
    # Инициализируем async сервисы
    async def init_async_services():
        await donation_service.start_services()
    
    # Запускаем инициализацию в новом event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_async_services())
    
    # Запускаем HTTP сервер в отдельном потоке
    def run_http_server():
        uvicorn.run(app, host="0.0.0.0", port=50052, log_level="info")
    
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    try:
        grpc_server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n🛑 Остановка сервисов...")
        grpc_server.stop(0)

if __name__ == '__main__':
    serve() 