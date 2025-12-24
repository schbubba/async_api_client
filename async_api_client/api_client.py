from typing import Optional, Dict, Type, TypeVar, Any, Callable
import aiohttp
import asyncio

T = TypeVar("T")

class ApiClient:
    def __init__(self, base_url: str | None = None, headers: Dict[str, str] | None = None, timeout: int | float = 60):
        self.base_url = base_url
        self.headers = headers if headers else {}
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self, base_url: str | None = None, headers: Dict[str, str] | None = None, timeout: int | float = 60):
        self.base_url = base_url if base_url else self.base_url
        self.headers = headers if headers else self.headers
        self.timeout = timeout if timeout else self.timeout

        if self.session:
            await self.session.close()
            self.session = None

        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))

    async def shutdown(self):
        if self.session:
            await self.session.close()
            self.session = None

    # --------------------------
    # Regular GET/POST
    # --------------------------
    async def get(self, url: str, return_type: Type[T] | None = None, headers: Dict[str, str] | None = None, timeout: int | float | None = None) -> Optional[T]:
        return await self._request("GET", url, return_type, headers, None, timeout)

    async def post(self, url: str, body: Any = None, return_type: Type[T] | None = None, headers: Dict[str, str] | None = None, timeout: int | float | None = None) -> Optional[T]:
        return await self._request("POST", url, return_type, headers, body, timeout)

    # --------------------------
    # Internal request helper
    # --------------------------
    async def _request(self, method: str, url: str, return_type: Type[T] | None = None, headers: Dict[str, str] | None = None, body: Any = None, timeout: int | float | None = None) -> Optional[T]:
        if not self.session:
            raise RuntimeError("ApiClient not initialized")

        req_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else self.session.timeout

        # Base URL
        if self.base_url and not url.startswith("http"):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

        # Merge headers
        req_headers = self.headers.copy()
        if headers:
            req_headers.update(headers)

        async with self.session.request(method=method, url=url, json=body if method != "GET" else None, headers=req_headers, timeout=req_timeout) as resp:
            if resp.content_type == "application/json":
                data = await resp.json()
                if return_type:
                    return return_type.from_dict(data)
                return data
            else:
                return await resp.text()

    # --------------------------
    # Streaming GET/POST
    # --------------------------
    async def stream_get(self, url: str, chunk_callback: Callable[[str], Any], headers: Dict[str, str] | None = None, timeout: int | float | None = None):
        await self._stream("GET", url, chunk_callback, headers, None, timeout)

    async def stream_post(self, url: str, body: Any, chunk_callback: Callable[[str], Any], headers: Dict[str, str] | None = None, timeout: int | float | None = None):
        await self._stream("POST", url, chunk_callback, headers, body, timeout)

    async def _stream(self, method: str, url: str, chunk_callback: Callable[[str], Any], headers: Dict[str, str] | None = None, body: Any = None, timeout: int | float | None = None):
        if not self.session:
            raise RuntimeError("ApiClient not initialized")

        req_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else self.session.timeout

        if self.base_url and not url.startswith("http"):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

        req_headers = self.headers.copy()
        if headers:
            req_headers.update(headers)

        async with self.session.request(method=method, url=url, json=body if method != "GET" else None, headers=req_headers, timeout=req_timeout) as resp:
            async for raw_chunk in resp.content.iter_any(1024):  # 1 KB chunks
                text = raw_chunk.decode("utf-8").strip()
                if text:
                    result = chunk_callback(text)
                    if asyncio.iscoroutine(result):
                        await result
