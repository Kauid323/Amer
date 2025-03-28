import re
import os
import io
import requests
from PIL import Image
from io import BytesIO
from .. import BindingManager, MessageManager, aitools, qqtools, yhtools, basetools
from datetime import datetime, timedelta
import redis
import html
import uuid
import json
import base64
from utils.config import (redis_client, admin_user_id, pass_ai_id, ban_ai_id, ai_max_length, qq_commands as commands, bot_name, bot_qq, redis_host, redis_port, redis_db, redis_password, temp_folder, replace_blocked_words)
from typing import Dict, Any
from utils import logger
import asyncio
async def send_sync_message(message_data, qqBot, group_name):
    """
    同步用户消息到群聊绑定的平台（仅适用于群聊）。
    """
    if message_data.sender_nickname:
        sender_name = message_data.sender_nickname
    else:
        sender_name = "未知用户"

    # 判断用户权限
    is_admin_or_owner = await qqtools.is_group_admin_or_owner(
        message_data.group_id,
        message_data.sender_user_id
    )
    if is_admin_or_owner:
        sender_name = sender_name
        sender_color = "#FFD700"
    else:
        sender_color = "None"

    message_content, message_content_alltext = await qqtools.process_message(
        message_data.raw_message,
        group_id=message_data.group_id,
        group_name=group_name
    )
    bind_infos = BindingManager.get_info("QQ", message_data.group_id)
    if bind_infos['status'] == 0:
        cleaned_name = replace_blocked_words(sender_name)
        message_content_html = message_content.replace('\n', '<br>')
        user_avatar_url = await qqtools.get_user_avatar_url(message_data.sender_user_id)

        if "@全体成员" in message_content_alltext:
            message_content_alltext = message_content_alltext.replace("@全体成员", "")
            await MessageManager.set_board_for_all_groups(
                platform="QQ",
                id=message_data.group_id,
                message_content=message_content_alltext,
                group_name=group_name,
                board_content=None
            )
        else:
            content_ = (
                f'<div style="display: flex; align-items: flex-start; margin-bottom: 10px;">'
                f'<img src="{user_avatar_url}" alt="用户头像" style="width: 36px; height: 36px; border-radius: 50%; margin-right: 10px;">'
                f'<div style="flex: 1;">'
                f'<strong style="font-size: 14px; color: {sender_color};">{cleaned_name}</strong>'
                f'<p style="font-size: 8px; color: #6c757d; margin-top: 2px;"><strong>用户ID: </strong>{message_data.sender_user_id}</p>'
                f'</div>'
                f'</div>'

                f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">'
                f'<p style="color: #000000;">{message_content_html}</p>'
                f'</div>'
                f'</div>'

                f'<div style="font-family: Arial, sans-serif; line-height: 1.4; font-size: 12px; color: #888;">'
                f'<details style="margin-top: 5px;">'
                f'<summary style="cursor: pointer; color: #007bff; font-size: 12px;">'
                f'详情'
                f'</summary>'
                f'<p style="margin: 3px 0;">群聊: {group_name}</p>'
                f'<p style="margin: 3px 0;">ID: {message_data.group_id}</p>'
                f'<p style="margin: 3px 0;">发送时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>'
                f'<p style="margin: 3px 0; text-align: right;"> <a href=\'https://amer.bot.anran.xyz/report?msgId={message_data.message_id}\'' \
                f' style="display: inline-block; padding: 4px 8px; background-color: #e74c3c; color: white; font-size: 10px; text-decoration: none; border-radius: 4px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); margin-top: 5px;"> 举报 </a></p>'
                f'</details>'
                f'</div>'
            )
            await MessageManager.send_to_all_bindings(
                "QQ",
                message_data.group_id,
                "html",
                message_content_alltext,
                message_data.sender_user_id,
                cleaned_name,
                noBaseContent=content_,
                msg_id=message_data.message_id
            )
