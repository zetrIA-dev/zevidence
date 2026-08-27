import asyncio

from zevidence.application import InMemoryRepository


class YieldingInMemoryRepository(InMemoryRepository):
    """Expose the scheduling point that real async persistence introduces."""

    async def _before_run_insert(self) -> None:
        await asyncio.sleep(0)
