from utils.config import redis_client, blocked_words, replace_blocked_words
from utils import logger
import datetime
import json
from . import BindingManager
from .ToolManager import YunhuTools, QQTools, BaseTools
from typing import Dict, Any
import re
yhtools = YunhuTools()
qqtools = QQTools()
basetools = BaseTools()
class QQMessageData:
    def __init__(self, data: Dict[str, Any]):
        self.self_id = data.get('self_id', "")
        self.user_id = data.get('user_id', "")
        self.time = data.get('time', "")
        self.message_id = data.get('message_id', "")
        self.message_seq = data.get('message_seq', "")
        self.real_id = data.get('real_id', "")
        self.message_type = data.get('message_type', "")
        self.raw_message = data.get('raw_message', "")
        self.font = data.get('font', "")
        self.sub_type = data.get('sub_type', "")
        self.message_format = data.get('message_format', "")
        self.post_type = data.get('post_type', "")
        self.group_id = data.get('group_id', "")
        
        sender_info = data.get('sender', {})
        self.sender_user_id = sender_info.get('user_id', "")
        self.sender_nickname = sender_info.get('nickname', "")
        self.sender_card = sender_info.get('card', "")
        self.sender_role = sender_info.get('role', "")

class YunhuMessageData:
    def __init__(self, data: Dict[str, Any]):
        self.version = data.get("version", "")
        self.header_event_id = data.get("header", {}).get("eventId", "")
        self.header_event_type = data.get("header", {}).get("eventType", "")
        self.header_event_time = data.get("header", {}).get("eventTime", "")

        # sender相关
        event_info = data.get("event", {})
        sender_info = event_info.get("sender", {})
        self.userid = event_info.get("userId", "")
        self.sender_id = sender_info.get("senderId", "")
        self.sender_type = sender_info.get("senderType", "")
        self.sender_user_level = sender_info.get("senderUserLevel", "")
        self.sender_nickname = sender_info.get("senderNickname", "")

        # msg相关
        message_info = event_info.get("message", {})
        self.msg_id = message_info.get("msgId", "")
        self.parent_id = message_info.get("parentId", "")
        self.send_time = message_info.get("sendTime", "")
        self.message_chat_id = message_info.get("chatId", "")
        self.message_chat_type = message_info.get("chatType", "")
        self.content_type = message_info.get("contentType", "")
        self.message_content = message_info.get("content", {}).get("text", "")
        self.message_content_base = message_info.get("content", {})
        self.instruction_id = message_info.get("instructionId", "")
        self.instruction_name = message_info.get("instructionName", "")
        self.command_id = message_info.get("commandId", "")
        self.command_name = message_info.get("commandName", "")

        # img相关
        self.image_url = self.message_content_base.get("imageUrl", "")
        self.image_name = self.message_content_base.get("imageName", "")
        self.etag = self.message_content_base.get("etag", "")
        self.is_gif = self.image_url.lower().endswith('.gif')

        self.setting_json = event_info.get('settingJson', '{}')
        self.settings = json.loads(self.setting_json)
        self.setting_group_id = event_info.get("groupId", "")
def detect_repeated_characters(message: str, threshold=10) -> bool:
    """
    检测消息中是否存在连续相同字符或大量空白字符。
    :param message: 用户发送的消息内容
    :param threshold: 连续字符的阈值，默认为10
    :return: 是否触发检测规则
    """
    # 检测连续相同字符
    if re.search(r'(.)\1{%d,}' % (threshold - 1), message):
        return True
    # 检测大量空白字符
    if re.search(r'\s{%d,}' % threshold, message):
        return True
    return False

def contains_blocked_words(message: str) -> tuple:
    """
    检测消息中是否包含违规词，并返回替换后的消息。
    :param message: 用户发送的消息内容
    :return: (是否包含违规词, 替换后的消息)
    """
    original_message = message
    replaced_message = replace_blocked_words(message)
    return original_message != replaced_message, replaced_message
def detect_message_frequency(redis_client, platform: str, user_id: str, threshold: int, time_window: int) -> bool:
    """
    检测用户在指定时间窗口内的消息发送频率。
    :param redis_client: Redis 客户端
    :param platform: 平台类型（QQ/YH）
    :param user_id: 用户ID
    :param threshold: 消息数量阈值
    :param time_window: 时间窗口（秒）
    :return: 是否触发频率检测规则
    """
    frequency_key = f"message_frequency:{platform}:{user_id}"
    # 增加计数
    count = redis_client.incr(frequency_key)
    if count == 1:
        # 第一次发送消息时设置过期时间
        redis_client.expire(frequency_key, time_window)
    
    # 判断是否超过阈值
    if count > threshold:
        return True
    return False