async def send_ai_response_separated(message_data, qqBot, group_name=None):
    """
    单独处理并发送AI的回复。
    """
    if message_data.sender_nickname:
        sender_name = message_data.sender_nickname
    else:
        sender_name = "未知用户"

    # 调用AI生成回复
    airesp = await aitools.send(
        message_data.raw_message,
        message_data.sender_user_id,
        sender_name,
        type="qq_group" if group_name else "private",
        group_id=message_data.group_id if group_name else None,
        group_name=group_name
    )

    # 发送AI回复到群聊或私聊
    if group_name:
        await qqBot.send_group_msg(group_id=message_data.group_id, message=airesp)
    else:
        await qqBot.send_private_msg(user_id=message_data.sender_user_id, message=airesp)

    # 如果是群聊，同步AI回复到绑定的平台
    if group_name:
        # 处理AI回复内容
        message_content, _ = await qqtools.process_message(
            airesp,
            group_id=message_data.group_id,
            group_name=group_name
        )
        message_content = message_content.replace('\n', '<br>')

        # 构造AI回复的HTML内容
        content_ = (
            f'<br>'
            f'<div style="background-color: #e9f7ef; padding: 10px; border-radius: 8px; margin-bottom: 10px;">'
            f'  <strong style="color: #28a745;">Amer</strong><br>'
            f'  <p style="color: #000000;">{message_content}</p>'
            f'</div>'
            f'<p style="font-size: 10px; color: #6c757d; margin-top: 10px;">以上内容由AI生成，仅供参考，请自行核实。</p>'
            f'<div style="font-size: 12px; color: #888; line-height: 1.4; margin-top: 10px;">'
            f'  <details style="margin-top: 5px;">'
            f'    <summary style="color: #007bff; font-size: 12px; cursor: pointer;">详情</summary>'
            f'    <p style="margin: 3px 0;"><strong>群聊:</strong> {group_name}</p>'
            f'    <p style="margin: 3px 0;"><strong>ID:</strong> {message_data.group_id}</p>'
            f'  </details>'
            f'</div>'
        )

        # 同步AI回复到绑定的平台
        await MessageManager.send_to_all_bindings(
            "QQ",
            message_data.group_id,
            "html",
            message_content,
            message_data.sender_user_id,
            "Amer",
            noBaseContent=content_
        )
        logger.info(f"同步群聊AI回复: {airesp}")


# 修改消息处理器
async def msg_handler(data: Dict[str, Any], qqBot):
    message_data = MessageManager.QQMessageData(data)
    logger.info(f"收到消息: {message_data.raw_message}")

    # 私聊处理逻辑
    if message_data.message_type == "private" and message_data.raw_message.strip():
        await send_ai_response_separated(message_data, qqBot)
        return

    # 群聊处理逻辑
    elif message_data.message_type == "group":
        check_ai = False
        group_name = await qqtools.get_group_name(message_data.group_id)
        keywords = set(json.loads(redis_client.get(f"keywords:{message_data.group_id}"))) if redis_client.get(f"keywords:{message_data.group_id}") else set()

        # 处理命令
        command_request = await handle_command(message_data, qqBot)

        # 继续处理非命令消息
        if (bot_qq in message_data.raw_message or
                any(keyword in message_data.raw_message for keyword in keywords)):
            ai_enabled = redis_client.get(f"ai_enabled:{message_data.group_id}")
            if not ai_enabled:
                redis_client.set(f"ai_enabled:{message_data.group_id}", "开")
                logger.info(f"首次触发AI功能，默认开启: {message_data.group_id}")

            if not ai_enabled or ai_enabled.decode() == "开":
                check_ai = True
                # 先同步用户消息
                await send_sync_message(message_data, qqBot, group_name)

                # 再发送AI回复
                await send_ai_response_separated(message_data, qqBot, group_name)
                return
        else:
            await aitools.add_RoleMessage(
                message_data.raw_message,
                message_data.sender_user_id,
                message_data.sender_nickname,
                message_data.group_id,
                group_name=group_name
            )
        if check_ai == False:
            await send_sync_message(message_data, qqBot, group_name)
        
    # 检查命令执行结果并同步到其他平台
    if isinstance(command_request, dict):
        if command_request.get("code", 0) == 0 or command_request.get("code", 0) == -1:
            # 构造指令返回的HTML内容
            content_ = (
                f'<br>'
                f'<div style="background-color: #e9f7ef; padding: 10px; border-radius: 8px; margin-bottom: 10px;">'
                f'  <strong style="color: #28a745;">Amer</strong><br>'
                f'  <p style="color: #000000;">{command_request.get("msg", "未知指令")}</p>'
                f'</div>'
                f'<div style="font-size: 12px; color: #888; line-height: 1.4; margin-top: 10px;">'
                f'  <details style="margin-top: 5px;">'
                f'    <summary style="color: #007bff; font-size: 12px; cursor: pointer;">详情</summary>'
                f'    <p style="margin: 3px 0;"><strong>群聊:</strong> {await qqtools.get_group_name(message_data.group_id)}</p>'
                f'    <p style="margin: 3px 0;"><strong>ID:</strong> {message_data.group_id}</p>'
                f'    <p style="margin: 3px 0;"><strong>发送时间:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>'
                f'  </details>'
                f'</div>'
            )

            # 同步指令返回消息到绑定的平台
            await MessageManager.send_to_all_bindings(
                "QQ",
                message_data.group_id,
                "html",  # 使用HTML格式发送
                command_request.get("msg", "未知指令"),
                message_data.sender_user_id,
                "Amer",
                noBaseContent=content_
            )

