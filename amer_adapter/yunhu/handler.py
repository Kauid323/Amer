import json
import re
from .. import BindingManager, MessageManager
from utils import logger
import uuid
import markdown
from typing import Dict, Any
from utils.config import(temp_folder, message_yh, message_yh_followed, bot_qq, replace_blocked_words)
import os

from .. import qqtools, yhtools

async def handler(data: Dict[str, Any], qqBot):
    message_data = MessageManager.YunhuMessageData(data)
    message_data.qqBot = qqBot
    logger.info(f"源:{data}")
    event_handlers = {
        "message.receive.normal": handle_normal_message,
        "message.receive.instruction": handle_instruction_message,
        "bot.followed": handle_bot_followed,
        "bot.unfollowed": handle_bot_unfollowed,
        "bot.setting": handle_bot_setting,
        "group.join": handle_group_join,
        "group.leave": handle_group_leave,
        "button.report.inline": handle_button_event,
    }

    handler = event_handlers.get(message_data.header_event_type)
    if handler:
        await handler(message_data)
    else:
        logger.warning(f"未知事件类型: {message_data.header_event_type}")

async def handle_normal_message(message_data: MessageManager.YunhuMessageData):
    logger.info(f"收到来自 {message_data.sender_nickname} 的普通消息: {message_data.message_content}")
    
    cleaned_name = replace_blocked_words(message_data.sender_nickname)
    message_content = message_data.message_content
    
    # 获取群名称并格式化
    group_name = await yhtools.get_group_name(message_data.message_chat_id)
    formatted_group_info = f"[{group_name}] {cleaned_name}({message_data.sender_id})"
    
    if message_data.image_url:
        # 图片消息排版
        text = f"{formatted_group_info}: [CQ:image,file={message_data.image_url}]"
    elif message_content:
        # 文本消息排版
        text = f"{formatted_group_info}: {message_content}"
    else:
        return
    
    # 发送消息到所有绑定
    await MessageManager.send_to_all_bindings(
        "YH",
        message_data.message_chat_id,
        "text",
        message_content,
        message_data.sender_id,
        message_data.sender_nickname,
        noBaseContent=text
    )

