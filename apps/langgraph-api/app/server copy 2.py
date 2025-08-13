from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from .langgraph.agent import assistant_ui_graph
from .langgraph.reasoning_agent import reasoning_agent_graph
from .add_langgraph_route import add_langgraph_route
import os

app = FastAPI(title="LangGraph Reasoning Agent API", description="AI агент с многошаговым рассуждением")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Основной маршрут - всегда рассуждающий агент
add_langgraph_route(app, reasoning_agent_graph, "/api/chat")

# Дополнительные маршруты для сравнения
add_langgraph_route(app, assistant_ui_graph, "/api/simple-chat")  # Простой агент для сравнения
add_langgraph_route(app, reasoning_agent_graph, "/api/reasoning-chat")  # Альтернативный путь

@app.get("/")
async def root():
    return {
        "message": "LangGraph Reasoning Agent API", 
        "description": "AI агент с многошаговым рассуждением и планированием",
        "endpoints": {
            "chat": "/api/chat - 🧠 РАССУЖДАЮЩИЙ АГЕНТ (основной)",
            "simple_chat": "/api/simple-chat - ⚡ Простой агент",
            "reasoning_chat": "/api/reasoning-chat - 🧠 Рассуждающий агент (дубль)",
            "docs": "/docs - Swagger документация"
        },
        "features": [
            "📋 Автоматическое планирование задач",
            "💭 Пошаговые размышления", 
            "🎯 Адаптивное выполнение плана",
            "📝 История рассуждений",
            "🔄 Многошаговое решение сложных задач"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))  # Используем PORT из docker-compose
    uvicorn.run(app, host="0.0.0.0", port=port)
