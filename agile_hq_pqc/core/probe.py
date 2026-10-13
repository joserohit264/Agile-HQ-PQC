"""Live environment probing: real loopback-socket RTT and host CPU.

A configurable StressInjector adds emulated congestion/CPU contention on top
of the real measurements so that stress scenarios are reproducible. The
injected component is always reported separately (never hidden).
"""
from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None


@dataclass
class StressInjector:
    """Emulated network + CPU contention (additive)."""
    rtt_ms: float = 0.0
    cpu_pct: float = 0.0
    jitter_ms: float = 0.0
    loss_pct: float = 0.0
    bw_mbps: float = 0.0     # 0 => unconstrained baseline link

    def set(self, rtt_ms=0.0, cpu_pct=0.0, jitter_ms=0.0, loss_pct=0.0, bw_mbps=0.0):
        self.rtt_ms, self.cpu_pct = float(rtt_ms), float(cpu_pct)
        self.jitter_ms, self.loss_pct = float(jitter_ms), float(loss_pct)
        self.bw_mbps = float(bw_mbps)

    def clear(self):
        self.set(0, 0, 0, 0, 0)

    def active(self) -> bool:
        return self.rtt_ms > 0 or self.cpu_pct > 0 or self.loss_pct > 0

    def to_dict(self) -> dict:
        return dict(rtt_ms=self.rtt_ms, cpu_pct=self.cpu_pct, jitter_ms=self.jitter_ms,
                    loss_pct=self.loss_pct, bw_mbps=self.bw_mbps)


STRESS_PRESETS = {
    "calm":     dict(rtt_ms=0,   cpu_pct=0,  jitter_ms=0,  loss_pct=0,   bw_mbps=0),
    "moderate": dict(rtt_ms=85,  cpu_pct=30, jitter_ms=5,  loss_pct=0.2, bw_mbps=20),
    "heavy":    dict(rtt_ms=125, cpu_pct=55, jitter_ms=10, loss_pct=0.5, bw_mbps=5),
    "severe":   dict(rtt_ms=150, cpu_pct=75, jitter_ms=15, loss_pct=1.0, bw_mbps=2),
}


class EchoServer(threading.Thread):
    """Tiny TCP echo server on 127.0.0.1 used for real RTT probes."""

    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self._stop = False

    def run(self):
        while not self._stop:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    @staticmethod
    def _serve(conn):
        with conn:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            while True:
                data = conn.recv(64)
                if not data:
                    return
                conn.sendall(data)

    def stop(self):
        self._stop = True
        try:
            self.sock.close()
        except OSError:
            pass


class Prober:
    """``deterministic=True`` replaces the live host measurements with fixed
    small baselines (0.2 ms RTT, 5 % CPU) so parallel / repeatable evaluation
    runs are not contaminated by the benchmark's own CPU load."""

    def __init__(self, stress: StressInjector | None = None, deterministic: bool = False):
        self.deterministic = deterministic
        self.stress = stress or StressInjector()
        self._echo = EchoServer()
        self._echo.start()
        self._client = socket.create_connection(("127.0.0.1", self._echo.port))
        self._client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if psutil:
            psutil.cpu_percent(None)

    def real_rtt_ms(self) -> float:
        if self.deterministic:
            return 0.2
        t0 = time.perf_counter()
        self._client.sendall(b"ping")
        self._client.recv(64)
        return (time.perf_counter() - t0) * 1000.0

    def real_cpu_pct(self) -> float:
        if self.deterministic:
            return 5.0
        return float(psutil.cpu_percent(None)) if psutil else 0.0

    def probe(self, rng=None) -> dict:
        """Return real + injected components and the totals the controller sees."""
        real_rtt, real_cpu = self.real_rtt_ms(), self.real_cpu_pct()
        jitter = 0.0
        if self.stress.jitter_ms and rng is not None:
            jitter = abs(rng.gauss(0, self.stress.jitter_ms))
        rtt = real_rtt + self.stress.rtt_ms + jitter
        cpu = min(100.0, real_cpu + self.stress.cpu_pct)
        return dict(rtt_ms=rtt, cpu_pct=cpu, real_rtt_ms=real_rtt,
                    real_cpu_pct=real_cpu, injected=self.stress.to_dict())

    def close(self):
        try:
            self._client.close()
        finally:
            self._echo.stop()
