import os
import redis
from openai import OpenAI
from . import logger
config = {
    "admin_user_id": "2694611137",
    "temp_folder": "/anran/bots/amer/utils/temp",
    "server": {
        "host": "0.0.0.0",
        "port": 5888
    },
    "qq": {
        "bot_name": "amer",
        "bot_qq": "643319481"
    },
    "yh": {
        "token": "405a97ee76e84bc78f6a8a362ffc0591",
        "webhook": {
            "path": "/yh/webhook"
        }
    },
    "blocked_words": {
        "骂人": ["傻逼", "蠢货", "混蛋", "狗屎", "废物", "傻瓜", "猪头", "白痴", "呆子", "死胖子", "二货", "死傻逼", "废物", "无耻", "死蠢", "低级", "蠢猪", "老狗", "傻逼", "傻屄", "脑残", "智障", "贱人", "婊子", "狗娘养的", "死变态", "死肥宅", "死穷鬼", "死秃子", "死矮子", "死穷逼", "死贱人", "死不要脸", "死垃圾", "死废物", "死狗", "死猪", "死猫", "死老鼠", "死蟑螂"],
        "政治": ["共产党", "国民党", "左翼", "右翼", "极左", "极右", "民主", "专制", "社会主义", "资本主义", "独裁", "威权", "自由派", "保守派", "革命", "反革命", "政权", "反对派", "执政党", "在野党", "政治犯", "言论自由", "选举舞弊", "政治迫害", "国家机器"],
        "宗教": ["基督教", "伊斯兰教", "佛教", "道教", "天主教", "犹太教", "神父", "牧师", "僧侣", "道士", "圣经", "古兰经", "佛经", "道教经典", "祈祷", "礼拜", "朝圣", "洗礼", "斋戒", "法会", "寺庙", "教堂", "清真寺", "修道院", "宗教仪式"],
        "广告": ["优惠", "促销", "打折", "优惠券", "广告", "推销", "特惠", "折扣", "买一送一", "限时", "免费试用", "限时抢购", "秒杀", "满减", "包邮", "会员专享", "新品上市", "爆款推荐", "清仓大甩卖", "限量发售", "预售", "团购", "积分兑换", "现金返还", "赠品"],
        "色情": ["色情", "成人内容", "性爱", "裸体", "淫秽", "性暗示", "性交易", "性骚扰", "性暴力", "色情网站"],
        "暴力": ["杀人", "打人", "斗殴", "暴力", "血腥", "枪击", "爆炸", "恐怖袭击", "绑架", "虐待", "自残", "自杀", "谋杀", "战争", "暴力游戏"],
        "赌博": ["赌场", "赌博", "赌球", "赌马", "彩票", "扑克", "轮盘", "老虎机", "下注", "赌资", "赌徒", "赌局", "赌债", "赌博网站", "赌博游戏"],
        "毒品": ["毒品", "吸毒", "贩毒", "大麻", "海洛因", "冰毒", "摇头丸", "可卡因", "鸦片", "毒品交易", "毒品制造", "毒品走私", "毒品滥用", "戒毒", "毒品犯罪"]
    },
    "OpenAI": {
        "base_url": "https://api.openai.com",
        "api_key": "",
        "aliyun_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "aliyun_key": "",
        "guijiliudong_url": "https://api.siliconflow.cn/v1",
        "guijiliudong_key": ""
    },
    "Redis": {
        "host": "127.0.0.1",
        "port": 6379,
        "db": 14,
        "password": ""
    },
    "SQLite": {
        "db_path": "utils/sqlite/amer.db"
    },
    "Message": {
        "message-YH": "**指令说明**\n\n1. **/绑定 <QQ群号>**\n   - **功能**: 将当前云湖群与指定的QQ群进行绑定。\n\n2. **/同步模式 <全同步 / 停止 / QQ到云湖 / 云湖到QQ> [可选:QQ群]**\n   - **功能**: 切换消息同步模式，支持多向同步、单向同步（云湖到QQ、QQ到云湖）和停止同步。\n\n3. **/解绑 <QQ群号 / 全部>**\n   - **功能**: 取消与指定QQ群的绑定，输入“全部”时取消所有绑定。\n---\n**注意**: 操作教程需在机器人私聊中使用 `/帮助` 指令。\n - **全体消息自动加到绑定群聊的看板**: 所有消息会自动添加到绑定群聊的看板中，方便查看和管理。",
        "message-YH-followed": "# 欢迎使用Amer-Link!\n\n**简介**\n- Amer机器人用于在云湖群和QQ群之间同步消息。请注意，您无法在当前页面使用绑定指令。\n\n**功能更新**\n- **单向消息同步**: 消息可以从云湖单向同步到QQ群或从QQ群单向同步到云湖。\n- **双向消息同步**: 消息可以在云湖和QQ群之间双向同步。\n- **其它同步**: 图片、表情包、视频、部分分享内容等也可以在云湖和QQ群之间同步。\n\n**如何使用**\n1. **添加Amer至群聊**: 确保将Amer添加至您的QQ群和云湖群。[点击此处添加QQ-Amer](https://qm.qq.com/q/2RSZSEkRwY)\n2. **在云湖端操作**: 在云湖群中绑定您的QQ群，以便开始消息同步。当云湖群绑定QQ群时，QQ群中会提示“此群被云湖绑定了”。\n3. **选择同步模式**: 根据您的需求选择单向或多向消息同步。\n\n**注意**: 指令详情请在云湖群中使用 `/帮助` 指令查看。\n\n如果想请我喝奶茶,[点我赞助](https://ifdian.net/a/YingXinche)"
    },
    "AI": {
        "Ban": {
            "ban_ai_id": [],
            "ban_ai_group": []
        },
        "Pass": {
            "pass_ai_id": []
        },
        "max_length": 10,
        "max_conversation_length": 10,
        "max_concurrent_requests": 2,
        "rate_limit": {
            "group": 3,
            "private": 3,
            "window": 30
        }
    },
    "commands": {
        "list": {
            "qq": ["封禁", "帮助", "ai配置", "ai开关", "同步群组管理"]
        },
        "qq": {
            "ai开关": "⚙️ 功能：控制AI核心运行状态\n📝 格式：`/ai开关 [开/关]`\n🛠️ 参数说明：\n- 开：激活AI应答功能\n- 关：停止AI应答功能\n⚠️ 需要管理员权限",
            "ai配置": "⚙️ 功能：AI核心参数配置\n📝 操作指令：\n▸ `/AI配置 清除记忆` → 永久删除所有对话记忆\n▸ `/AI配置 查看记忆` → 显示记忆存储状态\n▸ `/AI配置 关键词` → 管理触发关键词\n▸ `/AI配置 提示词` → 设置系统提示词\n🚨 注意：配置更改将直接影响AI行为",
            "同步群组管理": "📜 功能：管理跨平台绑定\n📝 使用：`/同步群组管理 [子命令]`\n🔍 子命令：\n- 绑定 <yh> <id/token>：绑定新平台\n- 解绑 <yh> <id/token>：解除平台绑定\n- 列表：查看当前绑定状态\n🔍 返回信息：\n- 平台类型 | 群组名称 | （同步模式）"
        },
        "qqForAI": {
            "ai配置": {
                "指令": "/ai配置 [子指令]",
                "子指令": {
                    "清除记忆": "永久删除所有对话记忆",
                    "查看记忆": "显示记忆存储状态",
                    "关键词": "管理触发关键词",
                    "提示词": "设置系统提示词"
                },
                "效果": "管理AI核心配置参数"
            },
            "同步群组管理": {
                "指令": "/同步群组管理 [子指令]",
                "子指令": {
                    "绑定": "绑定新平台，格式：`/同步群组管理 绑定 <yh> <id>`",
                    "解绑": "解除平台绑定，格式：`/同步群组管理 解绑 <yh> <id>`",
                    "列表": "查看当前绑定状态"
                },
                "效果": "管理跨平台绑定，包括绑定新平台、解除绑定和查看当前绑定状态"
            }
        }
    }
}

