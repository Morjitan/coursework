#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import sys
import argparse
import random
from typing import Dict, Any, List

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header():
    print(f"\n{Colors.CYAN}{Colors.BOLD} Отправка тестового доната стримеру{Colors.ENDC}")
    print(f"{Colors.CYAN}{'=' * 50}{Colors.ENDC}\n")


def print_success(message: str):
    print(f"{Colors.GREEN} {message}{Colors.ENDC}")


def print_error(message: str):
    print(f"{Colors.RED} {message}{Colors.ENDC}")


def print_info(message: str):
    print(f"{Colors.BLUE}ℹ  {message}{Colors.ENDC}")


def print_warning(message: str):
    print(f"{Colors.YELLOW}  {message}{Colors.ENDC}")


# Доступные активы (будут загружены из API)
AVAILABLE_ASSETS = []


async def load_assets_from_database():
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from database.database import get_database
        
        db = await get_database()
        await db.connect()
        
        try:
            assets = await db.get_all_assets()
            global AVAILABLE_ASSETS
            AVAILABLE_ASSETS = assets
            return True
        finally:
            await db.disconnect()
            
    except Exception as e:
        print_error(f"Ошибка загрузки активов: {e}")
        return False


def get_asset_by_symbol(symbol: str) -> Dict[str, Any]:
    for asset in AVAILABLE_ASSETS:
        if asset['symbol'].upper() == symbol.upper():
            return asset
    return None


def print_available_assets():
    print(f"\n{Colors.YELLOW} Доступные активы:{Colors.ENDC}")
    if not AVAILABLE_ASSETS:
        print("  ❌ Активы не загружены")
        return
    
    for asset in AVAILABLE_ASSETS:
        network = asset.get('network', 'unknown').upper()
        print(f"  • {Colors.BOLD}{asset['symbol']}{Colors.ENDC} - {asset['name']} ({network})")


# Предустановленные шаблоны донатов (обновлены для asset_id)
DONATION_TEMPLATES = {
    "random": {
        "donors": ["Тестер123", "StreamFan", "CryptoLover", "Поддержатель", "Анонимус", "Viewer777"],
        "amounts": [0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0],
        "asset_symbols": ["ETH", "USDT", "BNB", "MATIC", "TRX"],
        "messages": [
            "Отличный стрим!",
            "Спасибо за контент!",
            "Продолжай в том же духе",
            "Тестовый донат от системы",
            "Поддерживаю стримера!",
            "Хороший контент, держи!",
            "Тест тест тест 123",
            ""
        ]
    },
    "big": {
        "donor": "Щедрый_Донатер",
        "amount": 10.0,
        "asset_symbol": "ETH",
        "message": "Большой тестовый донат!"
    },
    "small": {
        "donor": "Мелкий_Поддержатель",
        "amount": 0.01,
        "asset_symbol": "USDT",
        "message": "Небольшая поддержка 😊"
    },
    "emoji": {
        "donor": "Emoji_Фан",
        "amount": 1.5,
        "asset_symbol": "BNB",
        "message": "🎮🔥💎🚀😍🎯💪🎉 Эмодзи тест! 🎉💪🎯😍🚀💎🔥🎮"
    },
    "long": {
        "donor": "Болтливый_Донатер",
        "amount": 2.0,
        "asset_symbol": "ETH",
        "message": "Это очень длинное сообщение для тестирования того, как система обрабатывает длинные тексты в донатах. Я хочу убедиться, что все отображается корректно и не ломается интерфейс при большом количестве текста в сообщении доната!"
    }
}


def generate_random_donation(streamer_id: str) -> Dict[str, Any]:
    """Генерирует случайный донат"""
    template = DONATION_TEMPLATES["random"]
    
    available_symbols = [asset['symbol'] for asset in AVAILABLE_ASSETS]
    if not available_symbols:
        asset_symbol = random.choice(template["asset_symbols"])
    else:
        asset_symbol = random.choice(available_symbols)
    
    asset = get_asset_by_symbol(asset_symbol)
    if not asset:
        asset = AVAILABLE_ASSETS[0] if AVAILABLE_ASSETS else None
        if not asset:
            raise ValueError("Нет доступных активов в системе")
    
    return {
        "streamer_id": streamer_id,
        "donor": random.choice(template["donors"]) + str(random.randint(1, 999)),
        "amount": random.choice(template["amounts"]),
        "asset_id": asset['id'],
        "asset_symbol": asset['symbol'],
        "message": random.choice(template["messages"])
    }


