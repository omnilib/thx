# Copyright 2022 Amethyst Reese
# Licensed under the MIT License

import asyncio
import logging
import sys
import unittest

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    if sys.platform == "win32" and sys.version_info < (3, 8):
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    unittest.main("thx.tests", verbosity=2)
