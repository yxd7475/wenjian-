"""
时区工具函数
"""
from datetime import datetime, timezone, timedelta

# 北京时区 UTC+8
BEIJING_TZ = timezone(timedelta(hours=8))


def get_beijing_time() -> datetime:
    """获取当前北京时间"""
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)


def utc_to_beijing(dt: datetime) -> datetime:
    """将UTC时间转换为北京时间"""
    if dt is None:
        return None
    utc_dt = dt.replace(tzinfo=timezone.utc)
    beijing_dt = utc_dt.astimezone(BEIJING_TZ)
    return beijing_dt.replace(tzinfo=None)
