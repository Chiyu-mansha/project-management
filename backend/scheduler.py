from apscheduler.schedulers.background import BackgroundScheduler
from notification.notifications import _do_check_deadlines
import logging

logger = logging.getLogger("uvicorn.error")

def start_scheduler():
    scheduler = BackgroundScheduler()
    # 每小时的第 0 分钟执行一次（例如 1:00, 2:00）
    scheduler.add_job(_do_check_deadlines, 'cron', minute=0, id='check_deadlines_job')
    scheduler.start()
    logger.info("⏰ APScheduler 已启动：每小时执行一次截止预警扫描")