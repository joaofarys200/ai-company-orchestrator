import asyncio
import sys

from dotenv import load_dotenv
from backend.logging_config import configure_structured_logging


class AnyThreadEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    def get_event_loop(self) -> asyncio.AbstractEventLoop:
        try:
            return super().get_event_loop()
        except RuntimeError:
            loop = self.new_event_loop()
            self.set_event_loop(loop)
            return loop


def configure_runtime_environment() -> None:
    if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure") and sys.stderr.encoding != "utf-8":
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    configure_structured_logging()
    asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())
    load_dotenv()