# 全局变量
temp_folder = config['temp_folder']
server_host = config['server']['host']
server_port = config['server']['port']

bot_name = config['qq']['bot_name']
bot_qq = config['qq']['bot_qq']
qq_commands = config['commands']['qq']
qq_commands_list = config['commands']['list']['qq']
qq_commandsForAI = config['commands']['qqForAI']

yh_token = config['yh']['token']
yh_webhook_path = config['yh']['webhook']['path']
message_yh = config['Message']['message-YH']
message_yh_followed = config['Message']['message-YH-followed']

openai_base_url = config['OpenAI']['base_url']
openai_api_key = config['OpenAI']['api_key']
aliyun_url = config['OpenAI']['aliyun_url']
aliyun_key = config['OpenAI']['aliyun_key']
guijiliudong_url = config['OpenAI']['guijiliudong_url']
guijiliudong_key = config['OpenAI']['guijiliudong_key']
ban_ai_id = config['AI']['Ban']['ban_ai_id']
ban_ai_group = config['AI']['Ban']['ban_ai_group']
pass_ai_id = config['AI']['Pass']['pass_ai_id']
ai_max_length = config['AI']['max_length']
max_conversation_length = config['AI']['max_conversation_length']
max_concurrent_requests = config['AI']['max_concurrent_requests']
ai_rate_limit_group = config['AI']['rate_limit']['group']
ai_rate_limit_private = config['AI']['rate_limit']['private']
ai_rate_limit_window = config['AI']['rate_limit']['window']
blocked_words = config['blocked_words']
admin_user_id = config['admin_user_id']

