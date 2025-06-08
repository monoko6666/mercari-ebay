from fastapi import APIRouter, Query, Depends
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
import uuid

from database import SessionLocal
from models.product import Product

router = APIRouter()  # ← これが必要！！

# DBセッションを使うための共通関数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/fetch-mercari")
def fetch_mercari(url: str = Query(..., description="メルカリの商品URL")):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.select_one("title").text.strip()
        description_tag = soup.select_one("meta[name='description']")
        description = description_tag["content"] if description_tag else "No description"

        images = [img["src"] for img in soup.select("img") if "https://static.mercdn.net/item/detail/" in img.get("src", "")]

        return {
            "title": title,
            "description": description,
            "images": images
        }

    except Exception as e:
        return {"error": str(e)}

@router.post("/save-mercari")
def save_mercari_data(
    url: str = Query(..., description="メルカリURL"),
    db: Session = Depends(get_db)
):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    title = soup.select_one("title").text.strip()
    description_tag = soup.select_one("meta[name='description']")
    description = description_tag["content"] if description_tag else "No description"
    images = [img["src"] for img in soup.select("img") if "https://static.mercdn.net/item/detail/" in img.get("src", "")]
    image_str = ",".join(images)

    product = Product(
        id=str(uuid.uuid4()),
        mercari_url=url,
        title_jp=title,
        title_en="",
        description_jp=description,
        description_en="",
        price_jpy=0,
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

    return {"message": "保存しました", "id": product.id}

from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@router.post("/generate-title")
def generate_title(japanese_title: str = Query(..., description="日本語のタイトル")):
    import re

    try:
        prompt = (
    f"以下の商品名をもとに、eBay向けの商品タイトルを英語で生成してください。\n"
    f"制約条件:\n"
    f"- 文字数は必ず80文字以内（理想は73〜80文字）\n"
    f"- 以下のキーワードのうち **できるだけ多く** を自然な形で含める：Japan, New, Toy, Plush, gift\n"
    f"- ただし無理に詰め込まず、意味が通る範囲で使用してください\n"
    f"- ピリオド (.) やカンマ (,) は使わない\n"
    f"- 最後に「...」がつくような切り捨ては避ける\n"
    f"- タイトル全体を自然で購買意欲のある英語に\n"
    f"\n"
    f"日本語の商品名：{japanese_title}"
)


        chat_completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "あなたはeBay用の英語タイトル最適化の専門家です。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.5
        )

        raw_title = chat_completion.choices[0].message.content.strip()

        # 句読点を除去して単語単位で調整
        cleaned = re.sub(r"[.,]", "", raw_title)
        words = cleaned.split()
        keywords = ["Japan", "New", "Toy", "Plush", "gift"]

        # 本文 + 必須キーワードを追加して文字数調整
        result = ""
        for word in words:
            if len(result) + len(word) + (1 if result else 0) > 80:
                break
            result += (" " if result else "") + word

        # 末尾にキーワードを追加（既に含まれていないもの）
        existing = result.lower()
        for kw in keywords:
            if kw.lower() not in existing and len(result) + len(kw) + 1 <= 80:
                result += " " + kw

        # 最終調整：73文字未満であればキーワードで埋める
        while len(result) < 73:
            for kw in keywords:
                if len(result) + len(kw) + 1 <= 80:
                    result += " " + kw
            if len(result) >= 73:
                break

        return {"english_title": result.strip(), "char_count": len(result.strip())}

    except Exception as e:
        return {"error": str(e)}

from fastapi import Body
import uuid

# データ保存用の仮データベース（本番ではDBと接続）
saved_items = []

@router.post("/save-mercari")
def save_mercari_data(
    url: str = Query(..., description="メルカリURL"),
    db: Session = Depends(get_db)
):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    # タイトル
    title = soup.select_one("title").text.strip()

    # 説明
    description_tag = soup.select_one("meta[name='description']")
    description = description_tag["content"] if description_tag else "No description"

    # ✅ 価格（例：¥1,999）
    price_tag = soup.find("span", string=lambda text: text and "¥" in text)
    try:
        price = int(price_tag.text.replace("¥", "").replace(",", "").strip()) if price_tag else 0
    except:
        price = 0

    # ✅ 画像
    image_tags = soup.find_all("img")
    image_urls = list({
        img.get("src") for img in image_tags
        if img.get("src") and "mercdn.net" in img.get("src")
    })
    image_str = ",".join(image_urls)

    product = Product(
        id=str(uuid.uuid4()),
        mercari_url=url,
        title_jp=title,
        title_en="",
        description_jp=description,
        description_en="",
        price_jpy=price,  # ← 改善された価格
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
        "price": price,
        "image_count": len(image_urls)
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
            "description": p.description_jp,  # ← 追加
            "image_urls": p.images.split(",") if p.images else [],  # ← キー名も合わせる
            "item_specifics": {}  # ← 空でOK、後で埋める
        })
    return result