async def handle_notice(event, qqBot):
    await aitools.log_event_to_conversation(event, qqBot)
async def handle_request(event, qqBot):
    logger.info(f"收到请求: {event}")
    if event.detail_type == 'friend':
        await qqBot.set_friend_add_request(flag=event.flag, approve=True)
    elif event.detail_type == 'group':
        await qqBot.set_group_add_request(flag=event.flag, sub_type=event.sub_type, approve=True)
    else:
        logger.warning(f"未知的请求类型: {event.detail_type}")

async def handle_command(message_data: MessageManager.QQMessageData, qqBot, type = None, is_tool = False):
    logger.info(f"MessageData: raw_message={message_data.raw_message}, "
            f"group_id={message_data.group_id}, "
            f"user_id={message_data.user_id}, "
            f"sender_user_id={message_data.sender_user_id}")
    message_data.sender_user_id = message_data.sender_user_id or message_data.user_id
    if message_data.raw_message.startswith("/"):
        command = message_data.raw_message[1:]
    else:
        command = message_data.raw_message
    logger.info(f"处理命令: {command}")
    async def check_group_admin_permission():
        if message_data.sender_user_id == 2694611137:
            return True
        if not await qqtools.is_group_admin_or_owner(message_data.group_id, message_data.sender_user_id):
            await qqBot.send_group_msg(
                group_id=message_data.group_id,
                message="抱歉，此命令仅限群主或管理员使用。"
            )
            logger.warning(f"用户 {message_data.sender_user_id} 尝试执行管理员命令: {command}")
            return False
        return True
    
    if command == "帮助":
        overview = "📌 指令指南 📌\n\n"
        for idx, cmd in enumerate(commands.keys(), start=1):
            overview += f"{idx}. {cmd}\n"
        overview += "\n输入 /帮助 <编号> 查看详细信息"
        await qqBot.send_group_msg(group_id=message_data.group_id, message=overview)
        logger.info(f"发送帮助信息: {overview}")
        return {"code": 0, "msg": overview}
    elif command.startswith("帮助 "):
        try:
            command_number = int(command.split()[1])
            if 1 <= command_number <= len(commands):
                cmd_name = list(commands.keys())[command_number - 1]
                cmd_detail = commands[cmd_name]
                await qqBot.send_group_msg(group_id=message_data.group_id, message=f"📌 {cmd_name} 📌\n\n{cmd_detail}")
                logger.info(f"发送详细帮助信息: {cmd_name}, 内容: {cmd_detail}")
                return {"code": 0, "msg": f"发送详细帮助信息: {cmd_name}, 内容: {cmd_detail}"}
            else:
                msg = "无效编号，请使用 /帮助 <编号> 查看详细信息"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.warning(f"无效的指令编号: {command_number}")
                return {"code": -1, "msg": msg}
        except ValueError:
            msg = "指令格式错误，请使用 /帮助 <编号> 查看详细信息"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"无效的指令编号: {command}")
            return {"code": -1, "msg": msg}
    elif command.startswith("绑定列表"):
        bind_infos = BindingManager.get_info("QQ", message_data.group_id)
        if bind_infos['status'] == 0:
            menu = f"QQ群: {await qqtools.get_group_name(message_data.group_id)}\n\n"
            YH_group_ids = bind_infos['data']['YH_group_ids']
            YH_item_number = 1
            if YH_group_ids:
                menu += "云湖群:\n"
                for YH_group in YH_group_ids:
                    sync_mode = "未设置"
                    if YH_group['sync'] and YH_group['binding_sync']:
                        sync_mode = "互通"
                    elif YH_group['sync'] and YH_group['binding_sync'] is False:
                        sync_mode = "单向-QQ到云湖"
                    elif YH_group['sync'] is False and YH_group['binding_sync']:
                        sync_mode = "单向-云湖到QQ"

                    menu += f"{YH_item_number}. 群号:{YH_group['id']} ({sync_mode})\n"
                    YH_item_number += 1
            await qqBot.send_group_msg(group_id=message_data.group_id, message=menu)
            logger.info(f"发送群列表信息: {menu}")
            return {"code": 0, "msg": menu}
    elif command.startswith("绑定"):
        if not await check_group_admin_permission():
            return {"code": -1, "msg": "命令执行失败, 用户无权限"}
            
        parts = command.split()
        if len(parts) < 2:
            msg = "指令格式错误，请使用 /绑定 <平台> <id>\n支持平台：yh（云湖群）"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"绑定指令格式错误: {command}")
            return {"code": -1, "msg": msg}
            
        platform = parts[1]
        if platform == "yh":
            binding_status = BindingManager.bind("QQ", "YH", message_data.group_id, parts[2])
            if binding_status['status'] == 0:
                msg = "云湖群已成功绑定"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.info(f"云湖群已成功绑定: {message_data.group_id}")
                return {"code": 0, "msg": msg}
            else:
                msg = binding_status['msg']
                await qqBot.send_group_msg(message = msg, group_id=message_data.group_id)
                return {"code": -1, "msg": msg}
        elif platform == "mc":
            binding_status = BindingManager.bind("QQ", "MC", message_data.group_id, parts[2])
            if binding_status['status'] == 0:
                msg = "Minecraft服务器已成功绑定"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.info(f"Minecraft服务器已成功绑定: {message_data.group_id}")
                return {"code": 0, "msg": msg}
            else:
                msg = binding_status['msg']
                await qqBot.send_group_msg(message = msg, group_id=message_data.group_id)
                return {"code": -1, "msg": msg}
        else:
            msg = "不支持的平台，请使用 /绑定 <平台> <id>\n支持平台：yh（云湖群）"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"不支持的平台: {platform}")
            return {"code": -1, "msg": msg}
    
    elif command.startswith("解绑"):
        if not await check_group_admin_permission():
            return {"code": -1, "msg": "命令执行失败, 用户无权限"}
        
        parts = command.split()
        if len(parts) < 2:
            msg = "指令格式错误，请使用 /解绑 <平台>\n支持平台：yh（云湖群）"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"解绑指令格式错误: {command}")
            return {"code": -1, "msg": msg}

        platform = parts[1].lower()
        id = parts[2]
        if id is None:
            msg = "指令格式错误，请使用 /解绑 <平台> <id>\n支持平台：yh（云湖群）"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"解绑指令格式错误: {command}")
            return {"code": -1, "msg": msg}
        if platform == "yh":
            unbind_status = BindingManager.unbind("QQ", "YH", message_data.group_id, id)
            if unbind_status['status'] == 0:
                msg = "云湖群已成功解绑"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.info(f"云湖群已成功解绑: {message_data.group_id}")
                return {"code": 0, "msg": msg}
            else:
                await qqBot.send_group_msg(group_id=message_data.group_id, message=unbind_status['msg'])
                return {"code": -1, "msg": unbind_status['msg']}
        elif platform == "mc":
            unbind_status = BindingManager.unbind("QQ", "MC", message_data.group_id, id)
            if unbind_status['status'] == 0:
                msg = "Minecraft服务器已成功解绑"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.info(f"Minecraft服务器已成功解绑: {message_data.group_id}")
                return {"code": 0, "msg": msg}
            else:
                await qqBot.send_group_msg(group_id=message_data.group_id, message=unbind_status['msg'])
                return {"code": -1, "msg": unbind_status['msg']}
        elif platform == "all" or platform == "全部" or platform == "所有":
            unbind_status = BindingManager.unbind_all("QQ", message_data.group_id)
            if unbind_status['status'] == 0:
                msg = "所有绑定已成功解绑"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.info(f"所有绑定已成功解绑: {message_data.group_id}")
            else:
                await qqBot.send_group_msg(group_id=message_data.group_id, message=unbind_status['msg'])
                return {"code": -1, "msg": unbind_status['msg']}
        else:
            msg = "不支持的平台，请使用 /解绑 <平台>\n支持平台：yh（云湖群）"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"不支持的平台: {platform}")
            return {"code": -1, "msg": msg}
    
    elif command.startswith("清除记忆"):
        conversation_key = f'conversation:{message_data.group_id}'
        input_history_key = f'input_history:{message_data.group_id}'
        
        if redis_client.exists(conversation_key):
            redis_client.delete(conversation_key)
            logger.info(f"已清除群 {message_data.group_id} 的对话记录")
        
        if redis_client.exists(input_history_key):
            redis_client.delete(input_history_key)
            logger.info(f"已清除群 {message_data.group_id} 的输入历史记录")
        
        await qqBot.send_group_msg(group_id=message_data.group_id, message="Amer的小脑袋瓜子里感觉有什么东西飞出去了")
        logger.info(f"通知群 {message_data.group_id} 记忆已成功清除")
        return {"code": 0, "msg": "记忆已成功清除"}
    
    elif command.startswith("触发关键词"):
        parts = command.split()
        if len(parts) < 2:
            msg = "格式错误，请使用 /触发关键词 <添加/删除/清空/列表>"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"关键词管理格式错误: {command}")
            return {"code": -1, "msg": msg}
        sub_command = parts[1]
        if sub_command == "添加":
            if len(parts) < 3:
                msg = "格式错误，请使用 /触发关键词 添加 <关键词>"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.warning(f"添加触发关键词格式错误: {command}")
                return {"code": -1, "msg": msg}
            
            keyword = parts[2].strip()
            keywords_ai = redis_client.get(f"keywords:{message_data.group_id}")
            if keywords_ai:
                keywords_ai = set(json.loads(keywords_ai))
            else:
                keywords_ai = set()

            if keyword in keywords_ai:
                msg = f"关键词 '{keyword}' 已经存在"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.warning(f"关键词 '{keyword}' 已经存在: {message_data.group_id}")
                return {"code": -1, "msg": msg}

            keywords_ai.add(keyword)
            redis_client.set(f"keywords:{message_data.group_id}", json.dumps(list(keywords_ai)))
            msg = f"已添加触发关键词: {keyword}"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.info(f"已添加触发关键词: {keyword}")
            return {"code": 0, "msg": msg}
        elif sub_command == "删除":
            if len(parts) < 3:
                msg = "格式错误，请使用 /触发关键词 删除 <关键词>"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.warning(f"删除触发关键词格式错误: {command}")
                return {"code": -1, "msg": msg}
            keyword = parts[2].strip()

            keywords_ai = redis_client.get(f"keywords:{message_data.group_id}")
            if keywords_ai:
                keywords_ai = set(json.loads(keywords_ai))
                if keyword in keywords_ai:
                    keywords_ai.remove(keyword)
                    msg = f"关键词 '{keyword}' 删除成功"
                    redis_client.set(f"keywords:{message_data.group_id}", json.dumps(list(keywords_ai)))
                    await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                    logger.info(f"关键词 '{keyword}' 已从群 {message_data.group_id} 删除")
                    return {"code": 0, "msg": msg}
                else:
                    msg = f"关键词 '{keyword}' 不存在"
                    await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                    logger.warning(f"关键词 '{keyword}' 不存在于群 {message_data.group_id}")
                    return {"code": -1, "msg": msg}
            else:
                msg = "没有设置任何关键词"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.warning(f"群 {message_data.group_id} 没有设置任何关键词")
                return {"code": -1, "msg": msg}
        
        elif sub_command == "清空":
            msg = "已清空所有关键词"
            redis_client.delete(f"keywords:{message_data.group_id}")
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.info(f"群 {message_data.group_id} 已清空所有关键词")
            return {"code": 0, "msg": msg}
        elif sub_command == "列表":
            keywords = redis_client.get(f"keywords:{message_data.group_id}")
            if keywords:
                keywords = json.loads(keywords)
                keywords_str = "\n".join(keywords)
                msg = f"关键词列表:\n{keywords_str}"
            else:
                msg = "没有设置任何关键词"
            
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.info(f"发送关键词列表: {msg}")
            return {"code": 0, "msg": msg}
        else:
            logger.warning(f"关键词管理指令格式错误: {command}")
            msg = "格式错误，请使用 /触发关键词 <添加/删除/清空/列表>"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            return {"code": -1, "msg": msg}
        
    elif command.startswith("系统提示词"):

        parts = command.split()
        if len(parts) < 2:
            msg = "格式错误，请使用 /系统提示词 <设置/清除/查看>"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"提示词管理格式错误: {command}")
            return {"code": -1, "msg": msg}
        sub_command = parts[1]
        if sub_command == "设置":
            if len(parts) < 3:
                msg = "格式错误，请使用 /系统提示词 设置 <提示词>"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
                logger.warning(f"设置提示词格式错误: {command}")
                return {"code": -1, "msg": msg}
            custom_system_prompt = parts[2].strip()
            redis_client.set(f"custom_system_prompt:{message_data.group_id}", custom_system_prompt)
            msg = f"系统提示词已设置为: {custom_system_prompt}"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.info(f"系统提示词已设置为: {custom_system_prompt}")
            return {"code": 0, "msg": msg}
        elif sub_command == "清除":
            msg = "系统提示词已清除"
            redis_client.delete(f"custom_system_prompt:{message_data.group_id}")
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.info(f"系统提示词已清除: {message_data.group_id}")
            return {"code": 0, "msg": msg}
        elif sub_command == "查看":
            custom_system_prompt = redis_client.get(f"custom_system_prompt:{message_data.group_id}")
            if custom_system_prompt:
                msg = f"当前系统提示词为: {custom_system_prompt.decode()}"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            else:
                msg = f"当前没有设置系统提示词"
                await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            return {"code": 0, "msg": msg}
        else:
            msg = "格式错误，请使用 /系统提示词 <设置/清除/查看>"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"提示词管理指令格式错误: {command}")
            return {"code": -1, "msg": msg}

    elif command.startswith("隐私模式"):
        parts = command.split()
        logger.info(f"收到指令: {parts}")
        if len(parts) < 2:
            msg = "无效子指令，请使用 /隐私模式 <开|关|最大上文提示>"
            await qqBot.send_group_msg(group_id=message_data.group_id, message= msg)
            logger.warning(f"缺少子指令: {command}")
            return {"code": -1, "msg": msg}
        if parts[1] in ["开", "关"]:
            switch_status = parts[1]
            msg = f"隐私模式已设置为 {switch_status}"
            redis.Redis(host=redis_host, port=redis_port, db=redis_db, password=redis_password).set(f"privacy_switch:{message_data.group_id}", switch_status)
            await qqBot.send_group_msg(group_id=message_data.group_id, message= msg)
            logger.info(f"隐私模式已设置为: {switch_status}")
            return {"code": -1, "msg": msg}
        elif parts[1] == "最大上文提示":
            if len(parts) < 3:
                msg = "指令格式错误，请使用 /隐私模式 最大上文提示 <数量>, 缺少数量参数，请输入一个整数"
                await qqBot.send_group_msg(group_id=message_data.group_id, message= msg)
                logger.warning(f"缺少数量参数: {command}")
                return {"code": -1, "msg": msg}
            try:
                max_context_count = int(parts[2])
                msg = f"最大上文提示数已设置为 {max_context_count}"
                redis.Redis(host=redis_host, port=redis_port, db=redis_db, password=redis_password).set(f"max_context_count:{message_data.group_id}", max_context_count)
                await qqBot.send_group_msg(group_id=message_data.group_id, message= msg)
                logger.info(f"最大上文提示数已设置为: {max_context_count}")
                return {"code": -1, "msg": msg}
            except ValueError:
                msg = "指令格式错误，请使用 /隐私模式 最大上文提示 <数量>, 缺少数量参数，请输入一个整数"
                await qqBot.send_group_msg(group_id=message_data.group_id, message= msg)
                logger.warning(f"无效的数量: {parts[2]}")
                return {"code": -1, "msg": msg}
        else:
            msg = "无效子指令，请使用 /隐私模式 <开|关|最大上文提示>"
            await qqBot.send_group_msg(group_id=message_data.group_id, message= msg)
            logger.warning(f"无效的数量: {parts[2]}")
            return {"code": -1, "msg": msg}

    elif command.startswith("ai开关") or command.startswith("AI开关"):
        if not await check_group_admin_permission():
            return {"code": -1, "msg": "命令执行失败, 用户无权限"}
        
        parts = command.split()
        if len(parts) < 2:
            msg = "格式错误，请使用 /ai开关 <开/关>"
            await qqBot.send_group_msg(group_id=message_data.group_id, message= msg)
            logger.warning(f"AI开关格式错误: {command}")
            return {"code": -1, "msg": msg}
        action = parts[1]
        if action in ["开", "关"]:
            msg = f"AI功能已{action}"
            redis_client.set(f"ai_enabled:{message_data.group_id}", "开" if action == "开" else "关")
            await qqBot.send_group_msg(group_id=message_data.group_id, message= msg)
            logger.info(f"AI功能已{action}: {message_data.group_id}")
            return {"code": -1, "msg": msg}

        else:
            msg = "无效的子命令，请使用 <开|关>"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"无效的AI开关子命令: {command}")
            return {"code": -1, "msg": msg}

    elif command.startswith("上传参考语音"):
        parts = command.split(maxsplit=1)
        if len(parts) < 2:
            msg = "请提供备注名称，例如：/上传参考语音 王八"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            return {"code": 400, "msg": msg}

        remark = parts[1]
        token = str(uuid.uuid4())

        redis_client.set(f"voice_upload_token:{token}", json.dumps({
            "user_id": message_data.sender_user_id,
            "user_name": message_data.sender_nickname,
            "remark": remark
        }), ex=3600)

        web_url = f"https://amer.bot.anran.xyz/upload-voice-page?token={token}"
        msg = (
            f"请访问以下网页上传参考音频文件：\n"
            f"{web_url}\n\n"
            f"上传时需要提供以下信息：\n"
            f"- 音频文件 (支持 MP3、WAV 等格式)\n"
            f"- 对应的文字内容\n\n"
            f"备注已自动填写为：{remark}\n"
            f"注意：Token 有效时间为 1 小时。"
        )
        await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
        logger.info(f"生成上传语音 Token: {token}, 用户ID: {message_data.sender_user_id}, 备注: {remark}")
        return {"code": 0, "msg": msg}
    elif command.startswith("生成语音"):
        if len(command.split()) < 3:
            msg = "格式错误，请使用 /生成语音 <备注> 内容"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"生成语音指令格式错误: {command}")
            return {"code": -1, "msg": msg}

        parts = command.split(maxsplit=2)
        custom_name = parts[1].strip()
        content = parts[2].strip()

        try:
            from .. import aitools
            audio_file_path = await aitools.generate_speech(custom_name, content)
            cq_code = f"[CQ:record,file={audio_file_path}]"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=cq_code)
            logger.info(f"生成语音成功: {audio_file_path}")
            return {"code": 0, "msg": cq_code}
        except Exception as e:
            logger.error(f"生成语音失败: {e}")
            return {"code": -1, "msg": f"生成语音失败: {str(e)}"}
    elif command.startswith("查看备注"):
        parts = command.split()
        page_size = 10

        if len(parts) == 1:
            page = 1
            search_keyword = None
        elif len(parts) == 2:
            if parts[1].isdigit():
                page = int(parts[1])
                search_keyword = None
            else:
                page = 1
                search_keyword = parts[1]
        elif len(parts) == 3 and parts[1] == "搜索":
            page = 1
            search_keyword = parts[2]
        else:
            msg = "格式错误，请使用 /查看备注 [页码] 或 /查看备注 搜索 <关键词>"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            return {"code": -1, "msg": msg}

        cursor = 0
        all_notes = []
        while True:
            cursor, keys = redis_client.scan(cursor=cursor, match="voice_style:*")
            for key in keys:
                note_data = json.loads(redis_client.get(key))
                note_name = key.decode().split(":")[1]
                all_notes.append({
                    "name": note_name,
                    "user_id": note_data["user_id"],
                    "user_name": note_data["user_name"]
                })
            if cursor == 0:
                break
        
        if search_keyword:
            all_notes = [note for note in all_notes if search_keyword.lower() in note["name"].lower()]

        total_notes = len(all_notes)
        total_pages = (total_notes + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        notes_on_page = all_notes[start_index:end_index]

        if notes_on_page:
            msg_lines = [f"当前页: {page}/{total_pages}，共 {total_notes} 条备注\n"]
            for idx, note in enumerate(notes_on_page, start=start_index + 1):
                msg_lines.append(f"{idx}. {note['name']} 【{note['user_name']}提供】")
            msg_lines.append("\n- 相关指令: /生成语音 <备注> <内容>")
            msg = "\n".join(msg_lines)
        else:
            msg = "没有找到相关备注"

        await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
        logger.info(f"发送备注列表: {msg}")
        return {"code": 0, "msg": msg}
    elif command.startswith("封禁"):
        if message_data.sender_user_id != 2694611137:
            await qqBot.send_group_msg(
                group_id=message_data.group_id,
                message="喵~抱歉呢，只有主人才能使用这个命令哦！"
            )
            logger.warning(f"非开发者尝试执行封禁命令: {command}")
            return {"code": -1, "msg": "命令执行失败, 用户无权限"}

        parts = command.split()
        if len(parts) < 6:
            msg = "喵呜~指令格式不对哦！正确用法是：/封禁 平台 群聊id 用户id 原因 秒"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"封禁指令格式错误: {command}")
            return {"code": -1, "msg": msg}

        platform = parts[1].strip().upper()  # 目标平台
        group_id = parts[2].strip()          # 通知群聊 ID
        user_id = parts[3].strip()           # 被封禁用户 ID
        reason = parts[4].strip()            # 封禁原因
        try:
            duration = int(parts[5].strip()) # 封禁时长（秒）
        except ValueError:
            msg = "喵？封禁时长必须是整数哦（单位为秒），-1 表示永远封禁呢~"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"无效的封禁时长: {parts[5]}")
            return {"code": -1, "msg": msg}

        # 调用封禁接口
        ban_status = await basetools.add_to_blacklist(user_id, reason, duration)
        if ban_status:
            # 获取用户名
            if platform == "QQ" or platform == "qq":
                user_name = await qqtools.get_user_nickname(user_id)
            elif platform == "YH" or platform == "yh":
                user_name = await yhtools.get_user_nickname(user_id)
            else:
                user_name = user_id

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

            
            if platform == "QQ" or platform == "qq":
                await qqBot.send_group_msg(group_id=group_id, message=notify_message_text)
                await MessageManager.send_to_all_bindings(
                    "QQ",
                    group_id,
                    "html",
                    notify_message_html,
                    0,
                    "Amer"
                )

            elif platform == "YH" or platform == "yh":
                await yhtools.send(recvId=group_id, recvType="group", contentType="html", content=notify_message_html)
                await MessageManager.send_to_all_bindings(
                    "YH",
                    group_id,
                    "text",
                    notify_message_text,
                    0,
                    "Amer"
                )
            else:
                await qqBot.send_group_msg(group_id=message_data.group_id, message=f"未知平台: {platform}")
            
            # 发送确认消息
            await qqBot.send_group_msg(group_id=message_data.group_id, message=f"用户 {user_name} (ID: {user_id}) 已成功封禁")
            logger.info(f"已封禁用户 {user_id}，通知已发送到 {platform}:{group_id}")
            return {"code": 0, "msg": f"用户 {user_name} (ID: {user_id}) 已成功封禁"}
        else:
            msg = f"哎呀呀~封禁失败了喵：{ban_status['message']}"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.error(f"封禁用户 {user_id} 失败: {ban_status['message']}")
            return {"code": -1, "msg": msg}
    elif command.startswith("删除语音"):
        parts = command.split(maxsplit=1)
        if len(parts) < 2:
            msg = "格式错误，请使用 /删除语音 <备注>"
            await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
            logger.warning(f"删除语音指令格式错误: {command}")
            return {"code": -1, "msg": msg}

        remark = parts[1].strip()
        voice_key = f"voice_style:{remark}"

        # 删除 Redis 中的记录
        redis_client.delete(voice_key)
        msg = f"备注为 '{remark}' 的语音记录已成功删除"
        await qqBot.send_group_msg(group_id=message_data.group_id, message=msg)
        logger.info(f"备注为 '{remark}' 的语音记录已成功删除")
        return {"code": 0, "msg": msg}
    elif type == "/":
        await qqBot.send_group_msg(group_id=message_data.group_id, message=f"未知指令或错误使用的指令: {command}")
        logger.warning(f"未知指令: {command}")
        return {"code": -2, "msg": "未知指令", "data": {"command": command}}
