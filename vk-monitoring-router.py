import asyncio
import aiohttp
from aiohttp import web
import os
import time
from kubernetes import config, client


CACHE_TTL = 5
CHAIN_NAME = os.environ['CHAIN_NAME']
NAMESPACE = os.environ['NAMESPACE']
config.load_incluster_config()
k8s_core = client.CoreV1Api()


class OnchainTwpkCache:
    def __init__(self):
        self.value = None
        self.last_update_time = 0
        self._lock = asyncio.Lock()

    async def get_or_fetch(self):
        async with self._lock:
            now = time.time()
            if now - self.last_update_time < CACHE_TTL: return self.value
            async with aiohttp.ClientSession() as session:
                async with session.get(f'https://prover.keyless.{CHAIN_NAME}.aptoslabs.com/cached/keyless-config', timeout=2) as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    self.value = data['data']['training_wheels_pubkey']['vec'][0]
                    self.last_update_time = now
        return self.value


class ServiceNameCache:
    def __init__(self):
        self.names_by_twpk = {}
        self.lock = asyncio.Lock()

    async def get_or_fetch(self, twpk):
        async with self.lock:
            if twpk in self.names_by_twpk: return self.names_by_twpk[twpk]
            label_selector = f"twpk={twpk}"
            services = k8s_core.list_namespaced_service(namespace=NAMESPACE, label_selector=label_selector)
            service_name = services.items[0].metadata.name
            self.names_by_twpk[twpk] = service_name
            return service_name


onchain_twpk_cache = OnchainTwpkCache()
service_name_cache = ServiceNameCache()


async def route_handler(request):
    path = request.match_info.get("path", "")
    onchain_twpk = await onchain_twpk_cache.get_or_fetch()
    service_name = await service_name_cache.get_or_fetch(onchain_twpk)
    target_base = f'http://{service_name}'
    target_url = f"{target_base}/{path}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=dict(request.headers),
                    data=await request.read()
            ) as resp:
                headers = dict(resp.headers)
                body = await resp.read()
                return web.Response(body=body, status=resp.status, headers=headers)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=502)


async def healthcheck_handler(_request):
    return web.Response(text="ok")


app = web.Application()
app.router.add_get("/healthz", healthcheck_handler)
app.router.add_route("*", "/{path:.*}", route_handler)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