async def handle_violation(platform: str, group_id: str, user_id: str, user_nickname: str, reason: str):
    """
    处理用户违规行为，包括封禁和通知。
    :param platform: 平台类型（QQ/YH）
    :param group_id: 群聊ID
    :param user_id: 用户ID
    :param user_nickname: 用户昵称
    :param reason: 违规原因
    """
    # 获取用户当天的违规记录
    violation_key = f"violation:{platform}:{user_id}:{datetime.date.today()}"
    violation_count = redis_client.get(violation_key)
    violation_count = int(violation_count) if violation_count else 0

    if violation_count == 0:
        # 首次违规，仅记录
        redis_client.set(violation_key, 1, ex=86400)
        logger.info(f"用户 {user_id} 首次违规，已记录但未封禁")
        return
    else:
        # 后续违规，递增封禁时长
        duration = violation_count * 60
        redis_client.incr(violation_key)

    # 调用封禁接口
    ban_status = await basetools.add_to_blacklist(user_id, reason, duration)
    if ban_status:
        # 获取用户名
        user_name = await basetools.get_user_nickname(platform, user_id)

        notify_message_text = (
            f"【ฅ喵呜·封禁通知ฅ】\n"
            f"✦{user_name} (ID: {user_id}) 的小鱼干被没收啦~\n"
            f"从现在起不会同步这个用户的消息了喵！\n"
            f"✦封禁原因：{reason}\n"
            f"✦持续时间：{'直到吃完'+str(duration//10)+'个猫罐头的时间(大概'+str(duration)+'秒)喵~' if duration >0 else '永久的喵~ (小爪爪盖上红印)'}"
        )

        notify_message_html = (
            # 消息容器：封禁通知内容
            f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">{user_name} (ID: {user_id}) 的小鱼干被没收啦~'
            f'<p style="font-size: 12px; color: #8b0000; margin: 5px 0;">'
            f'从现在起不会同步这个用户的消息了喵！'
            f'</p>'
            f'<p style="font-size: 12px; color: #333; margin: 5px 0;">'
            f'✦封禁原因：{reason}'
            f'</p>'
            f'<p style="font-size: 12px; color: #333; margin: 5px 0;">'
            f'✦持续时间：{"直到吃完"+str(duration//10)+"个猫罐头的时间(大概"+str(duration)+"秒)喵~" if duration > 0 else "永久的喵~ (小爪爪盖上红印)"}'
            f'</p>'
            f'</div>'
        )

        # 发送通知
        if platform == "QQ" or platform == "qq":
            await qqtools.send("group", int(group_id), notify_message_text)
            # 发送通知到所有绑定群聊
            await send_to_all_bindings(
                platform,
                group_id,
                "html",
                notify_message_html,
                0,
                "Amer"
            )
        elif platform == "YH" or platform == "yh":
            await yhtools.send(recvId=group_id, recvType="group", contentType="html", content=notify_message_html)
            await send_to_all_bindings(
                platform,
                group_id,
                "text",
                notify_message_text,
                0,
                "Amer"
            )
        logger.info(f"已封禁用户 {user_id}，通知已发送到 {platform}:{group_id}")
    else:
        logger.error(f"封禁用户 {user_id} 失败")

def store_sensitive_message(redis_client, platform: str, id: str, sender_id: str, sender_nickname: str, message_content: str):
    """
    存储敏感消息到 Redis。
    :param redis_client: Redis 客户端
    :param platform: 平台类型（QQ/YH）
    :param id: 群聊 ID
    :param sender_id: 用户 ID
    :param sender_nickname: 用户昵称
    :param message_content: 消息内容
    """
    sensitive_key = f"sensitive_messages:{platform}:{id}"
    sensitive_message = {
        "sender_id": sender_id,
        "sender_nickname": sender_nickname,
        "message_content": message_content,
        "timestamp": str(datetime.datetime.now()),
        "platform_from": platform,
        "id_from": id
    }
    redis_client.rpush(sensitive_key, json.dumps(sensitive_message))
    logger.info(f"存储敏感消息: {sensitive_key} -> {sensitive_message}")

