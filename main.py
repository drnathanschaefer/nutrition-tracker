import os
import json
import base64
from datetime import date
from database import today_local
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import database


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.globals["current_date"] = lambda: today_local().strftime("%A, %-d %B %Y")


@app.get("/", response_class=HTMLResponse)
async def today(request: Request):
    today_str = today_local().isoformat()
    today_fmt = today_local().strftime("%A, %d %B %Y")
    entries = database.get_day_entries(today_str)
    totals = database.get_day_totals(today_str)
    all_foods = database.get_all_foods()
    foods = [f for f in all_foods if not f.get("hidden", 0)]
    meals = database.get_all_meals()
    feedback = database.get_feedback(today_str)
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

    # Build per-slot data (5 slots)
    nutrient_keys = ["calories", "protein", "fat", "sat_fat", "carbs", "sugar", "fibre", "calcium", "sodium"]
    slots = {}
    for slot in range(1, 6):
        slot_entries = [e for e in entries if e.get("meal_slot", 1) == slot]
        if slot_entries:
            slot_totals = {k: round(sum(e[f"total_{k}"] for e in slot_entries), 1) for k in nutrient_keys}
            slots[slot] = {"entries": slot_entries, "totals": slot_totals}

    # Only show the 3 main meals in the quick-log section
    MAIN_MEALS = {"Breakfast", "Lunch with Couscous", "Lunch with Quinoa", "Walnuts - 30g + Brazil Nut"}
    log_meals = [m for m in meals if m["name"] in MAIN_MEALS]

    return templates.TemplateResponse(request=request, name="index.html", context={
        "today": today_str,
        "today_fmt": today_fmt,
        "entries": entries,
        "totals": totals,
        "slots": slots,
        "foods": foods,
        "meals": meals,
        "log_meals": log_meals,
        "feedback": feedback,
        "has_api_key": has_api_key,
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
async def log_meal(meal_id: int, meal_slot: int = Form(1)):
    today_str = today_local().isoformat()
    database.log_meal(meal_id, today_str, meal_slot)
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
    meal_slot: int = Form(1),
):
    database.add_log_entry(log_date, food_id, amount, meal_slot)
    return RedirectResponse(url="/", status_code=303)


@app.post("/log/delete/{entry_id}")
async def delete_log(entry_id: int):
    database.delete_log_entry(entry_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/feedback/generate")
async def generate_feedback(log_date: str = Form(...)):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse({"error": "API key not set"}, status_code=400)

    existing = database.get_feedback(log_date)
    if existing:
        return JSONResponse({"feedback": existing})

    totals = database.get_day_totals(log_date)
    if not any(v > 0 for v in totals.values()):
        return JSONResponse({"error": "No food logged for this day"}, status_code=400)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a concise nutrition coach reviewing someone's daily food log.
Their protein target is 200g/day.

Today's totals:
- Calories: {totals['calories']} kcal
- Protein: {totals['protein']}g (target: 200g)
- Carbs: {totals['carbs']}g (of which sugar: {totals['sugar']}g)
- Fat: {totals['fat']}g (sat fat: {totals['sat_fat']}g)
- Fibre: {totals['fibre']}g
- Sodium: {totals['sodium']}mg
- Calcium: {totals['calcium']}mg

Give exactly 3 lines using this format (include the emoji, nothing else):
✅ Win: [one specific positive, max 20 words]
⚠️ Watch: [one thing to be mindful of, max 20 words]
💡 Tomorrow: [one actionable suggestion, max 20 words]

Be specific, reference actual numbers, don't be preachy."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    feedback = response.content[0].text.strip()
    database.save_feedback(log_date, feedback)
    return JSONResponse({"feedback": feedback})


@app.get("/export")
async def export_day(date: str = None):
    if not date:
        date = today_local().isoformat()
    entries = database.get_day_entries(date)
    totals = database.get_day_totals(date)

    from datetime import datetime
    try:
        fmt_date = datetime.strptime(date, "%Y-%m-%d").strftime("%A, %-d %B %Y")
    except Exception:
        fmt_date = date

    lines = []
    lines.append(f"Daily Food Log — {fmt_date}")
    lines.append("=" * 50)

    if not entries:
        lines.append("\nNo food logged for this day.")
    else:
        nutrient_keys = ["calories", "protein", "fat", "sat_fat", "carbs", "sugar", "fibre", "calcium", "sodium"]
        slots = {}
        for e in entries:
            s = e.get("meal_slot", 1)
            slots.setdefault(s, []).append(e)

        for slot_num in sorted(slots):
            slot_entries = slots[slot_num]
            lines.append(f"\nMEAL {slot_num}")
            for e in slot_entries:
                lines.append(
                    f"  {e['name']} — {e['amount']}{e['unit_label']}  →  "
                    f"{e['total_calories']} kcal | {e['total_protein']}g protein | "
                    f"{e['total_carbs']}g carbs | {e['total_fat']}g fat"
                )
            slot_totals = {k: round(sum(e[f"total_{k}"] for e in slot_entries), 1) for k in nutrient_keys}
            lines.append(
                f"  ── Subtotal: {slot_totals['calories']} kcal | "
                f"{slot_totals['protein']}g protein | {slot_totals['carbs']}g carbs | "
                f"{slot_totals['fat']}g fat"
            )

    lines.append("\n" + "=" * 50)
    lines.append("DAILY TOTALS")
    lines.append(f"  Calories:  {totals['calories']} kcal")
    lines.append(f"  Protein:   {totals['protein']}g")
    lines.append(f"  Carbs:     {totals['carbs']}g  (sugar: {totals['sugar']}g)")
    lines.append(f"  Fat:       {totals['fat']}g  (sat fat: {totals['sat_fat']}g)")
    lines.append(f"  Fibre:     {totals['fibre']}g")
    lines.append(f"  Sodium:    {totals['sodium']}mg")
    lines.append(f"  Calcium:   {totals['calcium']}mg")
    lines.append("\nProtein target: 200g/day")

    text = "\n".join(lines)
    return JSONResponse({"text": text, "date": date})


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
