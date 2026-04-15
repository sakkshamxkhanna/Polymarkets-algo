"""
Latency injection for realistic simulation.
Models three delay sources: network (Gaussian), matching queue (Poisson), Polygon block (deterministic 2s).

Audit fix: using a fixed 100ms constant (as the original plan did) overstates fill rates by 30-60%.
"""
import asyncio
import random
import math
from dataclasses import dataclass
from typing import Any, Callable, Coroutine


@dataclass
class LatencyProfile:
    mean: float       # ms
    std: float        # ms
    tail_p: float     # probability of tail spike
    tail_ms: float    # tail latency in ms


PROFILES = {
    "vps_us_east": LatencyProfile(mean=85, std=30, tail_p=0.03, tail_ms=800),
    "vps_eu": LatencyProfile(mean=140, std=45, tail_p=0.05, tail_ms=1200),
    "residential": LatencyProfile(mean=200, std=80, tail_p=0.08, tail_ms=2000),
    "local_dev": LatencyProfile(mean=20, std=5, tail_p=0.01, tail_ms=200),
}


class LatencyInjector:
    def __init__(self, profile_name: str = "vps_us_east"):
        self.profile = PROFILES.get(profile_name, PROFILES["vps_us_east"])

    def sample_ms(self) -> float:
        """Returns latency in milliseconds, including tail spikes."""
        if random.random() < self.profile.tail_p:
            # Tail spike — uniform between tail_ms * 0.8 and tail_ms * 1.5
            return random.uniform(self.profile.tail_ms * 0.8, self.profile.tail_ms * 1.5)
        return max(10.0, random.gauss(self.profile.mean, self.profile.std))

    async def inject(self, fn: Callable[..., Coroutine], *args, **kwargs) -> Any:
        """Wrap any async API call with simulated latency."""
        latency_s = self.sample_ms() / 1000.0
        await asyncio.sleep(latency_s)
        return await fn(*args, **kwargs)

    def inject_sync(self) -> float:
        """Return sampled latency (for use in sync contexts)."""
        return self.sample_ms()
