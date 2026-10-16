"""Measure what Déjà costs on this PC: records your real screen for a few minutes into a
throwaway folder, then prints CPU, memory, time per screen read and disk per screen,
and deletes everything it recorded.

    python bench.py 180      # seconds, default 120
"""
import shutil
import sys
import tempfile
import time

import mss
import numpy as np
import psutil

from deja import capture
from deja.store import Store


def main(seconds=120):
    home = tempfile.mkdtemp(prefix="deja-bench-")
    try:
        store = Store(home)
        engine = capture.ocr_engine()
        with mss.MSS() as s:
            bgr = np.asarray(s.grab(s.monitors[1]))[:, :, :3]
        engine(bgr)  # warm up
        t0 = time.perf_counter()
        for _ in range(3):
            capture.read(engine, bgr)
        ocr_ms = (time.perf_counter() - t0) / 3 * 1000
        del engine

        me = psutil.Process()
        capture.lower_priority()
        rec = capture.Recorder(store, capture.Settings(f"{home}/settings.json"))
        rec.start()
        me.cpu_percent()
        samples, peak = [], 0
        for _ in range(seconds):
            time.sleep(1)
            samples.append(me.cpu_percent() / psutil.cpu_count())
            peak = max(peak, me.memory_info().rss)
        n = store.stats()["frames"]
        disk = store.stats()["mb"]
        if rec.state.startswith("error"):
            sys.exit(f"the recorder failed, so these numbers would be wrong: {rec.state}")
        print(f"screen {bgr.shape[1]}x{bgr.shape[0]}, {psutil.cpu_count()} logical CPUs")
        print(f"one screen read: {ocr_ms:.0f} ms")
        print(f"over {seconds}s: {n} screens kept, CPU {np.mean(samples):.1f}% average "
              f"(of the whole machine), {max(samples):.0f}% peak, memory {peak / 2**20:.0f} MB")
        print(f"disk: {disk} MB, about {disk / max(n, 1) * 1024:.0f} KB per screen kept")
    finally:
        store.db.close()
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)
