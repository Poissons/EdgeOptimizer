import json

import aiohttp
import asyncio
from aiohttp import FormData


async def main():
    async with aiohttp.ClientSession('http://localhost:4001') as session:
        data = FormData()
        observation = ["master", 10, {"master": {"18": {"success": 0, "failure": 1}, "16": {"success": 0, "failure": 1}, "2": {"success": 0, "failure": 1}, "11": {"success": 0, "failure": 1}, "3": {"success": 0, "failure": 1}, "19": {"success": 0, "failure": 2}, "20": {"success": 1, "failure": 2}}}, {"master": {"node1": {"15": 1, "20": 1}, "node2": {"16": 1, "18": 1}, "node3": {"17": 1, "19": 1}}, "mastera": {"nodea2": {"15": 1}, "nodea1": {"17": 1}}}, {"master": {"18": {"stuck": 1}, "20": {"stuck": 3}, "2": {"stuck": 1}, "11": {"stuck": 1}, "3": {"stuck": 1}, "16": {"stuck": 1}, "19": {"stuck": 2}}}, {"master": {"node1": {"cpu": {"percent": 75.0, "allocated": 6, "allocatable": 8}, "memory": {"percent": 34.95358194079156, "allocated": 2147483648, "allocatable": 6143815680}}, "node2": {"cpu": {"percent": 75.0, "allocated": 6, "allocatable": 8}, "memory": {"percent": 34.95353533467959, "allocated": 2147483648, "allocatable": 6143823872}}, "node3": {"cpu": {"percent": 75.0, "allocated": 6, "allocatable": 8}, "memory": {"percent": 34.95353533467959, "allocated": 2147483648, "allocatable": 6143823872}}}, "mastera": {"nodea1": {"cpu": {"percent": 75.0, "allocated": 3, "allocatable": 4}, "memory": {"percent": 23.550402068422155, "allocated": 1073741824, "allocatable": 4559335424}}, "nodea2": {"cpu": {"percent": 75.0, "allocated": 3, "allocatable": 4}, "memory": {"percent": 23.550402068422155, "allocated": 1073741824, "allocatable": 4559335424}}}}, 0]
        data.add_field('observation', json.dumps(observation))
        async with session.post('/predict', data=data) as resp:
            print(resp.url)
            print(await resp.text())


loop = asyncio.get_event_loop()
loop.run_until_complete(main())