def create_donation_from_template(template_name: str, streamer_id: str) -> Dict[str, Any]:
    """Создает донат из шаблона"""
    if template_name == "random":
        return generate_random_donation(streamer_id)
    
    template = DONATION_TEMPLATES.get(template_name)
    if not template:
        raise ValueError(f"Неизвестный шаблон: {template_name}")
    
    asset = get_asset_by_symbol(template["asset_symbol"])
    if not asset:
        raise ValueError(f"Актив {template['asset_symbol']} не найден в системе")
    
    return {
        "streamer_id": streamer_id,
        "donor": template["donor"],
        "amount": template["amount"],
        "asset_id": asset['id'],
        "asset_symbol": asset['symbol'],
        "message": template["message"]
    }


async def send_donation_new_api(donation_data: Dict[str, Any]) -> tuple[bool, Any]:
    """Отправляет донат через новый API с поддержкой активов"""
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from database.database import get_database
        import uuid
        
        db = await get_database()
        await db.connect()
        
        try:
            nonce = uuid.uuid4().hex
            payment_url = f"test://payment_{nonce}"
            
            donation_id = await db.create_donation(
                streamer_id=int(donation_data["streamer_id"]),
                asset_id=donation_data["asset_id"],
                donor_name=donation_data["donor"],
                amount=donation_data["amount"],
                message=donation_data["message"],
                payment_url=payment_url,
                nonce=nonce
            )
            
            # Сразу помечаем как подтверждённый для тестирования
            await db.update_donation_status(donation_id, "confirmed", f"test_tx_{nonce[:8]}")
            
            return True, {"donation_id": donation_id, "nonce": nonce}
            
        finally:
            await db.disconnect()
            
    except Exception as e:
        return False, f"Ошибка: {e}"


async def send_donation_legacy_api(donation_data: Dict[str, Any], overlay_url: str = "http://localhost:8000") -> tuple[bool, Any]:
    """Отправляет донат через старый overlay API (legacy)"""
    url = f"{overlay_url}/overlay/update"

    legacy_data = {
        "streamer_id": donation_data["streamer_id"],
        "donor": donation_data["donor"],
        "amount": donation_data["amount"],
        "currency": donation_data.get("asset_symbol", "ETH"),
        "message": donation_data["message"]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=legacy_data) as response:
                if response.status == 200:
                    result = await response.json()
                    return True, result
                else:
                    error_text = await response.text()
                    return False, f"HTTP {response.status}: {error_text}"
                    
    except aiohttp.ClientError as e:
        return False, f"Ошибка соединения: {e}"
    except Exception as e:
        return False, f"Неожиданная ошибка: {e}"


async def send_donation(donation_data: Dict[str, Any], use_legacy: bool = False, overlay_url: str = "http://localhost:8000") -> tuple[bool, Any]:
    """Отправляет донат через выбранный API"""
    if use_legacy:
        return await send_donation_legacy_api(donation_data, overlay_url)
    else:
        return await send_donation_new_api(donation_data)


