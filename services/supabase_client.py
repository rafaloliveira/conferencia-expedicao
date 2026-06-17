import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(override=True)

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar definidos no .env")
        _client = create_client(url, key)
    return _client
