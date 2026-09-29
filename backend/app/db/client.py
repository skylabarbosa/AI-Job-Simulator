from functools import lru_cache
from typing import Any

import httpx
from supabase import Client, ClientOptions, create_client

from app.core.config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Any:
    """Create the server-side Supabase client when database access is needed."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for database access"
        )

    http_client = httpx.Client(
        http2=False,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        timeout=120,
    )
    client: Client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(httpx_client=http_client),
    )
    return client
