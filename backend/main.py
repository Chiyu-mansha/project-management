from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from activity import activity_router
from faq import faqs_router, faqs_auto_router, qa_router

app = FastAPI(title="校园活动智能通知&报名助理")

# 开发阶段全放开,部署时收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
app.include_router(activity_router)
app.include_router(faqs_router)
app.include_router(faqs_auto_router)
app.include_router(qa_router)


@app.get("/api/hello")
def hello():
    return {"message": "backend ok"}