async def handle_instruction_message(message_data: MessageManager.YunhuMessageData):
    if message_data.message_chat_type == "group":
        if message_data.command_name == "帮助":
            await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "markdown", content=message_yh)
            return
        elif message_data.command_name == "群列表":
            bind_infos = BindingManager.get_info("YH", message_data.message_chat_id)
            if bind_infos['status'] == 0:
                # 获取云湖群名称
                yunhu_group_name = await yhtools.get_group_name(message_data.message_chat_id)
                menu = f"## 🌟 云湖群: {yunhu_group_name} 绑定信息\n\n"

                # QQ群信息
                QQ_group_ids = bind_infos['data'].get('QQ_group_ids', [])
                if QQ_group_ids:
                    menu += "### 📋 QQ群列表\n\n"
                    for index, QQ_group in enumerate(QQ_group_ids, start=1):
                        sync_mode = "未设置"
                        if QQ_group['sync'] and QQ_group['binding_sync']:
                            sync_mode = "互通"
                        elif QQ_group['sync'] and QQ_group['binding_sync'] is False:
                            sync_mode = "单向-云湖到QQ"
                        elif QQ_group['sync'] is False and QQ_group['binding_sync']:
                            sync_mode = "单向-QQ到云湖"
                        
                        group_name = await qqtools.get_group_name(QQ_group['id'])
                        menu += f"{index}. **{group_name}** ({QQ_group['id']}) - 同步模式: {sync_mode}\n"
                    menu += "\n---\n"

                # MC服务器信息
                MC_server_ids = bind_infos['data'].get('MC_server_ids', [])
                if MC_server_ids:
                    menu += "### 🎮 MC服务器列表\n\n"
                    for index, MC_server in enumerate(MC_server_ids, start=1):
                        sync_mode = "未设置"
                        if MC_server['sync'] and MC_server['binding_sync']:
                            sync_mode = "互通"
                        elif MC_server['sync'] and MC_server['binding_sync'] is False:
                            sync_mode = "单向-云湖到MC"
                        elif MC_server['sync'] is False and MC_server['binding_sync']:
                            sync_mode = "单向-MC到云湖"
                        
                        server_name = MC_server.get('name', "未知服务器")
                        menu += f"{index}. **{server_name}** ({MC_server['id']}) - 同步模式: {sync_mode}\n"
                    menu += "\n---\n"

                # 如果没有绑定任何群或服务器
                if not QQ_group_ids and not MC_server_ids:
                    menu += "当前云湖群未绑定任何QQ群或MC服务器。\n"

                # 发送消息
                await yhtools.send(
                    message_data.message_chat_id,
                    message_data.message_chat_type,
                    "markdown",
                    content=menu
                )
            else:
                await yhtools.send(
                    message_data.message_chat_id,
                    message_data.message_chat_type,
                    "text",
                    content=bind_infos['msg']
                )
        elif message_data.command_name == "绑定":
            from_infos = message_data.message_content_base.get("formJson", {})
            results = []
            selected_platform = None
            group_ids = []

            # 定义处理逻辑
            def handle_iomhvq(id_value):
                """处理绑定平台的选择"""
                return "QQ" if id_value == "QQ" else "MC"

            def handle_ifbygx(id_value):
                """处理输入的群组ID"""
                if id_value is not None:
                    return [group_id.strip() for group_id in re.split(r'[,\，]', id_value) if group_id.strip()]
                else:
                    return []

            # 遍历表单信息并处理
            for from_info in from_infos.values():
                id = from_info.get('id')
                id_value = from_info.get('value', from_info.get('selectValue'))
                valid_setting_ids = ['iomhvq', 'ifbygx']

                if id not in valid_setting_ids:
                    logger.error(f"无效的设置ID: {id}")
                    return

                # 根据id选择处理逻辑
                if id == "iomhvq":
                    selected_platform = handle_iomhvq(id_value)
                elif id == "ifbygx":
                    group_ids = handle_ifbygx(id_value)

            # 处理绑定逻辑
            if not selected_platform:
                results.append("请选择需要绑定的平台")
            elif not group_ids:
                results.append("请输入需要绑定的群组ID")
            else:
                member_info = await message_data.qqBot.get_group_list()
                for group_id in group_ids[:]:
                    is_in_group = False

                    if selected_platform == "QQ":
                        group_id = group_id.strip()
                        if not group_id.isdigit():
                            results.append(f"绑定失败, 无效的QQ群号: {group_id}")
                            continue

                        for group in member_info:
                            if group['group_id'] == int(group_id):
                                is_in_group = True
                                break

                        if not is_in_group:
                            results.append(f"绑定失败, 机器人不在QQ群{group_id}中")
                            continue

                    # 调用绑定接口
                    bind_result = BindingManager.bind("YH", selected_platform, message_data.message_chat_id, group_id)
                    logger.info(f"绑定状态: {bind_result}")

                    if bind_result["status"] == 0:
                        if selected_platform == "QQ":
                            await message_data.qqBot.send_group_msg(
                                group_id=int(group_id),
                                message=f"此群已通过Amer和云湖群聊{message_data.message_chat_id}成功绑定,默认同步模式为全同步.请测试同步功能是否正常!"
                            )
                        
                        results.append(f"{selected_platform}群组 {group_id} 绑定成功")

                    else:
                        results.append(f"{selected_platform}群组 {group_id} 绑定失败: {bind_result['msg']}")

            # 发送结果消息
            result_message = "\n".join(results)
            await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=result_message)
        elif message_data.command_name == "解绑":
            from_infos = message_data.message_content_base.get("formJson", {})
            results = []
            jb_switch_status = False
            selected_platform = None
            group_ids = []

            # 定义处理逻辑
            def handle_yvybln(id_value):
                """处理解绑全部绑定的开关"""
                nonlocal jb_switch_status
                if id_value is True:
                    unbind_status = BindingManager.unbind_all("YH", message_data.message_chat_id)
                    if unbind_status['status'] == 0:
                        results.append("已解绑所有关联平台")
                        return True
                    else:
                        results.append(f"解绑失败: {unbind_status['msg']}")
                        return True
                else:
                    jb_switch_status = True
                    return False

            def handle_nfadxy(id_value):
                """处理解绑平台的选择"""
                return "QQ" if id_value == "QQ" else "MC"

            def handle_ubzlvu(id_value):
                """处理输入的群组ID"""
                if id_value is not None:
                    return [group_id.strip() for group_id in re.split(r'[,\，]', id_value) if group_id.strip()]
                else:
                    return []

            # 遍历表单信息并处理
            for from_info in from_infos.values():
                id = from_info.get('id')
                id_value = from_info.get('value', from_info.get('selectValue'))
                valid_setting_ids = ['yvybln', 'nfadxy', 'ubzlvu']

                if id not in valid_setting_ids:
                    logger.error(f"无效的设置ID: {id}")
                    return

                # 根据id选择处理逻辑
                if id == "yvybln":
                    if handle_yvybln(id_value):
                        break  # 解绑全部后直接退出
                elif id == "nfadxy":
                    selected_platform = handle_nfadxy(id_value)
                elif id == "ubzlvu":
                    group_ids = handle_ubzlvu(id_value)

            # 处理解绑逻辑
            if not jb_switch_status and selected_platform:
                if group_ids:
                    for group_id in group_ids:
                        unbind_status = BindingManager.unbind("YH", selected_platform, message_data.message_chat_id, group_id)
                        if unbind_status['status'] == 0:
                            results.append(f"成功解绑{selected_platform}群号: {group_id}")
                        else:
                            results.append(f"解绑{selected_platform}群号失败: {unbind_status['msg']}")
                else:
                    results.append("请输入需要解绑的群组ID")
            elif jb_switch_status and not group_ids:
                results.append("请输入需要解绑的QQ群或选择解绑全部绑定")

            # 发送结果消息
            result_message = "\n".join(results)
            await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=result_message)
        elif message_data.command_name == "同步模式":
            from_infos = message_data.message_content_base.get("formJson", {})
            results = []
            selected_platform = None
            group_ids = []

            # 定义处理逻辑
            def handle_vadtwo(id_value):
                """处理全局同步状态的选择"""
                sync_type = id_value
                if id_value == "全同步":
                    return {"QQ": True, "YH": True, "MC": True}, sync_type
                elif id_value == "QQ到云湖":
                    return {"QQ": False, "YH": True, "MC": False}, sync_type
                elif id_value == "云湖到QQ":
                    return {"YH": False, "QQ": True, "MC": False}, sync_type
                elif id_value == "MC到云湖":
                    return {"MC": False, "YH": True, "QQ": False}, sync_type
                elif id_value == "云湖到MC":
                    return {"YH": False, "MC": True, "QQ": False}, sync_type
                elif id_value == "停止":
                    return {"QQ": False, "YH": False, "MC": False}, sync_type
                else:
                    logger.error(f"无效的同步类型: {id_value}")
                    return None, None

            def handle_ewgmdw(id_value):
                """处理平台选择"""
                return "QQ" if id_value == "QQ" else "MC"

            def handle_plylap(id_value):
                """处理输入的ID"""
                if id_value is not None:
                    return [group_id.strip() for group_id in re.split(r'[,\，]', id_value) if group_id.strip()]
                else:
                    return []

            # 遍历表单信息并处理
            sync_data, sync_type = None, None

            for from_info in from_infos.values():
                id = from_info.get('id')
                id_value = from_info.get('value', from_info.get('selectValue'))
                valid_setting_ids = ['vadtwo', 'ewgmdw', 'plylap']

                if id not in valid_setting_ids:
                    logger.error(f"无效的设置ID: {id}")
                    return

                # 根据id选择处理逻辑
                if id == "vadtwo":
                    sync_data, sync_type = handle_vadtwo(id_value)
                elif id == "ewgmdw":
                    selected_platform = handle_ewgmdw(id_value)
                elif id == "plylap":
                    group_ids = handle_plylap(id_value)

            # 处理同步逻辑
            if sync_data is None:
                results.append("请选择有效的同步状态")
            else:
                if selected_platform:
                    # 对指定平台进行同步设置
                    if group_ids:
                        for group_id in group_ids:
                            sync_status = BindingManager.set_sync("YH", selected_platform, message_data.message_chat_id, group_id, sync_data)
                            if sync_status['status'] == 0:
                                results.append(f"成功设置{selected_platform}群号 {group_id} 的同步模式为: {sync_type}")
                            else:
                                results.append(f"设置{selected_platform}群号 {group_id} 的同步模式失败: {sync_status['msg']}")
                    else:
                        sync_status = BindingManager.set_all_sync("YH", message_data.message_chat_id, sync_data)
                        if sync_status['status'] == 0:
                            results.append(f"已更改所有绑定的同步模式为: {sync_type}")
                        else:
                            results.append(f"设置同步模式失败: {sync_status['msg']}")
                else:
                    # 对所有平台进行同步设置
                    if group_ids:
                        for group_id in group_ids:
                            for platform in ["QQ", "MC"]:
                                sync_status = BindingManager.set_sync("YH", platform, message_data.message_chat_id, group_id, sync_data)
                                if sync_status['status'] == 0:
                                    results.append(f"成功设置{platform}群号 {group_id} 的同步模式为: {sync_type}")
                                else:
                                    results.append(f"设置{platform}群号 {group_id} 的同步模式失败: {sync_status['msg']}")
                    else:
                        sync_status = BindingManager.set_all_sync("YH", message_data.message_chat_id, sync_data)
                        if sync_status['status'] == 0:
                            results.append(f"已更改所有绑定的同步模式为: {sync_type}")
                        else:
                            results.append(f"设置同步模式失败: {sync_status['msg']}")

            # 发送结果消息
            result_message = "\n".join(results)
            await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=result_message)
    
    else:
        if message_data.command_name == "帮助":
            await yhtools.send(message_data.sender_id, "user", "markdown", content=message_yh_followed)
        else:
            await yhtools.send(message_data.sender_id, "user", "text", content="请在群内使用指令,您目前可且仅可以使用/帮助命令")
    logger.info(f"Received instruction message from {message_data.sender_nickname}: {message_data.message_content} (Command: {message_data.command_name})")

