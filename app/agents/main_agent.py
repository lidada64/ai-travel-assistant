import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.flight_agent import run_flight_agent
from app.agents.hotel_agent import run_hotel_agent
from app.agents.attraction_seed_agent import run_seed_agent
from app.agents.transportation_agent import run_travel_agent


class _BudgetModel(BaseModel):
    min: int = Field(default=0)
    max: int = Field(default=10000)
    currency: str = Field(default="MYR")


class _HotelRequestModel(BaseModel):
    city: str = Field(..., description="英文城市名")
    check_in: str = Field(..., description="YYYY-MM-DD")
    check_out: str = Field(..., description="YYYY-MM-DD")


class _FlightRequestModel(BaseModel):
    departure_city: str = Field(default="Shenzhen")
    arrival_city: str = Field(..., description="与酒店城市一致")
    departure_date: str = Field(..., description="与入住日期一致")
    passengers: int = Field(default=1)
    budget: _BudgetModel = Field(default_factory=_BudgetModel)


class _AttractionTaskModel(BaseModel):
    task: str = Field(default="search_attractions")
    agent: str = Field(default="attraction_seed_agent")
    destination: str = Field(..., description="与酒店城市一致")
    query: str = Field(..., description="形如 Top attractions in {city}")


class _DispatchPlanModel(BaseModel):
    hotel_request: _HotelRequestModel
    flight_request_outbound: _FlightRequestModel = Field(..., description="去程机票请求")
    flight_request_inbound: _FlightRequestModel = Field(..., description="返程机票请求")
    attraction_task: _AttractionTaskModel


_DISPATCH_PARSER = JsonOutputParser(pydantic_object=_DispatchPlanModel)


def _build_google_llm() -> ChatGoogleGenerativeAI:
    load_dotenv()
    return ChatGoogleGenerativeAI(
        model=os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash"),
        api_key=(os.getenv("GOOGLE_API_KEY") or "").strip(),
        temperature=0,
    )


def _build_fallback_dispatch_plan(user_text: str) -> dict:
    hotel_request_json = parse_natural_language_to_hotel_json(user_text)
    hotel_request = json.loads(hotel_request_json)
    
    flight_request_outbound = {
        "departure_city": "Shenzhen",
        "arrival_city": hotel_request["city"],
        "departure_date": hotel_request["check_in"],
        "passengers": 1,
        "budget": {"min": 0, "max": 10000, "currency": "MYR"},
    }
    
    flight_request_inbound = {
        "departure_city": hotel_request["city"],
        "arrival_city": "Shenzhen",
        "departure_date": hotel_request["check_out"],
        "passengers": 1,
        "budget": {"min": 0, "max": 10000, "currency": "MYR"},
    }
    
    attraction_dispatch_task = _build_attraction_dispatch_task(hotel_request_json)
    return {
        "hotel_request": hotel_request,
        "flight_request_outbound": flight_request_outbound,
        "flight_request_inbound": flight_request_inbound,
        "attraction_task": attraction_dispatch_task,
    }


def _dispatch_user_request_by_company(user_text: str) -> dict:
    prompt = PromptTemplate(
        template=(
            "你是旅行主调度 AI。\n"
            "你的唯一任务是把用户自然语言转换为 JSON 分发计划。\n"
            "只输出 JSON，不要输出任何解释。\n"
            "约束：\n"
            "1) hotel_request.city 必须是英文城市名。\n"
            "2) hotel_request.check_in / check_out 必须是 YYYY-MM-DD。\n"
            "3) flight_request_outbound.departure_city 必须等于用户提到的出发城市，默认 Shenzhen。\n"
            "4) flight_request_outbound.arrival_city 必须等于 hotel_request.city。\n"
            "5) flight_request_outbound.departure_date 必须等于 hotel_request.check_in。\n"
            "6) flight_request_inbound.departure_city 必须等于 hotel_request.city。\n"
            "7) flight_request_inbound.arrival_city 必须等于 flight_request_outbound.departure_city。\n"
            "8) flight_request_inbound.departure_date 必须等于 hotel_request.check_out。\n"
            "9) passengers 根据用户输入，默认为 1。\n"
            "10) budget 根据用户输入，默认 min=0,max=10000,currency=MYR。\n"
            "11) attraction_task 固定 task=search_attractions, agent=attraction_seed_agent。\n"
            "12) attraction_task.destination 必须等于 hotel_request.city。\n"
            "13) attraction_task.query 必须是 Top attractions in {{city}}。\n"
            "如果用户缺失日期，使用默认 2026-03-26 和 2026-03-28。\n"
            "{format_instructions}\n"
            "用户输入：{query}\n"
        ),
        input_variables=["query"],
        partial_variables={"format_instructions": _DISPATCH_PARSER.get_format_instructions()},
    )
    try:
        chain = prompt | _build_google_llm() | _DISPATCH_PARSER
        result = chain.invoke({"query": user_text})
        return _DISPATCH_PARSER.parse(json.dumps(result, ensure_ascii=False))
    except Exception:
        return _build_fallback_dispatch_plan(user_text)


