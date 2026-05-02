import os
import json
import base64
from datetime import date
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import database


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
templates.env.globals["current_date"] = lambda: date.today().strftime("%A, %-d %B %Y")


@app.get("/", response_class=HTMLResponse)
async def today(request: Request):
    today_str = date.today().isoformat()
    today_fmt = date.today().strftime("%A, %d %B %Y")
    entries = database.get_day_entries(today_str)
    totals = database.get_day_totals(today_str)
    foods = database.get_all_foods()
    meals = database.get_all_meals()
    return templates.TemplateResponse(request=request, name="index.html", context={
        "today": today_str,
        "today_fmt": today_fmt,
        "entries": entries,
        "totals": totals,
        "foods": foods,
        "meals": meals,
        "protein_target": 200,
    })


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    days = database.get_history(30)
    return templates.TemplateResponse(request=request, name="history.html", context={
        "days": days,
        "protein_target": 200,
    })


@app.get("/meals", response_class=HTMLResponse)
async def meals_page(request: Request):
    meals = database.get_all_meals()
    foods = database.get_all_foods()
    return templates.TemplateResponse(request=request, name="meals.html", context={
        "meals": meals,
        "foods": foods,
    })


@app.post("/meals/add")
async def add_meal(name: str = Form(...)):
    database.add_meal(name)
    return RedirectResponse(url="/meals", status_code=303)


@app.post("/meals/delete/{meal_id}")
async def delete_meal(meal_id: int):
    database.delete_meal(meal_id)
    return RedirectResponse(url="/meals", status_code=303)


@app.post("/meals/{meal_id}/add-item")
async def add_meal_item(meal_id: int, food_id: int = Form(...), amount: float = Form(...)):
    database.add_meal_item(meal_id, food_id, amount)
    return RedirectResponse(url="/meals", status_code=303)


@app.post("/meals/{meal_id}/remove-item/{item_id}")
async def remove_meal_item(meal_id: int, item_id: int):
    database.remove_meal_item(item_id)
    return RedirectResponse(url="/meals", status_code=303)


@app.post("/meals/{meal_id}/log")
async def log_meal(meal_id: int):
    today_str = date.today().isoformat()
    database.log_meal(meal_id, today_str)
    return RedirectResponse(url="/", status_code=303)


@app.get("/foods", response_class=HTMLResponse)
async def foods_page(request: Request):
    foods = database.get_all_foods()
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return templates.TemplateResponse(request=request, name="foods.html", context={
        "foods": foods,
        "has_api_key": has_api_key,
    })


@app.post("/log/add")
async def add_log(
    food_id: int = Form(...),
    amount: float = Form(...),
    log_date: str = Form(...),
):
    database.add_log_entry(log_date, food_id, amount)
    return RedirectResponse(url="/", status_code=303)


@app.post("/log/delete/{entry_id}")
async def delete_log(entry_id: int):
    database.delete_log_entry(entry_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/log/clear")
async def clear_log(log_date: str = Form(...)):
    database.delete_all_log_entries(log_date)
    return RedirectResponse(url="/", status_code=303)


@app.post("/foods/add")
async def add_food(
    name: str = Form(...),
    unit_type: str = Form(...),
    unit_label: str = Form(...),
    default_amount: float = Form(...),
    calories: float = Form(0),
    protein: float = Form(0),
    fat: float = Form(0),
    sat_fat: float = Form(0),
    carbs: float = Form(0),
    sugar: float = Form(0),
    fibre: float = Form(0),
    calcium: float = Form(0),
    sodium: float = Form(0),
    notes: str = Form(""),
):
    database.add_food(name, unit_type, unit_label, default_amount,
                      calories, protein, fat, sat_fat, carbs, sugar, fibre, calcium, sodium, notes)
    return RedirectResponse(url="/foods", status_code=303)


@app.post("/foods/delete/{food_id}")
async def delete_food(food_id: int):
    database.delete_food(food_id)
    return RedirectResponse(url="/foods", status_code=303)


@app.post("/foods/from-photo")
async def food_from_photo(photo: UploadFile = File(...)):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse({"error": "ANTHROPIC_API_KEY not set"}, status_code=400)

    import anthropic

    image_data = await photo.read()
    image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
    media_type = photo.content_type or "image/jpeg"

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                },
                {
                    "type": "text",
                    "text": (
                        "Extract nutrition info from this food label. "
                        "Return ONLY a JSON object with these exact keys: "
                        "name (string), calories (kcal per 100g or per 100ml), "
                        "protein (g), fat (g), sat_fat (g), carbs (g), sugar (g), fibre (g), "
                        "calcium (mg), sodium (mg), "
                        "unit_type ('weight' or 'volume' or 'unit'), "
                        "unit_label ('g' or 'ml' or 'sachet' etc), "
                        "default_amount (typical serving size as number). "
                        "If calories are only in kJ divide by 4.184. "
                        "Return only valid JSON, no other text."
                    ),
                },
            ],
        }],
    )

    try:
        data = json.loads(response.content[0].text.strip())
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": f"Could not parse response: {e}"}, status_code=500)


@app.get("/api/food/{food_id}")
async def get_food_api(food_id: int):
    foods = database.get_all_foods()
    food = next((f for f in foods if f["id"] == food_id), None)
    if not food:
        raise HTTPException(status_code=404, detail="Not found")
    return food
