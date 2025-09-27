# code structure

```
study-timer-project/
├── app_fix.py              # 👈 메인 Flask 앱 (이름 변경 불필요)
├── requirements.txt        # 👈 Python 종속성 목록
├── credentials.json        # 👈 Google Sheets 인증 정보 (gitignore에 추가 권장!)
├── templates/              # 👈 Flask 템플릿 폴더 (HTML 파일)
│   ├── index.html
│   └── multi.html
├── .gitignore
└── Procfile                # 👈 [추가 필요] 서버 실행 명령어를 정의 (Heroku/Render 등 사용)

```
