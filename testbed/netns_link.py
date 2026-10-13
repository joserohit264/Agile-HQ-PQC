"""Two Linux network namespaces joined by a veth pair, with kernel token-bucket
(tbf) bandwidth shaping on both directions.

Requires root / CAP_NET_ADMIN and `pip install pyroute2`. No `ip`/`tc` binaries needed.
Kernel netem (delay/loss) is NOT assumed: many minimal kernels lack it. Propagation
delay is therefore injected by the receiver (see run_testbed.py) and loss is not modelled.
"""
from __future__ import annotations

import os
from pyroute2 import IPRoute, NetNS, netns

NS_A, NS_B = "pqcA", "pqcB"
IP_A, IP_B = "10.9.0.1", "10.9.0.2"
QUEUE_US = 100_000          # tbf queue limit expressed as max queueing delay (100 ms)


def _rm():
    for n in (NS_A, NS_B):
        try:
            netns.remove(n)
        except Exception:
            pass


def setup():
    _rm()
    for n in (NS_A, NS_B):
        netns.create(n)
    ipr = IPRoute()
    ipr.link("add", ifname="vA", kind="veth", peer={"ifname": "vB"})
    for ifn, n in (("vA", NS_A), ("vB", NS_B)):
        ipr.link("set", index=ipr.link_lookup(ifname=ifn)[0], net_ns_fd=n)
    ipr.close()
    for n, ifn, ip in ((NS_A, "vA", IP_A), (NS_B, "vB", IP_B)):
        ns = NetNS(n)
        idx = ns.link_lookup(ifname=ifn)[0]
        ns.addr("add", index=idx, address=ip, prefixlen=24)
        ns.link("set", index=idx, state="up")
        ns.link("set", index=ns.link_lookup(ifname="lo")[0], state="up")
        ns.close()
    set_rate(None)


def set_rate(mbps: float | None):
    """Shape both directions to `mbps` (None => effectively unshaped 1 Gbit)."""
    rate = "1000000kbit" if not mbps else f"{int(mbps * 1000)}kbit"
    # Small bucket (~2 jiffies of tokens, min 1700 B ~ 1 MTU) so each packet is paced at link rate.
    # A large burst would let a 5 KB packet cross at line rate and make the "constrained" link a no-op.
    rate_bps = (mbps or 1000) * 1e6
    burst = max(1700, int(rate_bps / 8 / 250))
    for n, ifn in ((NS_A, "vA"), (NS_B, "vB")):
        ns = NetNS(n)
        idx = ns.link_lookup(ifname=ifn)[0]
        ns.tc("replace", "tbf", idx, "1:", rate=rate, burst=burst, latency=QUEUE_US)
        ns.close()


def enter(name: str):
    """Move the calling thread into namespace `name` (threads created afterwards inherit it)."""
    fd = os.open(f"/var/run/netns/{name}", os.O_RDONLY)
    try:
        os.setns(fd, os.CLONE_NEWNET)
    finally:
        os.close(fd)


def teardown():
    _rm()
