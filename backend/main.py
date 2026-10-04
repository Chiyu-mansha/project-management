from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
import faqs, qa, activities, faqs_auto

app = FastAPI(title="校园活动智能通知&报名助理")

# 开发阶段全放开,部署时收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
app.include_router(faqs.router)
app.include_router(faqs_auto.router)
app.include_router(qa.router)
app.include_router(activities.router)


@app.get("/api/hello")
def hello():
    return {"message": "backend ok"}
