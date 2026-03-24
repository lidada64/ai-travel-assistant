import json
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agents.flight_agent import run_flight_agent
from app.agents.hotel_agent import run_hotel_agent
from app.tests.test_attraction_agent import run_tool_flow


class Budget(BaseModel):
    min: float = Field(..., ge=0)
    max: float = Field(..., ge=0)
    currency: str = Field(default="CNY")


class TimeRange(BaseModel):
    start_date: str
    end_date: str


class GenerateItineraryRequest(BaseModel):
    departure: str
    destination: list[str]
    pax: int = Field(..., ge=1)
    budget: Budget
    time: TimeRange
    must_visit_attractions: list[str] | None = None


def _safe_parse_json(raw: Any):
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("`", "").strip()


def _summarize_output(user_input: str, flights: list, hotels: list, views: list) -> str:
    parts: list[str] = []
    if user_input:
        parts.append(f"需求：{_clean_text(user_input)}")
    if flights:
        f = flights[0] or {}
        title = _clean_text((f.get("name") or "") + " " + (f.get("code") or ""))
        route = _clean_text(f.get("departure_airport") or "") + " → " + _clean_text(f.get("arrival_airport") or "")
        parts.append(f"机票：{title}（{route}）")
    if hotels:
        h = hotels[0] or {}
        parts.append(f"酒店：{_clean_text(h.get('name'))}（{_clean_text(h.get('location'))}）")
    if views:
        names = [ _clean_text(v.get("name")) for v in views[:3] if isinstance(v, dict) ]
        if names:
            parts.append(f"推荐景点：{', '.join(names)}")
    if not parts:
        return "已生成行程。"
    return "；".join([p for p in parts if p])


def _build_standard_payload(req: GenerateItineraryRequest | None, user_input: str, flight_result, hotel_result, view_result) -> dict:
    flight_item = flight_result.get("flight") if isinstance(flight_result, dict) else None
    flights = [flight_item] if flight_item else []

    hotels = []
    if isinstance(hotel_result, list):
        hotels = hotel_result
    elif isinstance(hotel_result, dict) and isinstance(hotel_result.get("hotels"), list):
        hotels = hotel_result.get("hotels", [])

    normalized_hotels = []
    for item in hotels:
        if not isinstance(item, dict):
            continue
        if item.get("error"):
            normalized_hotels.append(
                {
                    "name": "",
                    "location": "",
                    "arrive_date": _clean_text(req.time.start_date) if req else "",
                    "leave_date": _clean_text(req.time.end_date) if req else "",
                    "price": 0.0,
                    "rating": 0.0,
                    "map_source": "",
                    "hotel_source": _clean_text(item.get("error")),
                }
            )
            continue
        normalized_hotels.append(
            {
                "name": _clean_text(item.get("name")),
                "location": _clean_text(item.get("location")),
                "arrive_date": _clean_text(item.get("arrive_date")),
                "leave_date": _clean_text(item.get("leave_date")),
                "price": float(item.get("price", 0) or 0),
                "rating": float(item.get("rating", 0) or 0),
                "map_source": _clean_text(item.get("map_source")),
                "hotel_source": _clean_text(item.get("hotel_source")),
            }
        )

    attractions = view_result.get("results", []) if isinstance(view_result, dict) else []
    normalized_views = []
    for index, item in enumerate(attractions):
        if not isinstance(item, dict):
            continue
        arrival_hour = 9 + index
        departure_hour = 12 + index
        normalized_views.append(
            {
                "name": _clean_text(item.get("attraction_name")),
                "location": _clean_text(item.get("attraction_location")),
                "information": "",
                "price": float(item.get("attraction_price", 0) or 0),
                "open_time": _clean_text(item.get("attraction_open_time")),
                "arrival_time": f"{req.time.start_date}T{arrival_hour:02d}:00:00" if req else "",
                "departure_time": f"{req.time.start_date}T{departure_hour:02d}:00:00" if req else "",
                "visit_duration": _clean_text(item.get("attraction_estimated_visit_time")),
                "image": "",
            }
        )

    output_text = _summarize_output(user_input, flights, normalized_hotels, normalized_views)

    return {
        "code": 200,
        "message": "success",
        "data": {
            "input": _clean_text(user_input),
            "output": output_text,
            "flights": flights,
            "hotels": normalized_hotels,
            "views": normalized_views,
        },
    }


app = FastAPI(title="AI Travel Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True, "ts": datetime.utcnow().isoformat() + "Z"}


@app.post("/api/v1/agent/generate_itinerary")
def generate_itinerary(payload: Dict[str, Any] = Body(...)):
    try:
        text_input = _clean_text(payload.get("input"))
        if text_input:
            req = None
            city = payload.get("destination", [None])[0] or ""
            check_in = payload.get("time", {}).get("start_date") or ""
            check_out = payload.get("time", {}).get("end_date") or ""

            hotel_request_json = json.dumps(
                {"city": city, "check_in": check_in, "check_out": check_out},
                ensure_ascii=False,
            )
            flight_request_json = json.dumps(
                {
                    "departure_city": "",
                    "arrival_city": city,
                    "departure_date": check_in,
                    "passengers": payload.get("pax", 1),
                    "budget": payload.get("budget") or {},
                },
                ensure_ascii=False,
            )
            view_request_json = json.dumps(
                {"location": city or text_input, "type": "tourist_attraction"},
                ensure_ascii=False,
            )

            hotel_result = _safe_parse_json(run_hotel_agent(hotel_request_json))
            flight_result = _safe_parse_json(run_flight_agent(flight_request_json))
            view_result = _safe_parse_json(run_tool_flow(view_request_json))

            return _build_standard_payload(req, text_input, flight_result, hotel_result, view_result)
        else:
            req = GenerateItineraryRequest(**payload)
            if not req.destination:
                return {"code": 400, "message": "destination is required", "data": {"flights": [], "hotels": [], "views": []}}

            city = req.destination[0]

            hotel_request_json = json.dumps(
                {"city": city, "check_in": req.time.start_date, "check_out": req.time.end_date},
                ensure_ascii=False,
            )
            flight_request_json = json.dumps(
                {
                    "departure_city": req.departure,
                    "arrival_city": city,
                    "departure_date": req.time.start_date,
                    "passengers": req.pax,
                    "budget": req.budget.model_dump(),
                },
                ensure_ascii=False,
            )
            view_request_json = json.dumps(
                {"location": city, "type": "tourist_attraction"},
                ensure_ascii=False,
            )

            hotel_result = _safe_parse_json(run_hotel_agent(hotel_request_json))
            flight_result = _safe_parse_json(run_flight_agent(flight_request_json))
            view_result = _safe_parse_json(run_tool_flow(view_request_json))

            return _build_standard_payload(req, "", flight_result, hotel_result, view_result)
    except Exception as e:
        return {
            "code": 500,
            "message": str(e),
            "data": {"input": "", "output": "", "flights": [], "hotels": [], "views": []},
        }

