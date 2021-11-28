# Copyright 2021 John Reese
# Licensed under the MIT License

import asyncio
import sys
import unittest

if __name__ == "__main__":
    if sys.platform == "win32" and sys.version_info < (3, 8):
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    unittest.main("thx.tests", verbosity=1)
