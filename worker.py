import asyncio
import uuid

from aiohttp import web

lock = asyncio.Lock()


async def run(request: web.Request) -> web.Response:
    if lock.locked():
        return web.json_response({"message": "다른 작업이 실행 중입니다."}, status=409)
    async with lock:
        name = "alpaca-job-" + uuid.uuid4().hex
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "run", "--name", name, "--network", "none",
                "--memory", "128m", "--cpus", "0.5", "--pids-limit", "32",
                "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--user", "65534:65534", "alpine:3.21", "echo", "Hello from alpaca job!",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            output = (stdout if process.returncode == 0 else stderr).decode(errors="replace")[-1500:]
            return web.json_response({"message": f"종료 코드: {process.returncode}\n```\n{output}\n```"})
        except (TimeoutError, OSError):
            return web.json_response({"message": "작업 실행에 실패했거나 30초 제한을 초과했습니다."}, status=500)
        finally:
            if process and process.returncode is None:
                process.kill()
                await process.wait()
            cleanup = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", name,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await cleanup.wait()


app = web.Application()
app.router.add_post("/run", run)
web.run_app(app, host="0.0.0.0", port=8080)
