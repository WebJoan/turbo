from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


PROM_BASE_URL = "https://office.promelec.ru/"


class PromAuthError(Exception):
    """Исключение при неуспешной авторизации на office.promelec.ru"""


@dataclass
class PromSession:
    """Результат успешной авторизации: cookie-словарь и заголовок Cookie."""

    cookies: Dict[str, str]
    cookie_header: str
    user_agent: str


def _cookie_header_from_jar(cookies: Dict[str, str]) -> str:
    parts = [f"{name}={value}" for name, value in cookies.items()]
    return "; ".join(parts)


class PromClient:
    """
    Асинхронный клиент для авторизации на office.promelec.ru и работы в одной браузерной сессии.

    Использует Playwright для навигации/POST и BeautifulSoup для валидации HTML-ответа.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 20000,
        user_agent: Optional[str] = None,
    ) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._user_agent_override = user_agent

        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> "PromClient":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self._headless)
        context_kwargs = {
            "locale": "ru-RU",
        }
        if self._user_agent_override:
            context_kwargs["user_agent"] = self._user_agent_override
        self._context = await self._browser.new_context(**context_kwargs)
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self._timeout_ms)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if self._context is not None:
                await self._context.close()
        finally:
            try:
                if self._browser is not None:
                    await self._browser.close()
            finally:
                if self._pw is not None:
                    await self._pw.stop()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Client is not started. Use 'async with PromClient(...) as c:'")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Client is not started. Use 'async with PromClient(...) as c:'")
        return self._context

    async def login_and_get_session(self, username: str, password: str) -> PromSession:
        """
        Логинится на PROM2PROM и возвращает cookies активной сессии.

        Поля формы согласно наблюдению сети:
          - login_reg
          - password_reg
          - autorize = "form_login"
          - url = "/"

        Если логин/пароль неверные, в HTML присутствует строка:
        "Авторизация не пройдена. (xW004)" — это отслеживается через BeautifulSoup.
        """

        # 1) Заходим на главную, чтобы получить первоначальные куки/скрипты
        await self.page.goto(PROM_BASE_URL, wait_until="domcontentloaded")

        # 2) Ожидаем поля формы и заполняем
        await self.page.wait_for_selector("input[name=login_reg]")
        await self.page.fill("input[name=login_reg]", username)
        await self.page.fill("input[name=password_reg]", password)

        # 3) Готовимся перехватить ответ POST логина (на тот же домен)
        def _is_login_post(response) -> bool:
            try:
                return (
                    response.request.method.upper() == "POST"
                    and response.url.startswith(PROM_BASE_URL)
                )
            except Exception:
                return False

        # Некоторые формы могут сабмититься кнопкой с type=submit
        # Также встречается скрытый input[name=autorize][value=form_login] и input[name=url][value=/]
        # Эти поля отправятся автоматически при сабмите формы.
        async with self.page.expect_response(_is_login_post) as response_info:
            # Пробуем клик по первой кнопке submit в форме авторизации
            submit_locator = self.page.locator("form button[type=submit], form input[type=submit]").first
            if await submit_locator.count() == 0:
                # fallback: нажмём Enter в поле пароля
                await self.page.press("input[name=password_reg]", "Enter")
            else:
                await submit_locator.click()

        resp = await response_info.value
        await self.page.wait_for_load_state("domcontentloaded")
        html = await self.page.content()

        # 4) Парсим HTML и проверяем наличие ошибки авторизации
        soup = BeautifulSoup(html, "lxml")
        text_all = soup.get_text(" ", strip=True)
        if "Авторизация не пройдена" in text_all or "xW004" in text_all:
            raise PromAuthError("Авторизация не пройдена. (xW004)")

        # 5) Собираем cookies активной сессии
        jar = await self.context.cookies(PROM_BASE_URL)
        cookies_dict: Dict[str, str] = {c["name"]: c["value"] for c in jar}
        cookie_header = _cookie_header_from_jar(cookies_dict)

        # user-agent может пригодиться для последующих запросов
        ua = await self.page.evaluate("() => navigator.userAgent")

        return PromSession(cookies=cookies_dict, cookie_header=cookie_header, user_agent=ua)

    async def get_and_parse(self, url: str) -> Tuple[str, BeautifulSoup]:
        """GET страница в рамках текущей авторизованной сессии и вернуть (html, soup)."""
        await self.page.goto(url, wait_until="domcontentloaded")
        html = await self.page.content()
        return html, BeautifulSoup(html, "lxml")


# Пример использования (для справки):
# async def _demo():
#     async with PromClient(headless=True) as client:
#         session = await client.login_and_get_session("user", "pass")
#         html, soup = await client.get_and_parse("https://office.promelec.ru/")
# asyncio.run(_demo())