async def send(platform_a, platform_b, id_a, id_b, message_type, message_content, sender_id, sender_nickname, noBaseContent=None, msg_id=None):
    # 检测是否被封禁
    ban_status = await basetools.is_in_blacklist(sender_id)
    if ban_status["is_banned"]:
        return False

    # 检测异常消息发送频率
    if detect_message_frequency(redis_client, platform_a, sender_id, threshold=15, time_window=30):
        await handle_violation(platform_a, id_a, sender_id, sender_nickname, "发送消息过于频繁")
        store_sensitive_message(redis_client, platform_a, id_a, sender_id, sender_nickname, message_content)
        return False
    
    # 检测重复字符
    if detect_repeated_characters(message_content):
        await handle_violation(platform_a, id_a, sender_id, sender_nickname, "发送重复字符")
        store_sensitive_message(redis_client, platform_a, id_a, sender_id, sender_nickname, message_content)
        return False

    # 检测违规词
    has_blocked_words, cleaned_message = contains_blocked_words(message_content)
    if has_blocked_words:
        await handle_violation(platform_a, id_a, sender_id, sender_nickname, "使用违规词")
        store_sensitive_message(redis_client, platform_a, id_a, sender_id, sender_nickname, message_content)
        message_content = cleaned_message
    
    key_ab = f"{platform_a}:{id_a}:{platform_b}:{id_b}"
    key_ba = f"{platform_b}:{id_b}:{platform_a}:{id_a}"
    key_local = f"{platform_a}:{id_a}:{platform_a}:{id_a}"
    message_to_save = {
        "sender_id": sender_id,
        "sender_nickname": sender_nickname,
        "message_type": message_type,
        "message_content": message_content,
        "timestamp": str(datetime.datetime.now()),
        "msg_id": msg_id,
        "platform_from": platform_a,
        "id_from": id_a
    }
    if platform_a == platform_b and id_a == id_b:
        redis_client.rpush(key_local, json.dumps(message_to_save))
    else:
        redis_client.rpush(key_ab, json.dumps(message_to_save))
        redis_client.rpush(key_ba, json.dumps(message_to_save))
        redis_client.rpush(key_local, json.dumps(message_to_save))
    
    if msg_id is not None:
        # 将 msg_id 作为键存储，值可以是消息的主键或完整消息内容
        redis_client.set(f"msg_id:{msg_id}", json.dumps(message_to_save))
        logger.info(f"存储 msg_id: msg_id:{msg_id} -> {message_to_save}")

    if noBaseContent:
        message_content = noBaseContent
    logger.info(f"存储消息: {key_local} -> {message_to_save}")

    if platform_b == "QQ" or platform_b == "qq":
        try:
            await qqtools.send("group", int(group['id']), message_content)
        except Exception as e:
            logger.error(f"发送QQ群消息失败，群组ID: {group['id']}, 错误信息: {e}")
    elif platform_b == "YH" or platform_b == "yh":
        await yhtools.send(recvId=id_b, recvType="group", contentType="html", content=message_content)
    else:
        return "不支持的平台"

