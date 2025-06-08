from fastapi import APIRouter, Query, Depends, HTTPException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid
import os
import re
from dotenv import load_dotenv
from openai import OpenAI

# 修正: 関連ファイルを正しく相対インポート
from ..database import SessionLocal
from ..models.product import Product

# --- Pydanticモデル定義 ---
class ProductUpdate(BaseModel):
    title_en: str
    price_usd: float

# --- OpenAIクライアントの初期化 ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- ルーターの初期化 ---
router = APIRouter()

# --- DBセッションを使うための共通関数 ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ヘルパー関数 ---
def _generate_english_title_from_japanese(japanese_title: str) -> str:
    """日本語タイトルからeBay向けの英語タイトルを生成する内部関数"""
    if not japanese_title or japanese_title == "タイトルが見つかりませんでした":
        return "" # 元のタイトルがなければ空文字を返す

    try:
        # プロンプトを再度修正
        prompt = (
            f"あなたは日本の商品を海外のeBayで販売するプロの出品者です。"
            f"以下の日本語の商品情報から、最も魅力的で正確な英語のタイトルを生成してください。\n"
            f"### 日本語の商品情報\n"
            f"{japanese_title}\n\n"
            f"### タイトル生成のルール\n"
            f"- 文字数は80文字以内に厳守。\n"
            f"- 商品の核心的な要素（例：'プロセカ', '東雲彰人', 'ぬいぐるみ'）を必ず含めること。\n"
            f"- 状態（New, Usedなど）、限定品（Limited, Rare）や日本からの発送（from Japan）といった、価値を高めるキーワードを適切に含める。\n"
            f"- カンマやピリオドは使用しない。\n\n"
            f"生成するタイトル："
        )

        chat_completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "あなたはeBayでの販売経験が豊富な、日本の商品に詳しい出品者です。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )
        english_title = chat_completion.choices[0].message.content.strip()
        
        # 念のため80文字に切り詰める
        if len(english_title) > 80:
            english_title = english_title[:80]

        return english_title

    except Exception as e:
        print(f"Error during title generation: {e}")
        return "" # エラー時も空文字を返す

# --- APIエンドポイント定義 ---

@router.get("/fetch-mercari")
def fetch_mercari(url: str = Query(..., description="メルカリの商品URL")):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.select_one("title").text.strip()
        description_tag = soup.select_one("meta[name='description']")
        description = description_tag["content"] if description_tag else "No description"
        images = [img["src"] for img in soup.select("img") if "https://static.mercdn.net/item/detail/" in img.get("src", "")]
        return {"title": title, "description": description, "images": images}
    except Exception as e:
        return {"error": str(e)}

# mercari.py の中の save_mercari_data 関数を置き換える

