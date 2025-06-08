from fastapi import APIRouter, Body
from typing import Dict

router = APIRouter()

# 仮想的な保存場所（本来はDBなど）
current_settings = {
    "shipping_cost": 0,
    "fee_rate": 0.0,
    "profit_rate": 0.0
}

@router.post("/save-settings")
def save_settings(data: Dict[str, float] = Body(...)):
    current_settings.update(data)
    return {"message": "設定を保存しました", "settings": current_settings}

@router.get("/get-settings")
def get_settings():
    return current_settings