async def send_to_all_bindings(platform, id, message_type, message_content, sender_id, sender_nickname, noBaseContent=None, msg_id=None):
    """发送消息到指定平台的所有绑定群聊，排除消息来源的平台"""
    ban_status = await basetools.is_in_blacklist(sender_id)
    if ban_status["is_banned"]:
        return False

    # 获取所有绑定信息
    bind_info = BindingManager.get_info(platform, id)
    logger.info(f"获取绑定信息: {platform}:{id} -> {bind_info}")
    if bind_info['status'] != 0:
        return bind_info['msg']
    
    # 检测是否被封禁
    ban_status = await basetools.is_in_blacklist(sender_id)
    if ban_status["is_banned"]:
        return False

    # 检测异常消息发送频率
    if detect_message_frequency(redis_client, platform, sender_id, threshold=15, time_window=30):
        await handle_violation(platform, id, sender_id, sender_nickname, "发送消息过于频繁")
        store_sensitive_message(redis_client, platform, id, sender_id, sender_nickname, message_content)
        return False

    # 检测重复字符
    if detect_repeated_characters(message_content):
        await handle_violation(platform, id, sender_id, sender_nickname, "发送重复字符")
        store_sensitive_message(redis_client, platform, id, sender_id, sender_nickname, message_content)
        return False

    # 检测违规词
    has_blocked_words, cleaned_message = contains_blocked_words(message_content)
    if has_blocked_words:
        await handle_violation(platform, id, sender_id, sender_nickname, "使用违规词")
        store_sensitive_message(redis_client, platform, id, sender_id, sender_nickname, message_content)
        message_content = cleaned_message
    
    # 创建消息记录
    key_local = f"{platform}:{id}:{platform}:{id}"
    message_to_save = {
        "sender_id": sender_id,
        "sender_nickname": sender_nickname,
        "message_type": message_type,
        "message_content": message_content,
        "timestamp": str(datetime.datetime.now()),
        "msg_id": msg_id,
        "platform_from": platform,
        "id_from": id
    }

    if msg_id is not None:
        # 将 msg_id 作为键存储，值可以是消息的主键或完整消息内容
        redis_client.set(f"msg_id:{msg_id}", json.dumps(message_to_save))
        logger.info(f"存储 msg_id: msg_id:{msg_id} -> {message_to_save}")

    message_content_alltext = message_content
    if noBaseContent:
        message_content = replace_blocked_words(noBaseContent)
    # 存储到所有相关key
    redis_client.rpush(key_local, json.dumps(message_to_save))
    logger.info(f"存储消息: {key_local} -> {message_to_save}")
    
    # 对于每个绑定群聊，存储key_ab/key_ba
    bind_data = bind_info['data']
    logger.info(f"绑定信息: {bind_data}")
    if platform == "QQ":
        for group in bind_data.get("YH_group_ids", []):
            if group['sync']:
                key_ab = f"{platform}:{id}:YH:{group['id']}"
                key_ba = f"YH:{group['id']}:{platform}:{id}"
                redis_client.rpush(key_ab, json.dumps(message_to_save))
                redis_client.rpush(key_ba, json.dumps(message_to_save))
    elif platform == "YH":
        for group in bind_data.get("QQ_group_ids", []):
            if group['sync']:
                key_ab = f"{platform}:{id}:QQ:{group['id']}"
                key_ba = f"QQ:{group['id']}:{platform}:{id}"
                redis_client.rpush(key_ab, json.dumps(message_to_save))
                redis_client.rpush(key_ba, json.dumps(message_to_save))
    
    bind_data = bind_info['data']
    if platform == "QQ":
        for group in bind_data.get("YH_group_ids", []):
            if group['sync']:
                await yhtools.send(recvId=group['id'], recvType="group", contentType="html", content=message_content)
    elif platform == "YH":
        for group in bind_data.get("QQ_group_ids", []):
            if group['sync']:
                try:
                    await qqtools.send("group", int(group['id']), message_content)
                except Exception as e:
                    logger.error(f"发送QQ群消息失败，群组ID: {group['id']}, 错误信息: {e}")
                    continue
    return "消息已发送到所有绑定群聊"
async def set_board_for_all_groups(platform, id, message_content, group_name, board_content):
    # 获取所有绑定信息
    bind_info = BindingManager.get_info(platform, id)
    if bind_info['status'] != 0:
        return bind_info['msg']
    
    board_content = (
        f"【提醒】\n{platform}群：{group_name} | {id}"
        f"\n  {message_content}"
    )
    bind_data = bind_info['data']
    if platform == "QQ":
        for group in bind_data.get("QQ_group_ids", []):
            if group['sync']:
                await yhtools.set_board(
                    group['id'],
                    "group", 
                    board_content
                )
                logger.info(f"发送看板云湖群 {group['id']} 设置看板: {board_content}")
        for group in bind_data.get("YH_group_ids", []):
            if group['sync']:
                await yhtools.set_board(
                    group['id'],
                    "group", 
                    board_content
                )
                logger.info(f"发送看板云湖群 {group['id']} 设置看板: {board_content}")
async def send_private_msg(platform, id, message_content):
    """发送私聊消息"""
    if platform == "QQ":
        await qqtools.send("private", int(group['id']), message_content)
    elif platform == "YH":
        await yhtools.send(recvId=id, recvType="user", contentType="text", content=message_content)
    else:
        return "平台不存在"

async def get_all_message_counts(platform, id_PF):
    """
    获取所有类型的消息数量。
    
    :param platform: 平台类型（QQ/YH）
    :param id_PF: 群聊或用户的ID
    :return: 包含所有类型消息数量的字典
    """
    # 获取本地消息数量
    key_local = f"{platform}:{id_PF}:{platform}:{id_PF}"
    local_messages = redis_client.lrange(key_local, 0, -1)
    total_count = len(local_messages) if local_messages else 0

    # 获取同步消息数量
    keys_ba = redis_client.keys(f"*:*:{platform}:{id_PF}")
    ba_messages = []
    for key in keys_ba:
        ba_messages.extend(redis_client.lrange(key, 0, -1))
    
    # 使用集合去重
    sync_messages = set(local_messages + ba_messages)
    sync_count = len(sync_messages) if sync_messages else 0

    # 获取敏感消息数量
    sensitive_key = f"sensitive_messages:{platform}:{id_PF}"
    sensitive_messages = redis_client.lrange(sensitive_key, 0, -1)
    sensitive_count = len(sensitive_messages) if sensitive_messages else 0

    # 获取活跃用户数量
    users = set()
    for msg in local_messages + ba_messages:
        message = json.loads(msg)
        users.add(message["sender_id"])
    active_users_count = len(users) if users else 0

    return {
        "code": 0,
        "msg": "获取消息数量成功",
        "total_count": total_count,
        "sync_count": sync_count,
        "sensitive_count": sensitive_count,
        "active_users_count": active_users_count
    }
