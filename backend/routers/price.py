from fastapi import APIRouter, Query
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

router = APIRouter()

@router.post("/calculate-price")
def calculate_price(
    url: str = Query(..., description="メルカリの商品URL（仕入れ値を取得）"),
    shipping_cost: int = Query(..., description="送料（円）"),
    fee_rate: float = Query(..., description="販売手数料（%）例: 10 for 10%"),
    profit_rate: float = Query(..., description="利益率（%）例: 30 for 30%")
):
    try:
        # ヘッドレスChromeの起動
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)

        # ページが完全に読み込まれるまで待機（必要に応じて調整）
        time.sleep(2)

        # 価格の取得
        price_element = driver.find_element(By.CSS_SELECTOR, "div[data-testid='price'] span:nth-of-type(2)")
        price_text = price_element.text.replace(",", "").replace("¥", "").strip()

        if not price_text.isdigit():
            driver.quit()
            return {"error": "価格をテキストから抽出できませんでした。"}

        cost_price = int(price_text)

        # 計算処理
        total_cost = cost_price + shipping_cost
        fee = total_cost * (fee_rate / 100)
        profit = total_cost * (profit_rate / 100)
        selling_price = int(total_cost + fee + profit)

        driver.quit()

        return {
            "仕入れ値": cost_price,
            "送料": shipping_cost,
            "販売手数料": round(fee),
            "利益": round(profit),
            "推奨販売価格": selling_price
        }

    except Exception as e:
        return {"error": str(e)}
