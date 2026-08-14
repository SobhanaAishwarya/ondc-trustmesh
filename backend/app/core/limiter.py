"""The shared slowapi `Limiter` instance.

Lives in its own module (not `app/main.py`) so endpoint modules can import
it for `@limiter.limit(...)` decorators on specific routes (login,
registration) without a circular import — `main.py` imports the API
router, which imports the endpoint modules, which would need to import
`main.py` back to reach a limiter defined there.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