async def get_messages(platform, id_PF, message_type="local", page=1, page_size=20):
    """
    通用的消息获取方法。
    
    :param platform: 平台类型（QQ/YH）
    :param id_PF: 群聊或用户的ID
    :param message_type: 消息类型（"local", "sync", "sensitive", "active_users"）
    :param page: 分页页码
    :param page_size: 分页大小
    :return: 消息详情或用户详情
    """
    if message_type == "local":
        # 获取本地消息
        key_local = f"{platform}:{id_PF}:{platform}:{id_PF}"
        total_count = redis_client.llen(key_local)
        
        # 计算分页偏移
        start = (page - 1) * page_size
        end = start + page_size - 1
        
        # 获取分页数据
        local_messages = redis_client.lrange(key_local, start, end)
        
        # 解析消息
        messages = []
        for msg in local_messages:
            message = json.loads(msg)
            messages.append({
                "sender": message["sender_nickname"],
                "content": message["message_content"],
                "timestamp": message["timestamp"]
            })
        
        # 按照时间戳倒序排列
        messages = sorted(messages, key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "code": 0,
            "msg": "成功",
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "messages": messages
        }
    
    elif message_type == "sync":
        # 获取同步消息
        key_local = f"{platform}:{id_PF}:{platform}:{id_PF}"
        local_messages = redis_client.lrange(key_local, 0, -1)
        
        keys_ba = redis_client.keys(f"*:*:{platform}:{id_PF}")
        ba_messages = []
        for key in keys_ba:
            ba_messages.extend(redis_client.lrange(key, 0, -1))
        
        all_messages = []
        seen = set()
        for msg in local_messages + ba_messages:
            if msg not in seen:
                seen.add(msg)
                message = json.loads(msg)
                all_messages.append({
                    "sender": message["sender_nickname"],
                    "content": message["message_content"],
                    "timestamp": message["timestamp"]
                })
        
        all_messages = sorted(all_messages, key=lambda x: x["timestamp"], reverse=True)
        
        total_count = len(all_messages)
        start = (page - 1) * page_size
        end = start + page_size
        messages = all_messages[start:end]
        
        return {
            "code": 0,
            "msg": "成功",
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "messages": messages
        }
    
    elif message_type == "sensitive":
        # 获取敏感消息
        sensitive_key = f"sensitive_messages:{platform}:{id_PF}"
        total_count = redis_client.llen(sensitive_key)
        
        start = (page - 1) * page_size
        end = start + page_size - 1
        
        sensitive_messages = redis_client.lrange(sensitive_key, start, end)
        
        messages = []
        for msg in sensitive_messages:
            try:
                message = json.loads(msg)
                messages.append({
                    "sender": message["sender_nickname"],
                    "content": message["message_content"],
                    "timestamp": message["timestamp"]
                })
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error parsing sensitive message: {e}")
        
        messages = sorted(messages, key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "code": 0,
            "msg": "成功",
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "messages": messages
        }
    
    elif message_type == "active_users":
        # 获取活跃用户
        key_local = f"{platform}:{id_PF}:{platform}:{id_PF}"
        messages = redis_client.lrange(key_local, 0, -1)
        
        users = {}
        for msg in messages:
            message = json.loads(msg)
            user_id = message["sender_id"]
            if user_id not in users:
                users[user_id] = {
                    "nickname": message["sender_nickname"],
                    "last_active": message["timestamp"],
                    "message_count": 0
                }
            users[user_id]["message_count"] += 1
        
        sorted_users = sorted(users.values(), key=lambda x: x["message_count"], reverse=True)
        
        total_count = len(sorted_users)
        start = (page - 1) * page_size
        end = start + page_size
        paged_users = sorted_users[start:end]
        
        return {
            "code": 0,
            "msg": "成功",
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "users": paged_users
        }
    
    else:
        return {
            "code": -1,
            "msg": "未知的消息类型",
        }