def parse_natural_language_to_hotel_json(user_text: str) -> str:
    city = "Seoul"  # 默认城市改为 Seoul 方便测试
    city_map = {
        "吉隆坡": "Kuala Lumpur",
        "槟城": "Penang",
        "曼谷": "Bangkok",
        "新加坡": "Singapore",
        "首尔": "Seoul",
        "北京": "Beijing",
        "上海": "Shanghai",
        "芭提雅": "Pattaya"
    }
    lowered = (user_text or "").lower()
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
    if "seoul" in lowered:
        city = "Seoul"
    if "beijing" in lowered:
        city = "Beijing"
    if "shanghai" in lowered:
        city = "Shanghai"
    if "pattaya" in lowered:
        city = "Pattaya"

    dates = re.findall(r"\d{4}[-.]\d{1,2}[-.]\d{1,2}", user_text or "")
    # Normalize dates to YYYY-MM-DD
    normalized_dates = []
    for d in dates:
        parts = re.split(r"[-.]", d)
        if len(parts) == 3:
            normalized_dates.append(f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}")
    
    check_in = normalized_dates[0] if len(normalized_dates) > 0 else "2026-05-01"
    check_out = normalized_dates[1] if len(normalized_dates) > 1 else "2026-05-04"
    return json.dumps({"city": city, "check_in": check_in, "check_out": check_out}, ensure_ascii=False)


def _build_flight_input(hotel_request_json: str) -> str:
    hotel_request = json.loads(hotel_request_json)
    flight_request = {
        "departure_city": "Shenzhen",  # 改为与示例一致的出发地
        "arrival_city": hotel_request["city"],
        "departure_date": hotel_request["check_in"],
        "passengers": 1,               # 改为与示例一致的人数
        "budget": {
            "min": 0,
            "max": 10000,              # 改为与示例一致的预算
            "currency": "MYR",         # 统一改为 MYR
        },
    }
    return json.dumps(flight_request, ensure_ascii=False)


def _safe_parse_json(raw):
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _clean_text(value):
    if value is None:
        return ""
    return str(value).replace("`", "").strip()


def _parse_price_to_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return 0.0

    lowered = text.lower()
    if lowered in {"free", "免费"}:
        return 0.0

    cleaned = (
        text.replace(",", "")
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .replace("to", "-")
    )
    nums = re.findall(r"\d+(?:\.\d+)?", cleaned)
    if not nums:
        return 0.0

    try:
        return float(nums[0])
    except Exception:
        return 0.0


def _build_view_input(hotel_request_json: str) -> str:
    hotel_request = json.loads(hotel_request_json)
    return json.dumps(
        {
            "location": hotel_request["city"],
            "type": "tourist_attraction",
        },
        ensure_ascii=False,
    )


def _build_attraction_dispatch_task(hotel_request_json: str) -> dict:
    hotel_request = json.loads(hotel_request_json)
    city = hotel_request.get("city", "")
    return {
        "task": "search_attractions",
        "agent": "attraction_seed_agent",
        "destination": city,
        "query": f"Top attractions in {city}",
    }


