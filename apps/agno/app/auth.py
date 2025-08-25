import jwt
import os
from typing import Optional
from fastapi import Request
from dotenv import load_dotenv
import requests

load_dotenv()

class UserInfo:
    def __init__(self, user_id: int, username: str | None = None, first_name: str | None = None, last_name: str | None = None):
        self.user_id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        
    def __str__(self):
        return f"User(id={self.user_id}, username={self.username})"

def _get_backend_base_url() -> str:
    """Базовый URL бэкенда Django внутри docker сети."""
    return os.getenv("API_URL") or os.getenv("BACKEND_URL") or "http://api:8000"


def _decode_token(access_token: str) -> Optional[dict]:
    """Декодирование JWT с использованием общего SECRET_KEY Django."""
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        print("❌ SECRET_KEY не найден в переменных окружения")
        return None
    try:
        payload = jwt.decode(
            access_token,
            secret_key,
            algorithms=['HS256'],
            options={"verify_signature": True}
        )
        return payload
    except jwt.ExpiredSignatureError:
        print("❌ JWT токен истек")
    except jwt.InvalidTokenError as e:
        print(f"❌ Недействительный JWT токен: {e}")
    except Exception as e:
        print(f"❌ Ошибка декодирования JWT: {e}")
    return None


def _fetch_user_details_with_token(access_token: str) -> Optional[dict]:
    """Получить детали пользователя с бэкенда по access token."""
    base_url = _get_backend_base_url().rstrip('/')
    url = f"{base_url}/api/users/me/"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"⚠️ Не удалось получить данные пользователя: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"⚠️ Ошибка запроса к бэкенду для получения пользователя: {e}")
    return None


def get_user_from_request(request: Request) -> Optional[UserInfo]:
    """Извлекаем информацию о пользователе из JWT токена (cookie или Authorization)."""
    try:
        # 1) Пытаемся взять токен из куки по основному имени (dj-rest-auth)
        access_token = request.cookies.get('access_token')
        # 2) Фолбэк на альтернативное имя, если настроено иначе
        if not access_token:
            access_token = request.cookies.get('auth.access_token')
        # 3) Фолбэк: Authorization: Bearer <token>
        if not access_token:
            auth_header = request.headers.get('Authorization') or request.headers.get('authorization')
            if auth_header and auth_header.lower().startswith('bearer '):
                access_token = auth_header.split(' ', 1)[1].strip()

        if not access_token:
            print("❌ JWT токен не найден ни в куки, ни в заголовках")
            return None

        payload = _decode_token(access_token)
        if not payload:
            return None

        user_id = payload.get('user_id')
        username = payload.get('username') or payload.get('user') or None

        # Если username отсутствует, попробуем забрать его из бэкенда
        user_details = None
        if not username and user_id:
            user_details = _fetch_user_details_with_token(access_token)
            if user_details:
                username = user_details.get('username') or username

        user_info = None
        if user_id:
            # Дополнительно пробуем first_name/last_name из user_details
            first_name = user_details.get('first_name') if user_details else None
            last_name = user_details.get('last_name') if user_details else None
            user_info = UserInfo(user_id=user_id, username=username, first_name=first_name, last_name=last_name)
            print(f"✅ Пользователь найден: {user_info}")
        else:
            print("❌ user_id не найден в JWT токене")
            return None

        return user_info

    except Exception as e:
        print(f"❌ Ошибка обработки JWT: {e}")
        return None

def extract_user_info_from_cookies(cookies: dict) -> Optional[UserInfo]:
    """Альтернативный метод для извлечения пользователя напрямую из куки."""
    access_token = cookies.get('access_token') or cookies.get('auth.access_token')
    if not access_token:
        return None
    try:
        payload = _decode_token(access_token)
        if not payload:
            return None
        user_id = payload.get('user_id')
        username = payload.get('username') or None
        if user_id:
            return UserInfo(user_id=user_id, username=username)
    except Exception:
        pass
    return None
