import asyncio
import aiohttp
from aiohttp import web
import os
import time
from kubernetes import config, client


CACHE_TTL = 5
NAMESPACE = os.environ['NAMESPACE']
KEYLESS_CONFIG_URL = os.environ['KEYLESS_CONFIG_URL']
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
                async with session.get(KEYLESS_CONFIG_URL, timeout=2, ssl=False) as resp:
                    if resp.status != 200:
                        return None
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
            if twpk in self.names_by_twpk:
                return self.names_by_twpk[twpk]
            truncated_twpk = twpk[:63]  # k8s label value length limit
            label_selector = f"twpk={truncated_twpk}"
            services = k8s_core.list_namespaced_service(namespace=NAMESPACE, label_selector=label_selector)
            if len(services.items) == 0:
                return None
            service_name = services.items[0].metadata.name
            self.names_by_twpk[twpk] = service_name
            return service_name


onchain_twpk_cache = OnchainTwpkCache()
service_name_cache = ServiceNameCache()


async def route_handler(request: web.Request) -> web.StreamResponse:
    path = request.match_info.get("path", "")
    print(f'path={path}', flush=True)
    path_segments = [segment for segment in path.split('/') if segment.strip() != '']
    if path_segments == []:
        return web.Response(text='''
Usage:
    to work with the currently on-chain circuit release, use path `./v0/prove`;
    to work with a specific circuit release, use path `./<circuit-release-twpk>/v0/prove`.
''')

    if path_segments == ['v0', 'prove']:
        target_twpk = await onchain_twpk_cache.get_or_fetch()
        if target_twpk is None:
            return web.json_response(
                text="Router could not fetch on-chain circuit release info.",
                status=500,
            )
        target_path_segments = path_segments
    else:
        target_twpk = path_segments[0]
        target_path_segments = path_segments[1:]

    print(f'target_twpk={target_twpk}', flush=True)
    service_name = await service_name_cache.get_or_fetch(target_twpk)
    if service_name is None:
        return web.json_response(
            text=f"Targeting the circuit release with twpk {target_twpk}, but no prover service deployment found for it",
            status=404,
        )
    target_base = f'http://{service_name}:8080'
    target_path = '/'.join(target_path_segments)
    target_url = f"{target_base}/{target_path}"
    print(f'target_url={target_url}')
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=dict(request.headers),
                    data=await request.read()
            ) as resp:
                print(f'CHECK1', flush=True)
                proxy_resp = web.StreamResponse(status=resp.status)
                excluded_headers = {
                    'Content-Length', 'Transfer-Encoding', 'Connection', 'Keep-Alive',
                    'Proxy-Authenticate', 'Proxy-Authorization', 'TE', 'Trailers',
                    'Upgrade'
                }
                for key, value in resp.headers.items():
                    if key not in excluded_headers:
                        proxy_resp.headers[key] = value
                print(f'CHECK2', flush=True)
                await proxy_resp.prepare(request)
                print(f'CHECK3', flush=True)
                async for chunk in resp.content.iter_chunked(1024):
                    await proxy_resp.write(chunk)
                print(f'CHECK4', flush=True)
                await proxy_resp.write_eof()
                print(f'CHECK5', flush=True)
                return proxy_resp
    except Exception as e:
        return web.json_response({"error": str(e)}, status=502)


async def healthcheck_handler(_request):
    return web.Response(text="ok")


app = web.Application()
app.router.add_get("/healthz", healthcheck_handler)
app.router.add_route("*", "/{path:.*}", route_handler)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