@router.post("/save-mercari")
def save_mercari_data(url: str = Query(..., description="メルカリURL"), db: Session = Depends(get_db)):
    """メルカリURLからSeleniumを使って情報を取得し、AIで英語タイトルを生成してDBに保存する"""
    
    # --- Seleniumでページを取得 ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless") # ブラウザ画面を表示しない
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Selenium WebDriverを起動
    # price.py と同じく、webdriver_manager を使って自動でドライバを管理
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(url)
        # JavaScriptがデータを読み込むのを3秒待つ
        time.sleep(3) 
        # 完全にレンダリングされた後のHTMLを取得
        html = driver.page_source
    finally:
        # 必ずブラウザを閉じる
        driver.quit()

    # --- BeautifulSoupで解析 ---
    soup = BeautifulSoup(html, "html.parser")

    # h1の見出しから商品名を取得
    name_element = soup.select_one('div[data-testid="name"] h1')
    
    # もし見出し(h1)から取得できた場合、それを優先して使う
    if name_element:
        title_jp = name_element.text.strip()
    else:
        # 万が一取得できなかった場合、予備として以前の<title>タグから取得する方法を使う
        title_tag = soup.select_one("title")
        raw_title = title_tag.text.strip() if title_tag else "タイトル取得失敗"
        # 予備の方法ではクリーニング処理を行う
        cleaned_title = raw_title.split(' - ')[0].split(' | ')[0]
        temp_title = cleaned_title.replace("メルカリ", "").strip()
        if temp_title:
            title_jp = temp_title
        else:
            title_jp = cleaned_title

    # AIで英語タイトルを生成
    title_en = _generate_english_title_from_japanese(title_jp)
    
    # 説明、価格、画像などを取得
    description_tag = soup.select_one("meta[name='description']")
    description = description_tag["content"] if description_tag else "No description"
    price_tag = soup.find("span", string=lambda text: text and "¥" in text)
    try:
        price = int(price_tag.text.replace("¥", "").replace(",", "").strip()) if price_tag else 0
    except:
        price = 0
    image_tags = soup.find_all("img")
    image_urls = list({img.get("src") for img in image_tags if img.get("src") and "mercdn.net" in img.get("src")})
    image_str = ",".join(image_urls)

    # データベースに保存
    product = Product(
        id=str(uuid.uuid4()),
        mercari_url=url,
        title_jp=title_jp,
        title_en=title_en,
        description_jp=description,
        description_en="",
        price_jpy=price,
        price_usd=0.0,
        condition_mercari="",
        condition_ebay_id=0,
        category_id="",
        images=image_str,
        stock_status="available",
        profit_rate=0.0,
        shipping_cost=0,
        exchange_rate=0.0
    )

    db.add(product)
    db.commit()

    return {
        "message": "保存しました",
        "id": product.id,
        "title_jp": title_jp,
        "generated_title_en": title_en
    }
    """メルカリURLからSeleniumを使って情報を取得し、AIで英語タイトルを生成してDBに保存する"""

    # --- Seleniumでページを取得 ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless") # ブラウザ画面を表示しない
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(url)
        # JavaScriptがデータを読み込むのを3秒待つ
        time.sleep(3) 
        # 完全にレンダリングされた後のHTMLを取得
        html = driver.page_source
    finally:
        # 必ずブラウザを閉じる
        driver.quit()

    # --- BeautifulSoupで解析 ---
    soup = BeautifulSoup(html, "html.parser")

    # h1の見出しから商品名を取得
    name_element = soup.select_one('div[data-testid="name"] h1')

    if name_element:
        title_jp = name_element.text.strip()
    else:
        # 万が一取得できなかった場合、予備として<title>タグから取得
        title_tag = soup.select_one("title")
        title_jp = title_tag.text.strip() if title_tag else "タイトル取得失敗"

    # AIで英語タイトルを生成
    title_en = _generate_english_title_from_japanese(title_jp)

    # 説明、価格、画像などを取得 (ここは変更なし)
    description_tag = soup.select_one("meta[name='description']")
    description = description_tag["content"] if description_tag else "No description"
    # (価格や画像の取得ロジックは、必要に応じてSelenium用に調整が必要になる可能性があります)
    price_tag = soup.find("span", string=lambda text: text and "¥" in text)
    try:
        price = int(price_tag.text.replace("¥", "").replace(",", "").strip()) if price_tag else 0
    except:
        price = 0
    image_tags = soup.find_all("img")
    image_urls = list({img.get("src") for img in image_tags if img.get("src") and "mercdn.net" in img.get("src")})
    image_str = ",".join(image_urls)

    # データベースに保存 (ここは変更なし)
    product = Product(
        id=str(uuid.uuid4()),
        mercari_url=url,
        title_jp=title_jp,
        title_en=title_en,
        description_jp=description,
        description_en="",
        price_jpy=price,
        price_usd=0.0,
        condition_mercari="",
        condition_ebay_id=0,
        category_id="",
        images=image_str,
        stock_status="available",
        profit_rate=0.0,
        shipping_cost=0,
        exchange_rate=0.0
    )

    db.add(product)
    db.commit()

    return {
        "message": "保存しました",
        "id": product.id,
        "title_jp": title_jp,
        "generated_title_en": title_en
    }

@router.get("/products")
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    result = []
    for p in products:
        result.append({
            "id": p.id,
            "title": p.title_jp,
            "price": p.price_jpy,
            "description": p.description_jp,
            "image_urls": p.images.split(",") if p.images else [],
            "item_specifics": {}
        })
    return result

@router.get("/products/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    return product

@router.put("/products/{product_id}")
def update_product(product_id: str, product_data: ProductUpdate, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    db_product.title_en = product_data.title_en
    db_product.price_usd = product_data.price_usd
    db.commit()
    db.refresh(db_product)
    return db_product

@router.delete("/products/{product_id}")
def delete_product(product_id: str, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="商品が見つかりません")
    db.delete(db_product)
    db.commit()
    return {"message": "商品を削除しました"}