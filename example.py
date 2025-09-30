"""
Пример использования OCR сервиса
"""
import base64
import json
import sys
from pathlib import Path

import requests


def process_receipt(image_path: str, api_url: str = "http://localhost:8000") -> dict:
    """
    Отправить изображение чека на распознавание
    
    Args:
        image_path: Путь к изображению
        api_url: URL OCR сервиса
        
    Returns:
        Результат распознавания
    """
    # Читаем изображение и конвертируем в base64
    image_file = Path(image_path)
    
    if not image_file.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    print(f"📸 Reading image: {image_path}")
    with open(image_file, "rb") as f:
        image_bytes = f.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    print(f"📦 Image size: {len(image_bytes) / 1024:.2f} KB")
    print(f"🚀 Sending request to {api_url}/api/v1/ocr/receipt")
    
    # Отправляем запрос
    response = requests.post(
        f"{api_url}/api/v1/ocr/receipt",
        json={
            "image": image_base64,
            "options": {}
        },
        timeout=30
    )
    
    # Проверяем ответ
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.json())
        return None
    
    result = response.json()
    
    # Выводим результат
    print(f"\n✅ Success!")
    print(f"⏱️  Processing time: {result['processing_time_ms']}ms")
    print(f"📊 Confidence: {result['confidence']:.2%}")
    print(f"🔧 OCR Engine: {result['ocr_engine_used']}")
    
    if result.get("receipt"):
        receipt = result["receipt"]
        
        print("\n🏪 Store:")
        store = receipt.get("store", {})
        if store.get("name"):
            print(f"   Name: {store['name']}")
        if store.get("inn"):
            print(f"   INN: {store['inn']}")
        if store.get("address"):
            print(f"   Address: {store['address']}")
        
        print("\n🛒 Items:")
        items = receipt.get("items", [])
        if items:
            total_items = 0
            for item in items:
                print(f"   - {item['name']}: {item['total']} руб")
                total_items += 1
            print(f"   Total items: {total_items}")
        else:
            print("   No items found")
        
        print("\n💰 Totals:")
        totals = receipt.get("totals", {})
        if totals.get("total"):
            print(f"   Total: {totals['total']} руб")
        if totals.get("payment_method"):
            print(f"   Payment: {totals['payment_method']}")
        
        print("\n📅 Metadata:")
        metadata = receipt.get("metadata", {})
        if metadata.get("date"):
            print(f"   Date: {metadata['date']}")
        if metadata.get("receipt_type"):
            print(f"   Type: {metadata['receipt_type']}")
    
    return result


def main():
    """Точка входа"""
    if len(sys.argv) < 2:
        print("Usage: python example.py <path_to_receipt_image>")
        print("Example: python example.py receipt.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    api_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    
    try:
        result = process_receipt(image_path, api_url)
        
        # Сохраняем результат в файл
        if result:
            output_file = Path(image_path).stem + "_result.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Full result saved to: {output_file}")
    
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Cannot connect to OCR service at {api_url}")
        print("Make sure the service is running: python run.py")
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
