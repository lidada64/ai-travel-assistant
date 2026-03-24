import os
import json
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 导入 main_agent 统一入口
from app.agents.main_agent import run_test_main_agent_flow

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
        user_input = payload.get("input")
        if not user_input:
            # 兼容旧逻辑，如果没有 input，则拼接一个自然语言 input 传给 main_agent
            dest = payload.get("destination", [""])[0]
            dep = payload.get("departure", "")
            pax = payload.get("pax", 1)
            start = payload.get("time", {}).get("start_date", "")
            end = payload.get("time", {}).get("end_date", "")
            user_input = f"From {dep} to {dest}, {pax} person. From {start} to {end}"

        user_input = str(user_input).strip()
        
        # 将请求委托给 main_agent
        result = run_test_main_agent_flow(user_input)
        
        # main_agent 返回的 stored_payload 已经符合前端所需格式
        stored_payload = result.get("stored_payload", {})
        
        # 如果 code 不是 200，说明内部报错
        if stored_payload.get("code") != 200:
            return stored_payload

        return stored_payload

    except Exception as e:
        return {
            "code": 500,
            "message": str(e),
            "data": {"input": "", "output": "", "flights": [], "hotels": [], "views": []},
        }

