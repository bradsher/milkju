"""Configuration constants for the message system."""

# 分段配置
SOFT_LIMIT = 3500          # 软上限：触发切断流程
HARD_LIMIT = 4000          # 硬上限：绝不能超过
TELEGRAM_MAX = 4096        # Telegram API 硬限制

# 流式配置
DRAFT_UPDATE_INTERVAL = 0.5    # 主模式更新间隔（秒），用户倾向于0.3s
FALLBACK_UPDATE_INTERVAL = 3.0 # 回退模式更新间隔（秒）

# 格式配置
PARSE_MODE = "HTML"        # 统一使用 HTML 格式

# 回退配置
MAX_RETRY_COUNT = 3        # 最大重试次数
