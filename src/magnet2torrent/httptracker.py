import asyncio
import struct
from ipaddress import IPv4Address
from urllib.parse import quote

import aiohttp
from yarl import URL

from . import settings
from .bencode import bdecode


async def retrieve_peers_http_tracker(task_registry, tracker, infohash):
    url = f"{tracker}?info_hash={quote(infohash)}&peer_id={quote(settings.PEER_ID)}&port=0&uploaded=0&downloaded=0&left=0&compact=1"
    failed = False
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        try:
            async with session.get(URL(url, encoded=True)) as response:
                task = asyncio.ensure_future(response.read())
                task_registry.add(task)
                result = await task
                if response.status != 200:
                    failed = True
                task_registry.remove(task)
        except (
            aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError,
            asyncio.CancelledError,
        ):
            failed = True

    if failed:
        return tracker, {"seeders": 0, "leechers": 0, "peers": []}

    result = bdecode(result)

    peer_data = result[b"peers"]
    peers = []
    while peer_data:
        peer_ip, peer_port = struct.unpack("!IH", peer_data[:6])
        peers.append((IPv4Address(peer_ip), peer_port))
        peer_data = peer_data[6:]

    return (
        tracker,
        {
            "seeders": result[b"complete"],
            "leechers": result[b"incomplete"],
            "peers": peers,
        },
    )