AI_drive = "guijiliudong"
low_AI_deive = "guijiliudong"

def get_ai():
    if AI_drive == "aliyun":
        drive_model = "qwen2.5-7b-instruct-1m"
        client = OpenAI(base_url=aliyun_url, api_key=aliyun_key)
    elif AI_drive == "guijiliudong":
        import datetime
        current_hour = datetime.datetime.now().hour
        if (8 <= current_hour < 10) or (18 <= current_hour < 20):
            drive_model = "deepseek-ai/DeepSeek-V2.5"
        else:
            drive_model = "deepseek-ai/DeepSeek-V2.5"
        client = OpenAI(base_url=guijiliudong_url, api_key=guijiliudong_key)
    else:
        drive_model = "deepseek-chat"
        client = OpenAI(base_url=openai_base_url, api_key=openai_api_key)
    return client, drive_model

# 低配的AI
if low_AI_deive == "aliyun":
    low_drive_model = "qwen-turbo-1101"
    low_client = OpenAI(base_url=aliyun_url, api_key=aliyun_key)
elif AI_drive == "guijiliudong":
    low_drive_model = "Pro/google/gemma-2-9b-it"
    low_client = OpenAI(base_url=guijiliudong_url, api_key=guijiliudong_key)
else:
    low_drive_model = "deepseek-chat"
    low_client = OpenAI(base_url=openai_base_url, api_key=openai_api_key)

def replace_blocked_words(message: str) -> str:
    replaced_words = []
    for category, words in blocked_words.items():
        for word in words:
            if word in message:
                message = message.replace(word, '*' * len(word))
                replaced_words.append((word, category))
    if replaced_words:
        logger.info(f"屏蔽字符: {replaced_words}")
    return message

# Redis
redis_host = config['Redis']['host']
redis_port = config['Redis']['port']
redis_db = config['Redis']['db']
redis_password = config['Redis']['password']
try:
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
    )
    redis_client.ping()
except redis.ConnectionError:
    logger.warning(f"无法连接到 Redis 服务器: {redis_host}:{redis_port}")
    exit(1)

# SQLite
sqlite_db_path = config['SQLite']['db_path']