async def handle_bot_followed(message_data: MessageManager.YunhuMessageData):
    await yhtools.send(message_data.userid, "user", "markdown", content=message_yh_followed)
    logger.info(f"{message_data.sender_nickname} 关注了机器人")

async def handle_bot_unfollowed(message_data: MessageManager.YunhuMessageData):
    logger.info(f"{message_data.sender_nickname} 取消关注了机器人")

async def handle_bot_setting(message_data: dict):
    pass
    
async def handle_group_join(message_data: MessageManager.YunhuMessageData):
    logger.info(f"{message_data.sender_nickname} 加入了群聊 {message_data.message_chat_id}")

async def handle_group_leave(message_data: MessageManager.YunhuMessageData):
    logger.info(f"{message_data.sender_nickname} 离开了群聊 {message_data.message_chat_id}")

async def handle_button_event(message_data: MessageManager.YunhuMessageData):
    event_data = message_data.data
    msg_id = event_data.get("msgId", "")
    recv_id = event_data.get("recvId", "")
    recv_type = event_data.get("recvType", "")
    user_id = event_data.get("userId", "")
    value = event_data.get("value", "")
    logger.info(f"机器人设置: msgId={msg_id}, recvId={recv_id}, recvType={recv_type}, userId={user_id}, value={value}")
