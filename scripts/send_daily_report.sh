#!/bin/bash
cd /home/erpnext/.services/api_cyber
/home/erpnext/api_cyber_env/bin/python -c "
from src.workers.tasks.daily_report import send_daily_report
result = send_daily_report()
print(result)
"
