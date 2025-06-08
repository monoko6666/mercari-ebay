from fastapi import APIRouter, Body, Depends
from typing import Dict
from sqlalchemy.orm import Session

# 新しくインポートする
from ..database import SessionLocal
from ..models.setting import Setting

router = APIRouter()

# DBセッションを使うための共通関数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/save-settings")
def save_settings(data: Dict[str, float] = Body(...), db: Session = Depends(get_db)):
    """受け取った設定をデータベースに保存・更新する"""
    # フロントエンドから送られてきた設定データ（data）を一つずつ処理
    for key, value in data.items():
        # データベースに同じキーの設定が既に存在するか確認
        db_setting = db.query(Setting).filter(Setting.key == key).first()
        
        if db_setting:
            # 存在すれば、そのレコードの値を更新
            db_setting.value = value
        else:
            # 存在しなければ、新しいレコードを作成
            db_setting = Setting(key=key, value=value)
            db.add(db_setting)
    
    # 加えた変更をすべてデータベースに保存（コミット）
    db.commit()
    
    # 保存後の現在の設定をDBから取得して返す
    all_settings = db.query(Setting).all()
    current_settings = {s.key: s.value for s in all_settings}
    return {"message": "設定を保存しました", "settings": current_settings}

@router.get("/get-settings")
def get_settings(db: Session = Depends(get_db)):
    """データベースから現在の設定をすべて取得する"""
    all_settings = db.query(Setting).all()
    
    # データベースのレコード（リスト形式）を、フロントエンドが使いやすい辞書形式に変換
    current_settings = {s.key: s.value for s in all_settings}
    
    # まだDBに保存されていないキーのデフォルト値を設定
    default_keys = ["shipping_cost", "fee_rate", "profit_rate"]
    for key in default_keys:
        if key not in current_settings:
            current_settings[key] = 0.0
            
    return current_settings