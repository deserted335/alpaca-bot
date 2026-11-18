# alpaca-bot

Python `discord.py`로 만든 Discord 봇입니다. 현재 `/ping` 명령에 `Pong!`으로 응답합니다.

`/run`은 별도 컨테이너에서 고정된 echo 명령을 실행하는 연결 확인용 명령입니다. `.env`에 `DISCORD_OWNER_ID=본인의_숫자_사용자_ID`를 설정해야 실행할 수 있습니다. 한 번에 한 작업만 허용하며 네트워크 없이 실행하고 30초, 메모리 128MB, CPU 0.5개로 제한합니다. 결과는 요청자에게만 보입니다.

`/repo_test`는 공개 `deserted335/alpaca-bot` 저장소를 임시로 복제하고, 격리 컨테이너에서 README에 테스트용 문구를 추가하고 Python 문법을 검사합니다. 변경 diff를 요청자에게 보여주며 원본에는 반영하지 않습니다. 작업 관리자는 GitHub 접근이 필요하며, 작업 컨테이너에는 네트워크가 없습니다.

## Claude Code 로그인 준비

`docker compose --profile manual build claude`로 이미지를 만들고 `docker compose --profile manual run --rm claude auth login`으로 본인이 직접 Claude 구독 계정에 로그인합니다. 로그인 정보는 `claude-home` Docker 볼륨에 보관됩니다. Claude Code가 Anthropic에 접속하려면 네트워크가 필요합니다.

`/develop task:작업내용`은 소유자만 사용할 수 있습니다. GitHub 기본 브랜치를 새로 복제해 Claude Code가 수정하며, 결과를 patch 파일로 전달합니다. 변경은 자동으로 반영되지 않습니다. Claude의 Bash 도구는 비활성화하며 별도의 네트워크 없는 컨테이너에서 Python 문법 검사를 실행합니다. 이 검사는 프로젝트의 전체 테스트가 아닙니다. Claude 작업 컨테이너는 인증 볼륨과 인터넷에 접근할 수 있으므로 신뢰하는 저장소와 지시만 사용하세요. 최초 실행 전에 Claude 이미지를 빌드하고 로그인해야 합니다.

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

기본적으로 슬래시 명령 이름과 사용자·서버·채널 ID, 수신 메시지의 ID와 작성자·채널 ID를 로그에 기록합니다. 메시지 본문은 기본적으로 기록하지 않습니다. 본문을 확인하려면 Discord Developer Portal의 Bot 설정에서 **Message Content Intent**를 켜고 `.env`에 `LOG_MESSAGE_CONTENT=true`를 추가한 뒤 봇을 재시작하세요. 본문이 로그에 저장되므로 디버깅 후 끄는 것을 권합니다. 메시지 이벤트를 받으려면 봇에 해당 채널 보기 권한도 필요합니다.