async def check_overlay_status(overlay_url: str = "http://localhost:8000") -> bool:
    """Проверяет доступность overlay сервиса"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{overlay_url}/health") as response:
                return response.status == 200
    except:
        return False


def print_donation_info(donation: Dict[str, Any]):
    """Красиво выводит информацию о донате"""
    print(f"{Colors.MAGENTA}📋 Детали доната:{Colors.ENDC}")
    print(f"  🎯 Стример ID: {Colors.BOLD}{donation['streamer_id']}{Colors.ENDC}")
    print(f"  👤 Донатер: {Colors.BOLD}{donation['donor']}{Colors.ENDC}")
    
    asset_info = f"{donation['amount']} {donation.get('asset_symbol', 'UNKNOWN')}"
    if 'asset_id' in donation:
        asset_info += f" (Asset ID: {donation['asset_id']})"
    print(f"  💰 Сумма: {Colors.BOLD}{asset_info}{Colors.ENDC}")
    
    print(f"  💬 Сообщение: {Colors.CYAN}{donation['message'] or '(пустое)'}{Colors.ENDC}")


def print_available_templates():
    """Выводит список доступных шаблонов"""
    print(f"\n{Colors.YELLOW}📚 Доступные шаблоны:{Colors.ENDC}")
    for name, template in DONATION_TEMPLATES.items():
        if name == "random":
            print(f"  • {Colors.BOLD}random{Colors.ENDC} - случайные донаты")
        else:
            print(f"  • {Colors.BOLD}{name}{Colors.ENDC} - {template['donor']}: {template['amount']} {template['asset_symbol']}")


async def interactive_mode():
    """Интерактивный режим создания доната"""
    print(f"\n{Colors.CYAN}🎮 Интерактивный режим{Colors.ENDC}")
    print("Введите данные для доната (Enter для значений по умолчанию):\n")
    
    if not AVAILABLE_ASSETS:
        print_info("Загрузка списка активов...")
        if not await load_assets_from_database():
            print_error("Не удалось загрузить активы")
            return None
    
    streamer_id = input(f"{Colors.BLUE}Streamer ID{Colors.ENDC} [1]: ").strip() or "1"
    
    donor = input(f"{Colors.BLUE}Имя донатера{Colors.ENDC} [Интерактивный_Тестер]: ").strip() or "Интерактивный_Тестер"
    
    while True:
        amount_str = input(f"{Colors.BLUE}Сумма{Colors.ENDC} [1.0]: ").strip() or "1.0"
        try:
            amount = float(amount_str)
            break
        except ValueError:
            print_error("Введите корректное число")
    
    print_available_assets()
    while True:
        asset_symbol = input(f"{Colors.BLUE}Символ актива{Colors.ENDC} [ETH]: ").strip().upper() or "ETH"
        asset = get_asset_by_symbol(asset_symbol)
        if asset:
            break
        print_error(f"Актив {asset_symbol} не найден. Доступные: {', '.join([a['symbol'] for a in AVAILABLE_ASSETS])}")
    
    message = input(f"{Colors.BLUE}Сообщение{Colors.ENDC} [Интерактивный тестовый донат]: ").strip() or "Интерактивный тестовый донат"
    
    return {
        "streamer_id": streamer_id,
        "donor": donor,
        "amount": amount,
        "asset_id": asset['id'],
        "asset_symbol": asset['symbol'],
        "message": message
    }


async def bulk_donations(count: int, streamer_id: str, delay: float = 1.0, use_legacy: bool = False):
    """Отправляет несколько случайных донатов"""
    print(f"\n{Colors.YELLOW}🚀 Отправка {count} случайных донатов с интервалом {delay}с{Colors.ENDC}")
    
    if not AVAILABLE_ASSETS:
        print_info("Загрузка списка активов...")
        if not await load_assets_from_database():
            print_error("Не удалось загрузить активы")
            return
    
    success_count = 0
    
    for i in range(1, count + 1):
        print(f"\n{Colors.CYAN}Донат {i}/{count}:{Colors.ENDC}")
        
        try:
            donation = generate_random_donation(streamer_id)
            print_donation_info(donation)
            
            success, result = await send_donation(donation, use_legacy)
            
            if success:
                print_success(f"Донат {i} отправлен успешно!")
                success_count += 1
            else:
                print_error(f"Ошибка отправки доната {i}: {result}")
        except Exception as e:
            print_error(f"Ошибка генерации доната {i}: {e}")
        
        if i < count:
            print(f"{Colors.BLUE}Ожидание {delay}с...{Colors.ENDC}")
            await asyncio.sleep(delay)
    
    print(f"\n{Colors.MAGENTA}📊 Итого: {success_count}/{count} донатов отправлено успешно{Colors.ENDC}")


async def main():
    parser = argparse.ArgumentParser(
        description="Отправка тестовых донатов стримеру (новая система активов)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python scripts/send_test_donation.py                           # Интерактивный режим
  python scripts/send_test_donation.py --template random         # Случайный донат стримеру #1
  python scripts/send_test_donation.py --template big --id 2     # Большой донат стримеру #2
  python scripts/send_test_donation.py --bulk 5                  # 5 случайных донатов
  python scripts/send_test_donation.py --custom --donor "Тест" --amount 3.5 --asset ETH --message "Привет!"
  python scripts/send_test_donation.py --legacy                  # Использовать старый overlay API
        """
    )
    
    parser.add_argument("--streamer-id", "-id", default="1", help="ID стримера (по умолчанию: 1)")
    parser.add_argument("--template", "-t", choices=list(DONATION_TEMPLATES.keys()), 
                       help="Использовать готовый шаблон")
    parser.add_argument("--templates", action="store_true", help="Показать доступные шаблоны")
    parser.add_argument("--assets", action="store_true", help="Показать доступные активы")
    parser.add_argument("--interactive", "-i", action="store_true", help="Интерактивный режим")
    parser.add_argument("--bulk", "-b", type=int, help="Отправить несколько случайных донатов")
    parser.add_argument("--delay", type=float, default=1.0, help="Задержка между донатами в bulk режиме (сек)")
    
    # Кастомный донат
    parser.add_argument("--custom", "-c", action="store_true", help="Создать кастомный донат")
    parser.add_argument("--donor", help="Имя донатера")
    parser.add_argument("--amount", type=float, help="Сумма доната")
    parser.add_argument("--asset", help="Символ актива (ETH, USDT, BNB, etc.)")
    parser.add_argument("--message", default="", help="Сообщение доната")
    
    parser.add_argument("--legacy", action="store_true", help="Использовать старый overlay API")
    parser.add_argument("--url", default="http://localhost:8000", help="URL overlay сервиса")
    parser.add_argument("--no-check", action="store_true", help="Не проверять доступность сервиса")
    
    args = parser.parse_args()
    
    print_header()
    
    if not args.templates:
        print_info("Загрузка списка активов из базы данных...")
        if not await load_assets_from_database():
            print_error("Не удалось загрузить активы из базы данных")
            return 1
        print_success(f"Загружено {len(AVAILABLE_ASSETS)} активов")
    
    if args.assets:
        print_available_assets()
        return 0
    
    if args.templates:
        print_available_templates()
        return 0
    
    if args.legacy and not args.no_check:
        print_info("Проверка доступности overlay сервиса...")
        if not await check_overlay_status(args.url):
            print_error(f"Overlay сервис недоступен по адресу {args.url}")
            print_warning("Убедитесь что сервис запущен: make up")
            print_info("Или используйте --no-check для пропуска проверки")
            return 1
        print_success("Overlay сервис доступен")
    
    if args.bulk:
        await bulk_donations(args.bulk, args.streamer_id, args.delay, args.legacy)
        return 0
    
    donation_data = None
    
    if args.custom:
        if not all([args.donor, args.amount, args.asset]):
            print_error("Для кастомного доната требуются: --donor, --amount, --asset")
            return 1
        
        asset = get_asset_by_symbol(args.asset)
        if not asset:
            print_error(f"Актив {args.asset} не найден")
            print_available_assets()
            return 1
        
        donation_data = {
            "streamer_id": args.streamer_id,
            "donor": args.donor,
            "amount": args.amount,
            "asset_id": asset['id'],
            "asset_symbol": asset['symbol'],
            "message": args.message
        }
        
    elif args.template:
        try:
            donation_data = create_donation_from_template(args.template, args.streamer_id)
        except ValueError as e:
            print_error(str(e))
            print_available_templates()
            return 1
            
    elif args.interactive or len(sys.argv) == 1:
        donation_data = await interactive_mode()
        if not donation_data:
            return 1
        
    else:
        parser.print_help()
        return 1
    
    # Отправка доната
    api_type = "legacy overlay" if args.legacy else "новый database"
    print(f"\n{Colors.YELLOW}🚀 Отправка доната через {api_type} API...{Colors.ENDC}")
    print_donation_info(donation_data)
    
    success, result = await send_donation(donation_data, args.legacy, args.url)
    
    if success:
        print_success("Донат успешно отправлен!")
        if not args.legacy:
            print_info(f"ID доната: {result.get('donation_id', 'N/A')}")
        print_info("Проверьте overlay стримера для отображения доната")
        print(f"{Colors.CYAN}🌐 Overlay URL: {args.url}/overlay/html/{args.streamer_id}{Colors.ENDC}")
        return 0
    else:
        print_error(f"Ошибка отправки доната: {result}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Отправка прервана пользователем{Colors.ENDC}")
        sys.exit(130) 