def _build_standard_payload(hotel_request_json: str, flight_result, hotel_result, view_result, transport_result=None, user_text: str = "", output_text: str = "") -> dict:
    hotel_request = json.loads(hotel_request_json)
    flights = []
    if isinstance(flight_result, dict):
        if isinstance(flight_result.get("flights"), list):
            flights = [item for item in flight_result.get("flights", []) if isinstance(item, dict)]
        elif isinstance(flight_result.get("flight"), dict):
            flights = [flight_result.get("flight")]

    hotels = []
    if isinstance(hotel_result, list):
        hotels = hotel_result
    elif isinstance(hotel_result, dict) and isinstance(hotel_result.get("hotels"), list):
        hotels = hotel_result.get("hotels", [])
        
    # 根据需求，只返回第一个酒店结果
    if len(hotels) > 0:
        hotels = [hotels[0]]
        
    normalized_hotels = []
    for item in hotels:
        if not isinstance(item, dict):
            continue
        if item.get("error"):
            normalized_hotels.append(
                {
                    "name": "",
                    "location": "",
                    "arrive_date": _clean_text(hotel_request.get("check_in")),
                    "leave_date": _clean_text(hotel_request.get("check_out")),
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

    attractions = []
    if isinstance(view_result, dict):
        if isinstance(view_result.get("results"), list):
            attractions = view_result.get("results", [])
        elif isinstance(view_result.get("attractions"), list):
            attractions = view_result.get("attractions", [])
        elif isinstance(view_result.get("travel_plan"), list):
            # 处理 travel_plan_agent 返回的结构: {"travel_plan": [{"day": 1, "date": "...", "route": [{"name": "...", ...}]}]}
            for day_plan in view_result.get("travel_plan", []):
                if isinstance(day_plan, dict) and isinstance(day_plan.get("route"), list):
                    for route_item in day_plan.get("route", []):
                        if isinstance(route_item, dict):
                            # 为了让后面的 _clean_text(item.get("attraction_name") or item.get("name")) 能抓到名字
                            if "name" in route_item and "attraction_name" not in route_item:
                                route_item["attraction_name"] = route_item["name"]
                            attractions.append(route_item)
    elif isinstance(view_result, dict) and "views" in view_result:
        # 直接处理 travel_plan_agent 返回的 {"views": [...]} 结构
        attractions = view_result.get("views", [])
    elif isinstance(view_result, dict) and "travel_plan" in view_result:
        # 兼容可能有 travel_plan 的情况
        attractions = view_result.get("travel_plan", [])
    elif isinstance(view_result, dict):
        # 兼容直接返回的可能是字典格式但没有标准 key 的情况
        if "views" in view_result:
             attractions = view_result["views"]
        else:
             # 有些时候 LLM 可能返回字符串格式的 JSON
             pass
    elif isinstance(view_result, list):
         # 有时可能直接返回一个列表
         attractions = view_result

    # 再次尝试解析如果 view_result 还是字符串
    if isinstance(view_result, str):
        try:
            parsed = json.loads(view_result)
            if isinstance(parsed, dict) and "views" in parsed:
                attractions = parsed.get("views", [])
            elif isinstance(parsed, list):
                attractions = parsed
            elif isinstance(parsed, dict) and "travel_plan" in parsed:
                attractions = parsed.get("travel_plan", [])
            elif isinstance(parsed, dict):
                # 假设它直接返回了一个字典，可能包含我们需要的数据，比如首尔的测试用例返回了包含 views 的 json 字符串
                if "views" in parsed:
                    attractions = parsed["views"]
        except:
            pass
            
    # 新增：由于 travel_plan_agent 返回的 json_str 中可能直接包含了 {"views": [...]}
    if not attractions and isinstance(view_result, dict):
         # 有时 view_result 已经被 _safe_parse_json 成功解析为一个嵌套的字典
         # 例如 {"views": [...]} 这个结构本身就是一个字符串，再次被 _safe_parse_json 解析后变成了 dict
         # 我们检查字典的值，看看有没有哪个值是包含列表的字符串并可以被解析
         for v in view_result.values():
             if isinstance(v, str):
                 try:
                     inner_parsed = json.loads(v)
                     if isinstance(inner_parsed, list):
                         attractions = inner_parsed
                         break
                     elif isinstance(inner_parsed, dict) and "views" in inner_parsed:
                         attractions = inner_parsed["views"]
                         break
                 except:
                     pass

    # 最后再兜底一次，如果 view_result 是一个字典但上面没匹配到，直接看里面有没有 views 键
    if not attractions and isinstance(view_result, dict) and "views" in view_result:
        attractions = view_result["views"]
        
    # 如果 attractions 还是空，打印一下到底是什么以便调试
    if not attractions:
        print(f"警告：无法从 view_result 中提取 attractions。view_result: {view_result}")

    normalized_views = []
    for index, item in enumerate(attractions):
        if not isinstance(item, dict):
            continue
        attraction_name = _clean_text(item.get("attraction_name") or item.get("name"))
        attraction_location = _clean_text(item.get("attraction_location") or hotel_request.get("city"))
        attraction_price = item.get("attraction_price", item.get("ticket_price", 0))
        open_time = _clean_text(item.get("attraction_open_time"))
        if not open_time:
            open_time = _clean_text(item.get("opening_hours"))
        information = _clean_text(item.get("description"))
        if not information:
            information = _clean_text(item.get("information"))
        image = _clean_text(item.get("image"))
        visit_duration = _clean_text(item.get("attraction_estimated_visit_time") or item.get("visit_duration"))
        normalized_views.append(
            {
                "name": attraction_name,
                "location": attraction_location,
                "information": information,
                "price": _parse_price_to_float(attraction_price),
                "open_time": open_time,
                "visit_duration": visit_duration,
                "image": image,
            }
        )

    data_payload = {
        "input": user_text,
        "flights": flights,
        "hotels": normalized_hotels,
        "views": normalized_views,
    }
    
    # 生成自然语言 output，如果需要的话
    if user_text and not output_text:
        output_text = _generate_natural_language_output(user_text, data_payload)
        
    data_payload["output"] = output_text

    return {
        "code": 200,
        "message": "success",
        "data": data_payload,
    }


def _generate_natural_language_output(user_text: str, data: dict) -> str:
    """
    根据用户的自然语言输入和查询到的旅游数据，生成一段自然语言的总结输出。
    """
    prompt = PromptTemplate(
        template=(
            "你是一个旅行助手。用户输入了：{user_text}\n"
            "你查询到了以下行程数据：\n{data}\n"
            "请用默认用英文写一段自然语言的总结，告诉用户你为他规划了什么航班、酒店和景点。\n"
            "如果用户使用中文输入，那么请用中文输出。\n"
            "如果用户使用其他语言输入，那么请用对应语言输出。\n"
            "航班输出格式：去程航班 出发地 -> 目的地，出发时间，到达时间，航空公司，航班号，舱位等级，价格。\n"
            "回程航班 出发地 -> 目的地，出发时间，到达时间，航空公司，航班号，舱位等级，价格。\n"
            "酒店输出格式：酒店名称，价格。\n"
            "必须输出所有景点的信息，不能省略任何景点。\n"
            "在输出时，请适当添加 emoji 表情，让内容更加生动活泼。\n"
            "景点输出格式："
            "景点1：景点名称，景点信息，额外信息\n"
            "景点2：景点名称，景点信息，额外信息\n"
            "直接输出总结文本，不要包含任何多余的格式。"
        ),
        input_variables=["user_text", "data"],
    )
    try:
        llm = _build_google_llm()
        chain = prompt | llm
        result = chain.invoke({"user_text": user_text, "data": json.dumps(data, ensure_ascii=False)})
        return result.content
    except Exception as e:
        return f"为您规划的行程已生成，请查看详细数据。（生成总结失败: {str(e)}）"


def run_test_main_agent_flow(user_text: str) -> dict:
    dispatch_plan = _dispatch_user_request_by_company(user_text)
    hotel_request_json = json.dumps(dispatch_plan["hotel_request"], ensure_ascii=False)
    flight_request_outbound_json = json.dumps(dispatch_plan["flight_request_outbound"], ensure_ascii=False)
    flight_request_inbound_json = json.dumps(dispatch_plan["flight_request_inbound"], ensure_ascii=False)
    attraction_dispatch_task = dispatch_plan["attraction_task"]
    view_request_json = _build_view_input(hotel_request_json)

    print("=== AI 分发计划（自然语言 -> JSON） ===")
    print(json.dumps(dispatch_plan, ensure_ascii=False))
    print("=== 中间分发任务（Attraction） ===")
    print(json.dumps(attraction_dispatch_task, ensure_ascii=False))

    hotel_result = _safe_parse_json(run_hotel_agent(hotel_request_json))
    
    hotel_request_json_dict = json.loads(hotel_request_json)
    flight_request_outbound = json.loads(flight_request_outbound_json)
    
    # 执行去程和返程机票查询
    flight_result_outbound = _safe_parse_json(run_flight_agent(flight_request_outbound_json))
    flight_result_inbound = _safe_parse_json(run_flight_agent(flight_request_inbound_json))
    
    # 合并机票结果，由于 flight_agent 现在返回 'flights' 列表且已截断为前2个，我们直接将它们加入
    merged_flight_result = {"flights": []}
    if isinstance(flight_result_outbound, dict):
        if "flight" in flight_result_outbound and flight_result_outbound["flight"]:
            merged_flight_result["flights"].append(flight_result_outbound["flight"])
        elif "flights" in flight_result_outbound and len(flight_result_outbound["flights"]) > 0:
            merged_flight_result["flights"].extend(flight_result_outbound["flights"])
            
    if isinstance(flight_result_inbound, dict):
        if "flight" in flight_result_inbound and flight_result_inbound["flight"]:
            merged_flight_result["flights"].append(flight_result_inbound["flight"])
        elif "flights" in flight_result_inbound and len(flight_result_inbound["flights"]) > 0:
            merged_flight_result["flights"].extend(flight_result_inbound["flights"])

    
    # 使用 attraction_seed_agent 获取景点推荐，并取前10个
    dest_city = attraction_dispatch_task['destination']
    print(f"📍 调用 attraction_seed_agent 查询 {dest_city} 的景点")
    
    transport_result = None
    
    try:
        view_result_raw = run_seed_agent(dest_city)
        # run_seed_agent 已经返回了字典，无需再次 json.loads
        view_result = view_result_raw
        
        # 如果返回了景点列表，截取前 10 个
        if isinstance(view_result, dict) and "attractions" in view_result:
            view_result["attractions"] = view_result["attractions"][:10]
            
            # 提取景点名称和游玩时间用于路线规划
            attraction_names = []
            attraction_durations = {}
            for attr in view_result["attractions"]:
                if isinstance(attr, dict) and "name" in attr:
                    name = attr["name"]
                    attraction_names.append(name)
                    # 尝试获取 visit_duration
                    duration = attr.get("visit_duration") or attr.get("attraction_estimated_visit_time") or "未知"
                    attraction_durations[name] = duration
            
            # 提取酒店名称用于路线规划的起点
            hotel_name = "the hotel"
            if isinstance(hotel_result, dict) and "hotels" in hotel_result and len(hotel_result["hotels"]) > 0:
                hotel_item = hotel_result["hotels"][0]
                if isinstance(hotel_item, dict) and "name" in hotel_item:
                    hotel_name = hotel_item["name"]
            elif isinstance(hotel_result, list) and len(hotel_result) > 0:
                hotel_item = hotel_result[0]
                if isinstance(hotel_item, dict) and "name" in hotel_item:
                    hotel_name = hotel_item["name"]
            
            # 酒店不需要游玩时间
            attraction_durations[hotel_name] = "N/A"
            
                
    except Exception as e:
        print(f"调用 run_seed_agent 失败: {e}")
        view_result = {}
        
    stored_payload = _build_standard_payload(hotel_request_json, merged_flight_result, hotel_result, view_result, transport_result, user_text)

    return {
        "dispatch_payload": {
            "hotel_request": json.loads(hotel_request_json),
            "flight_request_outbound": json.loads(flight_request_outbound_json),
            "flight_request_inbound": json.loads(flight_request_inbound_json),
            "view_request": json.loads(view_request_json),
            "attraction_task": attraction_dispatch_task,
        },
        "stored_payload": stored_payload,
    }


def main() -> None:
    print("示例: 我从吉隆坡去首尔玩，一个人，2026.5.1到2026.5.4")
    # 为了自动化测试，不再阻塞等待输入
    user_text = "我从吉隆坡去首尔玩，一个人，2026.5.1到2026.5.4"
    print(f"使用的查询: {user_text}")
    output = run_test_main_agent_flow(user_text)
    print("=== 分发请求 ===")
    print(json.dumps(output["dispatch_payload"], ensure_ascii=False, indent=2))
    print("=== 存储结果 ===")
    print(json.dumps(output["stored_payload"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
