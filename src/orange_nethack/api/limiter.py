"""Rate limiter configuration (V7 security fix)."""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Create a global limiter instance
limiter = Limiter(key_func=get_remote_address)
