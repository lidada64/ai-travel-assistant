import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import json
from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from app.tools.hotel_tool import search_hotels
from datetime import datetime

load_dotenv()

class HotelAgentInput(BaseModel):
    city: str = Field(..., description="酒店城市英文名")
    check_in: str = Field(..., description="入住日期 YYYY-MM-DD")
    check_out: str = Field(..., description="退房日期 YYYY-MM-DD")


HOTEL_INPUT_PARSER = JsonOutputParser(pydantic_object=HotelAgentInput)


def run_hotel_agent(json_input: str):
    data = HOTEL_INPUT_PARSER.parse(json_input)
    city = data.get("city")
    check_in = data.get("check_in")
    check_out = data.get("check_out")
    hotels = search_hotels.invoke(
        {
            "location": city,
            "check_in_date": check_in,
            "check_out_date": check_out,
        }
    )
    return json.dumps(hotels, ensure_ascii=False, indent=2)
   

if __name__ == "__main__":
    import json
    from datetime import datetime

    print("--- 🏨 AI Hotel Booking Assistant ---")
    
    while True:
        city = input("Enter destination city (e.g., Penang): ").strip()
        if city:
            break
        print("❌ City name cannot be empty. Please try again.")

   
    while True:
        check_in_str = input("Enter check-in date (YYYY-MM-DD): ")
        check_out_str = input("Enter check-out date (YYYY-MM-DD): ")

        def validate_dates(in_str, out_str):
            try:
                today = datetime.now().date()
                check_in_date = datetime.strptime(in_str, "%Y-%m-%d").date()
                check_out_date = datetime.strptime(out_str, "%Y-%m-%d").date()

                if check_in_date < today:
                    return False, "Check-in date must be today or later."
                if check_out_date <= check_in_date:
                    return False, "Check-out date must be after the check-in date."
                return True, None
            except ValueError:
                return False, "Invalid date format. Please use YYYY-MM-DD."

        is_valid, error_msg = validate_dates(check_in_str, check_out_str)
        
        if is_valid:
            break  
        else:
            print(f"❌ Error: {error_msg} Please re-enter both dates.")

    user_input_json = json.dumps({
        "city": city,
        "check_in": check_in_str,
        "check_out": check_out_str,
        "guests": 2,  
        "budget": { "min": 0, "max": 10000, "currency": "MYR" } 
    })

    print(f"\n🚀 Processing request for {city} from {check_in_str} to {check_out_str}...")
    run_hotel_agent(user_input_json)
    
    
