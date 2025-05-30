import os
import sys
import grpc
import logging
from typing import Optional, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import donation_pb2
import donation_pb2_grpc

logger = logging.getLogger(__name__)

class DonationClient:
    def __init__(self, server_address: str = "payment-service:50051"):
        self.server_address = server_address
        self._channel = None
        self._stub = None
    
    def _get_stub(self):
        """Получает gRPC stub, создавая подключение при необходимости"""
        if self._channel is None or self._stub is None:
            self._channel = grpc.insecure_channel(self.server_address)
            self._stub = donation_pb2_grpc.DonationServiceStub(self._channel)
        return self._stub
    
    def create_payment_link(self, streamer_wallet: str, amount: float, asset_symbol: str, 
                           network: str, donation_id: str, donor_name: str, 
                           message: str = "") -> dict:
        """
        Creates a payment link for donation
        
        Returns:
            dict: {
                'payment_url': str,
                'qr_code_url': str, 
                'nonce': str,
                'expires_at': int,
                'status': str
            }
        """
        try:
            stub = self._get_stub()
            
            request = donation_pb2.CreatePaymentRequest(
                streamer_wallet_address=streamer_wallet,
                amount=amount,
                asset_symbol=asset_symbol,
                network=network,
                donation_id=donation_id,
                donor_name=donor_name,
                message=message
            )
            
            response = stub.CreatePaymentLink(request)
            
            # Конвертируем статус в строку
            status_names = {
                donation_pb2.CREATED: "created",
                donation_pb2.PENDING_PAYMENT: "pending_payment", 
                donation_pb2.PAYMENT_CONFIRMED: "payment_confirmed",
                donation_pb2.SHOWING_IN_OVERLAY: "showing_in_overlay",
                donation_pb2.COMPLETED: "completed",
                donation_pb2.CANCELLED: "cancelled"
            }
            
            result = {
                'payment_url': response.payment_url,
                'qr_code_url': response.qr_code_url,
                'nonce': response.nonce,
                'expires_at': response.expires_at,
                'status': status_names.get(response.status, "unknown")
            }
            
            logger.info(f"Создана ссылка для оплаты: {result['nonce']}")
            return result
            
        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при создании платежа: {e.code()} - {e.details()}")
            # Fallback - генерируем базовую ethereum ссылку
            fallback_amount_wei = int(amount * (10 ** 18))  # Предполагаем 18 decimals для fallback
            return {
                'payment_url': f"ethereum:{streamer_wallet}@1?value={fallback_amount_wei}&gas=21000",
                'qr_code_url': "",
                'nonce': f"fallback_{donation_id}",
                'expires_at': 0,
                'status': "error"
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании платежа: {str(e)}")
            # Fallback - генерируем базовую ethereum ссылку
            fallback_amount_wei = int(amount * (10 ** 18))  # Предполагаем 18 decimals для fallback
            return {
                'payment_url': f"ethereum:{streamer_wallet}@1?value={fallback_amount_wei}&gas=21000",
                'qr_code_url': "",
                'nonce': f"error_{donation_id}",
                'expires_at': 0,
                'status': "error"
            }
    
    def check_transaction_status(self, payment_url: str) -> dict:
        """
        Проверяет статус транзакции
        
        Returns:
            dict: {
                'confirmed': bool,
                'transaction_hash': str,
                'status': str,
                'error_message': str
            }
        """
        try:
            stub = self._get_stub()
            
            request = donation_pb2.CheckTransactionStatusRequest(
                payment_url=payment_url
            )
            
            response = stub.CheckTransactionStatus(request)
            
            status_names = {
                donation_pb2.CREATED: "created",
                donation_pb2.PENDING_PAYMENT: "pending_payment",
                donation_pb2.PAYMENT_CONFIRMED: "payment_confirmed", 
                donation_pb2.SHOWING_IN_OVERLAY: "showing_in_overlay",
                donation_pb2.COMPLETED: "completed",
                donation_pb2.CANCELLED: "cancelled"
            }
            
            return {
                'confirmed': response.confirmed,
                'transaction_hash': response.transaction_hash,
                'status': status_names.get(response.status, "unknown"),
                'error_message': response.error_message
            }
            
        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при проверке статуса: {e.code()} - {e.details()}")
            return {
                'confirmed': False,
                'transaction_hash': "",
                'status': "error",
                'error_message': f"gRPC ошибка: {e.details()}"
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка при проверке статуса: {str(e)}")
            return {
                'confirmed': False,
                'transaction_hash': "",
                'status': "error", 
                'error_message': f"Ошибка: {str(e)}"
            }
    
    def get_payment_qr_code(self, payment_url: str):
        """
        Gets QR code for payment
        
        Returns:
            GetQRCodeResponse object or None on error
        """
        try:
            stub = self._get_stub()
            
            request = donation_pb2.GetQRCodeRequest(
                payment_url=payment_url
            )
            
            response = stub.GetPaymentQRCode(request)
            return response
            
        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при получении QR кода: {e.code()} - {e.details()}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении QR кода: {str(e)}")
            return None
    
    def update_donation_status(self, nonce: str, status: str, transaction_hash: str = "") -> bool:
        """
        Updates donation status
        
        Args:
            nonce: Unique payment identifier
            status: New status ('created', 'pending_payment', 'payment_confirmed', etc.)
            transaction_hash: Transaction hash (optional)
            
        Returns:
            bool: True if update is successful
        """
        try:
            stub = self._get_stub()
            
            status_map = {
                "created": donation_pb2.CREATED,
                "pending_payment": donation_pb2.PENDING_PAYMENT,
                "payment_confirmed": donation_pb2.PAYMENT_CONFIRMED,
                "showing_in_overlay": donation_pb2.SHOWING_IN_OVERLAY,
                "completed": donation_pb2.COMPLETED,
                "cancelled": donation_pb2.CANCELLED
            }
            
            proto_status = status_map.get(status, donation_pb2.CREATED)
            
            request = donation_pb2.UpdateDonationStatusRequest(
                nonce=nonce,
                status=proto_status,
                transaction_hash=transaction_hash
            )
            
            response = stub.UpdateDonationStatus(request)
            
            if response.success:
                logger.info(f"Статус доната {nonce} обновлен на {status}")
            else:
                logger.error(f"Ошибка обновления статуса: {response.message}")
            
            return response.success
            
        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при обновлении статуса: {e.code()} - {e.details()}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обновлении статуса: {str(e)}")
            return False
    
    def close(self):
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None 