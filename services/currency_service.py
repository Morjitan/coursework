import aiohttp
import asyncio
import logging
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class CurrencyService:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.exchangerate_api_key = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_cbr_rates(self) -> Dict[str, Decimal]:
        """
        Get currency rates from CBR
        Returns rates relative to ruble
        """
        if not self.session:
            raise RuntimeError("CurrencyService should be used as async context manager")
        
        url = "https://www.cbr.ru/scripts/XML_daily.asp"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    return self._parse_cbr_xml(content)
                else:
                    logger.error(f"ЦБ РФ API returned status {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching CBR rates: {e}")
            return {}
    
    def _parse_cbr_xml(self, xml_content: str) -> Dict[str, Decimal]:
        rates = {}
        
        try:
            root = ET.fromstring(xml_content)
            
            for valute in root.findall('Valute'):
                char_code = valute.find('CharCode')
                value = valute.find('Value')
                nominal = valute.find('Nominal')
                
                if char_code is not None and value is not None and nominal is not None:
                    code = char_code.text
                    rate_value = Decimal(value.text.replace(',', '.'))
                    nominal_value = Decimal(nominal.text)
                    
                    rate_per_unit = rate_value / nominal_value
                    rates[code] = rate_per_unit
            
            rates['RUB'] = Decimal('1.0')
            
        except Exception as e:
            logger.error(f"Error parsing CBR XML: {e}")
        
        return rates
    
    async def get_exchangerate_api_rates(self, base: str = "USD") -> Dict[str, Decimal]:
        """
        Get currency rates from ExchangeRate-API
        Free plan: 1500 requests/month
        """
        if not self.session:
            raise RuntimeError("CurrencyService should be used as async context manager")
        
        url = f"https://api.exchangerate-api.com/v4/latest/{base}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    rates = {}
                    rates[base] = Decimal('1.0')
                    
                    for currency, rate in data.get('rates', {}).items():
                        rates[currency] = Decimal(str(rate))
                    
                    return rates
                else:
                    logger.error(f"ExchangeRate-API returned status {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching ExchangeRate-API rates: {e}")
            return {}
    
    async def get_fixer_rates(self, api_key: str, base: str = "USD") -> Dict[str, Decimal]:
        """
        Получает курсы от Fixer.io
        Требует API ключ
        """
        if not self.session:
            raise RuntimeError("CurrencyService should be used as async context manager")
        
        url = f"http://data.fixer.io/api/latest"
        params = {
            'access_key': api_key,
            'base': base,
            'symbols': 'USD,RUB,EUR' 
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('success'):
                        rates = {}
                        rates[base] = Decimal('1.0')
                        
                        for currency, rate in data.get('rates', {}).items():
                            rates[currency] = Decimal(str(rate))
                        
                        return rates
                    else:
                        logger.error(f"Fixer API error: {data.get('error', {}).get('info', 'Unknown error')}")
                        return {}
                else:
                    logger.error(f"Fixer API returned status {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching Fixer rates: {e}")
            return {}
    
    async def get_combined_rates(self) -> Dict[str, Decimal]:
        logger.info("Fetching currency rates from multiple sources...")
        
        tasks = [
            self.get_cbr_rates(),
            self.get_exchangerate_api_rates("USD")
        ]
        
        cbr_rates, exchange_rates = await asyncio.gather(*tasks, return_exceptions=True)
        
        if isinstance(cbr_rates, Exception):
            logger.error(f"CBR rates error: {cbr_rates}")
            cbr_rates = {}
        
        if isinstance(exchange_rates, Exception):
            logger.error(f"ExchangeRate-API error: {exchange_rates}")
            exchange_rates = {}
        
        combined_rates = {}
        
        combined_rates['USD'] = Decimal('1.0')
        
        for currency, rate in exchange_rates.items():
            combined_rates[currency] = rate
        
        if 'USD' in cbr_rates:
            usd_to_rub = cbr_rates['USD']
            combined_rates['RUB'] = Decimal('1.0') / usd_to_rub
        
        logger.info(f"Retrieved rates for {len(combined_rates)} currencies")
        return combined_rates
    
    async def convert_currencies(
        self, 
        amount: Decimal, 
        from_currency: str, 
        to_currency: str,
        rates: Optional[Dict[str, Decimal]] = None
    ) -> Optional[Decimal]:
        if from_currency == to_currency:
            return amount
        
        if rates is None:
            rates = await self.get_combined_rates()
        
        if from_currency not in rates or to_currency not in rates:
            logger.error(f"Currency {from_currency} or {to_currency} not found in rates")
            return None
        
        from_rate = rates[from_currency]
        to_rate = rates[to_currency]
        
        usd_amount = amount / from_rate
        result = usd_amount * to_rate
        
        return result


async def get_current_rates() -> Dict[str, Decimal]:
    async with CurrencyService() as service:
        return await service.get_combined_rates()


async def convert_currency(
    amount: Decimal, 
    from_currency: str, 
    to_currency: str
) -> Optional[Decimal]:
    async with CurrencyService() as service:
        return await service.convert_currencies(amount, from_currency, to_currency) 