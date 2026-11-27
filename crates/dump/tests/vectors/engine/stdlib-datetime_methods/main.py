import datetime

start = datetime.date(2024, 1, 31)
later = start + datetime.timedelta(days=1)
later.isoformat()
