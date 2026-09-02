"""Resolve the client IP every per-IP budget in this module is keyed on.

Direct/dev traffic uses the socket peer. When the immediate peer is a trusted
proxy (`TRUSTED_PROXY_CIDRS`), the address is the right-most `X-Forwarded-For`
hop *outside* the trusted CIDRs — the closest address a trusted proxy actually
vouches for. Left-most entries are client-supplied and forgeable; an untrusted
peer or a malformed header is ignored entirely.

Without the deploy's trusted-proxy config every request would resolve to the
edge's address and all traffic would share one bucket.
"""

import ipaddress
from collections.abc import Sequence


def resolve_client_ip(
    *,
    peer_host: str | None,
    x_forwarded_for: str | None,
    trusted_proxy_cidrs: Sequence[str],
) -> str:
    if peer_host is None:
        return "unknown"
    peer = _parse_ip(peer_host)
    if peer is None:
        return peer_host
    if x_forwarded_for and _is_trusted_proxy(peer, trusted_proxy_cidrs):
        hops: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        for part in x_forwarded_for.split(","):
            hop = _parse_ip(part.strip())
            if hop is None:
                # Malformed entry — distrust the whole header.
                return str(peer)
            hops.append(hop)
        for hop in reversed(hops):
            if not _is_trusted_proxy(hop, trusted_proxy_cidrs):
                return str(hop)
        if hops:
            # Every hop is a trusted proxy — the chain origin is the client.
            return str(hops[0])
    return str(peer)


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _is_trusted_proxy(
    peer: ipaddress.IPv4Address | ipaddress.IPv6Address,
    trusted_proxy_cidrs: Sequence[str],
) -> bool:
    for raw_cidr in trusted_proxy_cidrs:
        try:
            network = ipaddress.ip_network(raw_cidr, strict=False)
        except ValueError:
            continue
        if peer in network:
            return True
    return False
