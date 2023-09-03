# Storyzer
## run django
- 다음 명령어를 실행하여 서버를 실행합니다. 
- 괄호 안의 주소는 host:port이며 입력하지 않으면 localhost:8000. 
```
python manage.py runserver (0.0.0.0:7000)
```

## migrate
- models.py파일을 수정한 후, 다음 명령어를 실행하여 변경 사항을 데이터베이스에 마이그레이션합니다.
- models.py -> makemigrations -> migrate
```bash
python manage.py makemigrations
python manage.py migrate
```

## trouble shooting
- 다음 명령어를 실행하여 필요한 패키지를 설치합니다.
```bash
sudo apt-get install -y pkg-config default-libmysqlclient-dev gcc python3.11-dev build-essential
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```