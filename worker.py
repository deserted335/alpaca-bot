import asyncio
import os
import tempfile
import uuid
from pathlib import Path

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


async def command(*args: str, timeout: int = 60) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise
    return process.returncode, output.decode(errors="replace")


async def repo_test(request: web.Request) -> web.Response:
    if lock.locked():
        return web.json_response({"message": "다른 작업이 실행 중입니다."}, status=409)
    async with lock:
        name = "alpaca-job-" + uuid.uuid4().hex
        try:
            with tempfile.TemporaryDirectory(prefix="alpaca-") as tmp:
                repo = Path(tmp) / "repo"
                code, output = await command("git", "clone", "--depth", "1", "https://github.com/deserted335/alpaca-bot.git", str(repo))
                if code:
                    return web.json_response({"message": "저장소 복제 실패:\n" + output[-1200:]}, status=500)
                script = "cp -R /work /tmp/repo && printf '\\n<!-- alpaca test -->\\n' >> /tmp/repo/README.md && python -m py_compile /tmp/repo/main.py && echo 'Python syntax: OK'"
                code, output = await command("docker", "create", "--name", name, "--network", "none", "--memory", "256m", "--cpus", "0.5", "--pids-limit", "64", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65534:65534", "python:3.12-slim", "sh", "-c", script)
                if code:
                    return web.json_response({"message": "컨테이너 생성 실패:\n" + output[-1200:]}, status=500)
                code, output = await command("docker", "cp", str(repo), name + ":/work")
                if code:
                    return web.json_response({"message": "파일 복사 실패:\n" + output[-1200:]}, status=500)
                code, output = await command("docker", "start", "-a", name, timeout=30)
                if code:
                    return web.json_response({"message": f"테스트 실패 ({code}):\n{output[-1200:]}"}, status=500)
                code, copy_output = await command("docker", "cp", name + ":/tmp/repo/README.md", str(repo / "README.md"))
                if code:
                    return web.json_response({"message": "결과 복사 실패:\n" + copy_output[-1200:]}, status=500)
                _, diff = await command("git", "-C", str(repo), "diff", "--", "README.md")
                return web.json_response({"message": f"테스트 결과: {output.strip()}\n변경 내용:\n```diff\n{diff[-1200:]}\n```"})
        except (asyncio.TimeoutError, OSError):
            return web.json_response({"message": "작업 실행 오류 또는 시간 초과"}, status=500)
        finally:
            await command("docker", "rm", "-f", name, timeout=15)


app.router.add_post("/repo-test", repo_test)


async def develop(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        task = data.get("task", "").strip()
        if not isinstance(task, str) or not 1 <= len(task) <= 1500:
            raise ValueError
    except (ValueError, AttributeError):
        return web.json_response({"message": "작업 지시는 1~1500자로 입력해 주세요."}, status=400)
    if lock.locked():
        return web.json_response({"message": "다른 작업이 실행 중입니다."}, status=409)
    async with lock:
        name = "alpaca-dev-" + uuid.uuid4().hex
        test_name = name + "-test"
        try:
            with tempfile.TemporaryDirectory(prefix="alpaca-dev-") as tmp:
                repo = Path(tmp) / "repo"
                code, output = await command("git", "clone", "--depth", "1", "https://github.com/deserted335/alpaca-bot.git", str(repo))
                if code:
                    return web.json_response({"message": "저장소 복제 실패: " + output[-1000:]}, status=500)
                script = 'cp -R /source /tmp/repo && cd /tmp/repo && exec claude -p --permission-mode acceptEdits --tools Read,Edit,Write,Glob,Grep --max-turns 20 -- "$1"'
                code, output = await command("docker", "create", "--name", name, "--memory", "1g", "--cpus", "1", "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "-v", os.getenv("CLAUDE_VOLUME", "alpaca-bot_claude-home") + ":/home/claude", "--entrypoint", "sh", os.getenv("CLAUDE_IMAGE", "alpaca-bot-claude"), "-c", script, "sh", task)
                if code:
                    return web.json_response({"message": "Claude 컨테이너 생성 실패: " + output[-1000:]}, status=500)
                code, output = await command("docker", "cp", str(repo), name + ":/source")
                if code:
                    return web.json_response({"message": "저장소 전달 실패: " + output[-1000:]}, status=500)
                code, output = await command("docker", "start", "-a", name, timeout=420)
                if code:
                    return web.json_response({"message": f"Claude 실행 실패 ({code}):\n{output[-1400:]}"}, status=500)
                result = Path(tmp) / "result"
                code, copy_output = await command("docker", "cp", name + ":/tmp/repo", str(result))
                if code:
                    return web.json_response({"message": "결과 회수 실패: " + copy_output[-1000:]}, status=500)
                git = ("git", "-c", "safe.directory=*", "-C", str(result))
                code, git_output = await command(*git, "add", "-N", "--all")
                if code:
                    return web.json_response({"message": "변경 분석 실패: " + git_output[-1000:]}, status=500)
                code, diff = await command(*git, "diff", "--no-ext-diff", "--binary")
                if code or len(diff.encode()) > 7_000_000:
                    return web.json_response({"message": "변경 내용을 생성할 수 없거나 7MB를 초과했습니다."}, status=500)
                test_code, test_output = await command("docker", "create", "--name", test_name, "--network", "none", "--memory", "256m", "--cpus", "0.5", "--pids-limit", "64", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65534:65534", "-e", "PYTHONPYCACHEPREFIX=/tmp/pycache", "python:3.12-slim", "python", "-m", "compileall", "-q", "/work")
                if not test_code:
                    test_code, test_output = await command("docker", "cp", str(result), test_name + ":/work")
                if not test_code:
                    test_code, test_output = await command("docker", "start", "-a", test_name, timeout=30)
                test_summary = "Python 문법 검사 통과" if test_code == 0 else "Python 문법 검사 실패 또는 실행 불가: " + test_output[-500:]
                return web.json_response({"message": f"Claude 작업 완료. {test_summary}\n{output[-1000:]}", "diff": diff})
        except (asyncio.TimeoutError, OSError):
            return web.json_response({"message": "작업 실행 오류 또는 시간 초과"}, status=500)
        finally:
            for container in (name, test_name):
                try:
                    await command("docker", "rm", "-f", container, timeout=15)
                except (asyncio.TimeoutError, OSError):
                    pass


app.router.add_post("/develop", develop)
web.run_app(app, host="0.0.0.0", port=8080)
