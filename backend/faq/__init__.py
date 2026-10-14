"""成员3：FAQ 知识库 + 智能答疑模块包。

本包只导出本模块的路由；共享的 database.py、schema.sql、main.py 仍保留在 backend/ 根目录。
"""
from .activity_stub import router as activity_stub_router
from .faqs import router as faqs_router
from .faqs_auto import router as faqs_auto_router
from .qa import router as qa_router

__all__ = [
    "activity_stub_router",
    "faqs_router",
    "faqs_auto_router",
    "qa_router",
]
