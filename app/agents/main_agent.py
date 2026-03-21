import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.flight_agent import run_flight_agent
from app.agents.hotel_agent import run_hotel_agent


class HotelMainInput(BaseModel):
    city: str = Field(..., description="酒店城市英文名，例如 Bangkok")
    check_in: str = Field(..., description="入住日期，格式 YYYY-MM-DD")
    check_out: str = Field(..., description="退房日期，格式 YYYY-MM-DD")


MAIN_TO_HOTEL_INPUT_PARSER = JsonOutputParser(pydantic_object=HotelMainInput)


def _build_company_llm() -> ChatOpenAI:
    load_dotenv()
    return ChatOpenAI(
        model=os.getenv("COMPANY_LLM_MODEL", "gpt-4o-mini"),
        base_url=os.getenv("COMPANY_BASE_URL"),
        api_key=(os.getenv("COMPANY_API_KEY") or "").strip(),
        temperature=0,
    )


def _heuristic_parse_hotel_request(user_text: str) -> dict:
    city = "Bangkok"
    city_map = {
        "吉隆坡": "Kuala Lumpur",
        "槟城": "Penang",
        "曼谷": "Bangkok",
        "新加坡": "Singapore",
    }
    lowered = user_text.lower()
    for cn, en in city_map.items():
        if cn in user_text:
            city = en
            break
    if "kuala lumpur" in lowered:
        city = "Kuala Lumpur"
    if "penang" in lowered:
        city = "Penang"
    if "bangkok" in lowered:
        city = "Bangkok"
    if "singapore" in lowered:
        city = "Singapore"

    dates = re.findall(r"\d{4}-\d{2}-\d{2}", user_text)
    check_in = dates[0] if len(dates) > 0 else "2026-03-26"
    check_out = dates[1] if len(dates) > 1 else "2026-03-28"
    payload = {"city": city, "check_in": check_in, "check_out": check_out}
    return MAIN_TO_HOTEL_INPUT_PARSER.parse(json.dumps(payload, ensure_ascii=False))


def parse_natural_language_to_hotel_json(user_text: str) -> str:
    prompt = PromptTemplate(
        template=(
            "你是酒店请求参数解析器。\n"
            "把用户自然语言解析成酒店查询 JSON。\n"
            "只允许输出 JSON，不要输出其他文字。\n"
            "字段要求：city, check_in, check_out。\n"
            "city 使用英文城市名；日期格式必须是 YYYY-MM-DD。\n"
            "{format_instructions}\n"
            "用户输入：{query}\n"
        ),
        input_variables=["query"],
        partial_variables={"format_instructions": MAIN_TO_HOTEL_INPUT_PARSER.get_format_instructions()},
    )
    try:
        llm = _build_company_llm()
        chain = prompt | llm | MAIN_TO_HOTEL_INPUT_PARSER
        parsed_obj = chain.invoke({"query": user_text})
    except Exception:
        parsed_obj = _heuristic_parse_hotel_request(user_text)
    return json.dumps(parsed_obj, ensure_ascii=False)


def _build_flight_input_from_hotel_json(hotel_json: str) -> str:
    hotel_obj = json.loads(hotel_json)
    payload = {
        "departure_city": "Kuala Lumpur",
        "arrival_city": hotel_obj["city"],
        "departure_date": hotel_obj["check_in"],
        "passengers": 2,
        "budget": {
            "min": 1000,
            "max": 5000,
            "currency": "MYR",
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def _safe_json_loads(raw_text: str):
    try:
        return json.loads(raw_text)
    except Exception:
        return raw_text


def run_main_hotel_flow(user_text: str) -> str:
    hotel_json = parse_natural_language_to_hotel_json(user_text)
    hotel_output = run_hotel_agent(hotel_json)

    flight_input_json = _build_flight_input_from_hotel_json(hotel_json)
    flight_output = run_flight_agent(flight_input_json)

    merged = {
        "hotel_result": _safe_json_loads(hotel_output),
        "flight_result": _safe_json_loads(flight_output),
    }
    return json.dumps(merged, ensure_ascii=False, indent=2)


def main() -> None:
    user_text = input("请输入酒店需求（自然语言）: ").strip() or "我想订曼谷酒店，2026-03-26入住，2026-03-28退房"
    output = run_main_hotel_flow(user_text)
    print(output)


if __name__ == "__main__":
    main()
