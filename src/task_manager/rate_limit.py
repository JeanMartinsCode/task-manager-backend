"""Application-level rate limiting for write endpoints.

Defense in depth, not a replacement: in a real production deployment this
should be paired with rate limiting at the gateway/reverse-proxy layer
(nginx, an API gateway, Cloudflare, etc.), which is harder to bypass and
doesn't spend application CPU/memory per rejected request. This in-app
layer protects deployments that don't have such a layer yet, and acts as
a second line of defense for those that do.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Applies to POST/PUT/DELETE only — read endpoints are left unthrottled.
RATE_LIMIT_WRITE = os.getenv("RATE_LIMIT_WRITE", "20/minute")

limiter = Limiter(key_func=get_remote_address)
