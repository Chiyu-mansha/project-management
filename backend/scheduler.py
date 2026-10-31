from apscheduler.schedulers.background import BackgroundScheduler
# 同时引入两个函数
from notification.notifications import _do_check_deadlines, _do_check_lottery
import logging

logger = logging.getLogger("uvicorn.error")

def start_scheduler():
    scheduler = BackgroundScheduler()
    
    # 每小时的第 0 分钟执行一次（例如 1:00, 2:00）截止预警扫描
    scheduler.add_job(_do_check_deadlines, 'cron', minute=0, id='check_deadlines_job')
    
    # 每小时的第 30 分钟执行一次（例如 1:30, 2:30）开奖提醒扫描
    scheduler.add_job(_do_check_lottery, 'cron', minute=30, id='check_lottery_job')
    
    scheduler.start()
    logger.info("⏰ APScheduler 已启动：截止预警 + 开奖提醒已挂载")