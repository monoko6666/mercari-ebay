# 1. ベースとなるPythonの公式イメージを選択
FROM python:3.11-slim

# 2. 作業ディレクトリをコンテナ内に作成
WORKDIR /app

# 3. 必要なライブラリをインストール
# まずpip自体をアップグレード
RUN pip install --upgrade pip
# requirements.txtをコンテナにコピー
COPY ./requirements.txt /app/requirements.txt
# コピーしたrequirements.txtを元にライブラリをインストール
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# 4. プロジェクトの全ファイルをコンテナにコピー
# . は Dockerfile があるディレクトリ（backend/）を指す
COPY . /app

# 5. コンテナ起動時に実行するコマンド
# 0.0.0.0 を指定して、コンテナ外部からのアクセスを許可する
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]