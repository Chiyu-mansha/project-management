"""成员2：活动发布管理模块包。

本包只导出活动模块的路由；共享的 database.py、schema.sql、main.py 仍在 backend/ 根目录。
"""
from .activities import router as activity_router

__all__ = ["activity_router"]
