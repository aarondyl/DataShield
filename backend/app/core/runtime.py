"""进程级运行时信息（启动时间戳等，供管理后台 /system 端点展示）。"""

import time

#: 进程启动时间戳（模块随进程首次导入时记录）
STARTED_AT = time.time()
