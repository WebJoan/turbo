import jwt
import os
from typing import Optional
from fastapi import Request
from dotenv import load_dotenv

load_dotenv()

class UserInfo:
    def __init__(self, user_id: int, username: str = None):
        self.user_id = user_id
        self.username = username
        
    def __str__(self):
        return f"User(id={self.user_id}, username={self.username})"

def get_user_from_request(request: Request) -> Optional[UserInfo]:
    """Извлекаем информацию о пользователе из JWT токена в куки"""
    try:
        # Получаем JWT токен из куки
        cookies = request.cookies
        access_token = cookies.get('auth.access_token')
        
        if not access_token:
            print("❌ JWT токен не найден в куки")
            return None
            
        # Используем тот же SECRET_KEY что и Django
        secret_key = os.getenv('SECRET_KEY')
        if not secret_key:
            print("❌ SECRET_KEY не найден в переменных окружения")
            return None
        
        # Расшифровываем JWT токен
        payload = jwt.decode(
            access_token, 
            secret_key, 
            algorithms=['HS256'],
            options={"verify_signature": True}
        )
        
        user_id = payload.get('user_id')
        if user_id:
            user_info = UserInfo(user_id=user_id)
            print(f"✅ Пользователь найден: {user_info}")
            return user_info
        else:
            print("❌ user_id не найден в JWT токене")
            return None
            
    except jwt.ExpiredSignatureError:
        print("❌ JWT токен истек")
        return None
    except jwt.InvalidTokenError as e:
        print(f"❌ Недействительный JWT токен: {e}")
        return None
    except Exception as e:
        print(f"❌ Ошибка обработки JWT: {e}")
        return None

def extract_user_info_from_cookies(cookies: dict) -> Optional[UserInfo]:
    """Альтернативный метод для извлечения пользователя напрямую из куки"""
    access_token = cookies.get('auth.access_token')
    if not access_token:
        return None
        
    try:
        secret_key = os.getenv('SECRET_KEY')
        if not secret_key:
            return None
            
        payload = jwt.decode(access_token, secret_key, algorithms=['HS256'])
        user_id = payload.get('user_id')
        
        if user_id:
            return UserInfo(user_id=user_id)
    except:
        pass
    
    return None
