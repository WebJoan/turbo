from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from .langgraph.reasoning_agent import reasoning_agent_graph
from .add_langgraph_route import add_langgraph_route

app = FastAPI(title="Reasoning Agent API", description="AI агент с возможностью многошагового рассуждения")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Добавляем маршрут для рассуждающего агента
add_langgraph_route(app, reasoning_agent_graph, "/api/chat")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)  # Запускаем на другом порту
