from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# backend/models/product.py

from ..database import Base  # ✅ 相対パスに変更

from .models import product
from .routers import mercari, price, settings


# データベースのテーブル作成（初回のみ実行される）
product.Base.metadata.create_all(bind=engine)

# FastAPIアプリケーションの作成
app = FastAPI()

# フロントエンド（http://localhost:3000）からのリクエストを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターの登録
app.include_router(mercari.router)
app.include_router(price.router)
app.include_router(settings.router)  # ← これでOK！

@app.get("/")
def read_root():
    return {"message": "Mercari to eBay Auto Reseller is running!"}
