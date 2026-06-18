from slowapi import Limiter as _Limiter
from slowapi.util import get_remote_address

limiter = _Limiter(key_func=get_remote_address)
