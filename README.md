# alpaca-bot

Python `discord.py`로 만든 Discord 봇입니다. 현재 `/ping` 명령에 `Pong!`으로 응답합니다.

`/run`은 별도 컨테이너에서 고정된 echo 명령을 실행하는 연결 확인용 명령입니다. `.env`에 `DISCORD_OWNER_ID=본인의_숫자_사용자_ID`를 설정해야 실행할 수 있습니다. 한 번에 한 작업만 허용하며 네트워크 없이 실행하고 30초, 메모리 128MB, CPU 0.5개로 제한합니다. 결과는 요청자에게만 보입니다.

작업 관리 컨테이너만 Docker 소켓을 사용합니다. Docker 소켓은 호스트 관리자 수준의 권한을 제공하므로 작업 관리자와 그 내부 네트워크는 신뢰할 수 있는 코드로만 운영해야 합니다. 작업 컨테이너에는 소켓이나 봇 토큰을 전달하지 않습니다.

## Docker로 실행

1. Discord Developer Portal에서 애플리케이션과 Bot을 만들고 Bot Token을 준비합니다.
2. `.env.example`을 `.env`로 복사한 뒤 `DISCORD_TOKEN`을 채웁니다.
3. 개발 서버에 명령을 바로 등록하려면 `DISCORD_GUILD_ID`에 해당 서버 ID를 설정합니다. 생략하면 명령을 전역으로 등록하며, Discord 반영까지 시간이 걸릴 수 있습니다.
4. Discord OAuth2 URL Generator에서 `bot`과 `applications.commands` 스코프를 선택해 봇을 서버에 초대합니다.
5. 실행합니다.

```sh
docker compose up -d --build
```

로그 확인:

```sh
docker compose logs -f bot
```

## 로컬 실행

Python 3.12 이상을 준비하고 의존성을 설치한 다음 `DISCORD_TOKEN`을 환경변수로 지정해 실행합니다.

```sh
python -m pip install -r requirements.txt
python main.py
```

봇은 서버 멤버 목록이나 메시지 내용을 읽지 않으므로 별도의 privileged intents는 필요하지 않습니다.
