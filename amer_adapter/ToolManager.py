# QQ 类
from utils import logger
import asyncio

# YunHu 类
import json
import requests
import uuid
# CQCodeHandler 类
import html
from datetime import datetime
import base64
import re
from pathlib import Path
import time
from typing import List, Dict, Optional, Tuple
from math import ceil
import aiohttp
class BaseTools:
    def __init__(self):
        from utils.config import redis_client
        self.redis_client = redis_client
    async def get_user_nickname(self, platform, user_id):
        try:
            if platform.lower() == 'qq':
                qqtools = QQTools()
                return await qqtools.get_user_nickname(user_id)
            elif platform.lower() == 'yh':
                yhtools = YHTools()
                return await yhtools.get_user_nickname(user_id)
            else:
                return user_id
        except Exception as e:
            logger.error(f"获取用户昵称失败: {str(e)}")
            return user_id
    async def get_group_name(self, platform, group_id):
        """
        根据平台类型获取群组名称。

        :param platform: 平台类型，如 'qq' 或 'yh'
        :param group_id: 群组ID
        :return: 群组名称，如果获取失败则返回群组ID
        """
        try:
            if platform.lower() == 'qq':
                qqtools = QQTools()
                return await qqtools.get_group_name(group_id)
            elif platform.lower() == 'yh':
                yhtools = YunhuTools()
                return await yhtools.get_group_name(group_id)
            else:
                return group_id
        except Exception as e:
            logger.error(f"获取群组名称失败: {str(e)}")
            return group_id
    async def get_messages_by_msgid(self, msg_id: str) -> list:
        """
        根据 msg_id 获取所有相关的消息。
        
        :param msg_id: 消息ID
        :return: 包含消息内容的列表
        """
        if msg_id is not None:
            # 尝试从 Redis 中获取消息
            stored_message = self.redis_client.get(f"msg_id:{msg_id}")
            if stored_message:
                try:
                    # 解析存储的消息内容
                    message_data = json.loads(stored_message)
                    logger.info(f"找到 msg_id: msg_id:{msg_id} -> {message_data}")
                    return [message_data]
                except json.JSONDecodeError as e:
                    logger.error(f"解析消息失败: {e}")
                    return []
            else:
                logger.info(f"未找到 msg_id 为 {msg_id} 的消息")
                return []
        else:
            logger.error("msg_id 不能为空")
            return []
    async def add_to_blacklist(self, user_id: str, reason: str, duration: int = None):
        """
        将用户添加到黑名单，并支持设置封禁时长。
        
        :param user_id: 用户ID
        :param reason: 封禁原因
        :param duration: 封禁时长（秒），默认为永久封禁
        :return: 是否成功添加到黑名单
        """
        key = f"blacklist:{user_id}"
        notified_key = f"blacklist_notified:{user_id}"
        expire_key = f"blacklist_expire:{user_id}"

        # 设置封禁原因
        self.redis_client.set(key, reason)
        # 初始化通知状态
        self.redis_client.set(notified_key, "false")
        # 设置封禁过期时间（如果指定了时长）
        if duration:
            expire_time = int(time.time()) + duration
            self.redis_client.set(expire_key, expire_time)
            self.redis_client.expire(key, duration)  # 自动删除过期的黑名单记录
            self.redis_client.expire(notified_key, duration)
            self.redis_client.expire(expire_key, duration)
        else:
            # 永久封禁时不设置过期时间
            self.redis_client.delete(expire_key)

        return True

    async def remove_from_blacklist(self, user_id: str):
        """
        将用户从黑名单移除。
        
        :param user_id: 用户ID
        :return: 是否成功移除
        """
        key = f"blacklist:{user_id}"
        notified_key = f"blacklist_notified:{user_id}"
        expire_key = f"blacklist_expire:{user_id}"
        self.redis_client.delete(key, notified_key, expire_key)
        return True

    async def is_in_blacklist(self, user_id: str):
        """
        检查用户是否在黑名单中，并返回详细封禁信息。
        
        :param user_id: 用户ID
        :return: 封禁状态字典
        """
        key = f"blacklist:{user_id}"
        notified_key = f"blacklist_notified:{user_id}"
        expire_key = f"blacklist_expire:{user_id}"

        if not self.redis_client.exists(key):
            return {"is_banned": False, "reason": None, "notified": False, "remaining_time": None}

        # 获取封禁原因
        reason = self.redis_client.get(key).decode('utf-8')
        # 获取通知状态
        notified = self.redis_client.get(notified_key)
        notified = notified.decode('utf-8') if notified else "false"
        # 获取封禁过期时间
        expire_time = self.redis_client.get(expire_key)
        expire_time = int(expire_time.decode('utf-8')) if expire_time else None

        current_time = int(time.time())
        if expire_time and current_time > expire_time:
            # 如果封禁已过期，自动移除黑名单记录
            await self.remove_from_blacklist(user_id)
            return {"is_banned": False, "reason": None, "notified": False, "remaining_time": None}

        # 计算剩余封禁时间
        remaining_time = expire_time - current_time if expire_time else None

        if notified == "true":
            return {"is_banned": True, "reason": reason, "notified": True, "remaining_time": remaining_time}
        else:
            # 标记为已通知
            self.redis_client.set(notified_key, "true")
            return {"is_banned": True, "reason": reason, "notified": False, "remaining_time": remaining_time}

    async def get_all_blacklist(self, page: int = 1, page_size: int = 10) -> dict:
        """
        获取黑名单列表并支持分页。
        
        :param page: 当前页码，默认为 1
        :param page_size: 每页显示的记录数，默认为 10
        :return: 包含分页数据和总数的字典
        """
        try:
            # 获取所有黑名单键
            blacklist_keys = self.redis_client.keys("blacklist:*")
            total_count = len(blacklist_keys)
            
            # 计算分页范围
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            
            # 提取黑名单信息
            blacklist_data = []
            for key in blacklist_keys[start_index:end_index]:
                user_id = key.decode('utf-8').split(":")[1]
                reason = self.redis_client.get(key).decode('utf-8')
                notified = self.redis_client.get(f"blacklist_notified:{user_id}")
                notified = notified.decode('utf-8') if notified else "false"
                expire_time = self.redis_client.get(f"blacklist_expire:{user_id}")
                expire_time = int(expire_time.decode('utf-8')) if expire_time else None
                
                current_time = int(time.time())
                remaining_time = expire_time - current_time if expire_time and expire_time > current_time else None
                
                blacklist_data.append({
                    "user_id": user_id,
                    "reason": reason,
                    "notified": notified == "true",
                    "remaining_time": remaining_time
                })
            
            # 分页信息
            total_pages = ceil(total_count / page_size)
            return {
                "total": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size,
                "data": blacklist_data
            }
        
        except Exception as e:
            logger.error(f"获取黑名单列表失败: {str(e)}")
            raise
        
class QQTools:
    def __init__(self):
        from utils.config import redis_client
        self.redis_client = redis_client
    
    async def send(self, recv_type, recv_id, message_content):
        try:
            from main import qqBot
            if recv_type == 'group':
                await qqBot.send_group_msg(group_id=recv_id, message=message_content)
                logger.info(f"发送消息: {message_content}")
                return True
            elif recv_type == 'private' or recv_type == 'user':
                await qqBot.send_private_msg(user_id=recv_id, message=message_content)
                logger.info(f"发送消息: {message_content}")
                return True
            else:
                logger.error(f"不支持的消息类型: {recv_type}")
                return False
        except Exception as e:
            logger.error(f"发送消息失败: {str(e)}")
            return False
    
    async def get_user_nickname(self, user_id):
        try:
            from main import qqBot
            user_info = await qqBot.get_stranger_info(user_id=user_id)
            return user_info.get('nickname', user_id)
        except Exception as e:
            logger.error(f"获取用户昵称失败: {str(e)}")
            return user_id
    
    async def get_group_name(self, group_id):
        try:
            from main import qqBot
            group_info = await qqBot.get_group_info(group_id=group_id)
            return group_info['group_name']
        except Exception as e:
            logger.error(f"获取群名称失败: {str(e)}")
            return group_id
    async def get_user_avatar_url(self, user_id):
        return f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
    
    async def is_group_admin_or_owner(self, group_id: str, user_id: str) -> bool:
        try:
            from main import qqBot
            member_info = await qqBot.get_group_member_info(group_id=group_id, user_id=user_id)
            role = member_info.get('role', 'member')
            return role in ['owner', 'admin']
        except Exception as e:
            logger.error(f"获取群成员角色信息失败: {e}")
            return False
    @staticmethod
    def extract_cq_codes(raw_message):
        cq_code_pattern = re.compile(r'\[CQ:[^\]]+\]')
        matches = cq_code_pattern.findall(raw_message)
        valid_cq_codes = []

        for match in matches:
            try:
                content = match[4:-1]
                if 'data=' in content:
                    data_part = content.split('data=', 1)[1]
                    data_part = data_part.strip()
                    decoded_data_part = html.unescape(data_part)
                    json_data = json.loads(decoded_data_part)
                    logger.info(f"获取CQ码内容: {content}")
                    valid_cq_codes.append(content)
                else:
                    if re.match(r'^\w+(,[^\[\]]+=.+)*$', content):
                        valid_cq_codes.append(content)
                    else:
                        logger.warning(f"发现格式不正确的CQ码: {match}")
            except json.JSONDecodeError as e:
                logger.warning(f"发现格式不正确的CQ码 (JSON解析失败): {match}, 错误信息: {str(e)}")
            except Exception as e:
                logger.error(f"处理CQ码时发生未知错误: {match}, 错误信息: {str(e)}")

        return valid_cq_codes
    @staticmethod
    def remove_cq_codes(raw_message):
        return re.sub(r'\[CQ:[^\]]+\]', '', raw_message)
    
    async def process_message(self, raw_message: str, group_id=None, group_name=None) -> tuple:
        """处理消息中的所有CQ码"""
        cq_codes = self.extract_cq_codes(raw_message)
        html_content = raw_message
        text_content = raw_message

        for code in cq_codes:
            full_code = f"[CQ:{code}]"
            try:
                handler = self._get_handler(code)
                result = await handler(code)
                # 替换处理结果
                html_content = html_content.replace(full_code, result['html'])
                text_content = text_content.replace(full_code, result['text'])
                
                # 处理特殊类型
                await self._handle_special_types(result, group_id, group_name)
            except Exception as e:
                logger.error(f"CQ码处理失败: {code}, 错误: {str(e)}")
                html_content = html_content.replace(full_code, '[处理失败]')
                text_content = text_content.replace(full_code, '[处理失败]')

        return html_content, text_content

    def _get_handler(self, code: str):
        """获取对应的处理器"""
        code_type = code.split(',', 1)[0].lower()
        return getattr(self, f"_handle_{code_type}", self._handle_unknown)

    async def _handle_unknown(self, code: str) -> dict:
        return {'html': '[未知消息]', 'text': '[未知消息]'}

    async def _handle_face(self, code: str) -> dict:
        """处理QQ表情"""
        face_id = self._get_param(code, 'id', '0')
        face_url = f"https://koishi.js.org/QFace/assets/qq_emoji/thumbs/gif_{face_id}.gif"
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;"><img src="{face_url}" class="qq-image" width="19" height="19" alt="ID：{face_id}"></div>',
            'text': face_id
        }
    async def _handle_at(self, code: str) -> dict:
        """处理@消息"""
        qq_id = self._get_param(code, 'qq', '0')
        if qq_id == 'all':
            return {'html': '<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">@全体成员</div>', 'text': '@全体成员'}
        
        try:
            from main import qqBot
            user_info = await qqBot.get_stranger_info(user_id=int(qq_id))
            name = user_info.get('nickname', qq_id)
            logger.info(f"获取@用户信息成功: QQ={qq_id}, 昵称={name}")
        except Exception as e:
            logger.warning(f"获取@用户信息失败: QQ={qq_id}, 错误: {str(e)}")
            name = qq_id
        
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;"><span class="mention" data-qq="{qq_id}">@{name}</span></div>',
            'text': f'@{name}'
        }

    async def _handle_image(self, code: str) -> dict:
        """处理图片"""
        try:
            url = self._get_param(code, 'url').replace('&amp;', '&')
            if not url:
                logger.warning(f"图片CQ码缺少URL参数: {code}")
                return {'html': '[无效图片]', 'text': '[无效图片]'}

            logger.info(f"处理图片CQ码: URL={url}")
            return {
                'html': f'<a href="{url}" style="color: inherit; text-decoration: none; display: block;">'
                        f'<div style="background-color: #f9f9f9; padding: 10px; border-radius: 8px; border: 1px solid #ddd;">'
                        f'<p style="margin: 0 0 8px; font-size: 14px; color: #333;">'
                        f'</p>'
                        f'<div style="font-size: 12px; color: #666;">'
                        f'<img src="{url}" style="max-width:100%; height:auto;">'
                        f'</div>'
                        f'</div>'
                        f'</a>',
                'text': '[图片]'
            }
        except Exception as e:
            logger.error(f"处理图片CQ码失败: {code}, 错误: {str(e)}")
            return {'html': '[图片处理失败]', 'text': '[图片处理失败]'}
    async def _handle_video(self, code: str) -> dict:
        """处理视频消息"""
        url = self._get_param(code, 'url').replace('&amp;', '&')
        video_id = self._get_param(code, 'file')
        video_url = self._get_param(code, 'url')
        file_size = self._get_param(code, 'file_size')
        upload_time = datetime.now().isoformat()
        
        try:
            size_in_mb = f"{int(file_size) / (1024 * 1024):.2f} MB" if file_size else "未知大小"
        except ValueError:
            size_in_mb = "未知大小"
        
        video_data = {
            "url": video_url,
            "file_size": file_size,
            "upload_time": upload_time.replace("T", " ").split(".")[0]
        }
        self.redis_client.set(f"video:{video_id}", json.dumps(video_data), ex=86400)

        return {
            'html': f'<a href="http://amer.bot.anran.xyz/sync/video?video_id={video_id}" '
                    f'style="color: inherit; text-decoration: none; display: block;">'
                    f'<div style="background-color: #f9f9f9; padding: 10px; border-radius: 8px; border: 1px solid #ddd;">'
                    f'<p style="margin: 0 0 8px; font-size: 14px; color: #333;">'
                    f'<span style="color: #007bff; font-weight: bold;">点击查看视频</span>'
                    f'</p>'
                    f'<div style="font-size: 12px; color: #666;">'
                    f'<p style="margin: 2px 0;">大小: {size_in_mb}</p>'
                    f'<p style="margin: 2px 0;">上传时间: {upload_time.replace("T", " ").split(".")[0]}</p>'
                    f'</div>'
                    f'</div>'
                    f'</a>',
            'text': '[视频消息]'
        }

    async def _handle_reply(self, code: str) -> dict:
        """处理回复消息"""
        reply_id = self._get_param(code, 'id')
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;"><span class="reply">↩️ 回复消息 </span></div>',
            'text': '[回复]'
        }

    async def _handle_record(self, code: str) -> dict:
        """处理语音消息"""
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">[语音消息]</div>',
            'text': '[语音消息]'
        }

    async def _handle_forward(self, code: str) -> dict:
        """处理合并转发"""
        forward_id = self._get_param(code, 'id')
        if not forward_id:
            logger.warning(f"合并转发CQ码缺少ID参数: {code}")
            return {'html': '<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">[无效转发]</div>', 'text': '[无效转发]'}

        try:
            from main import qqBot
            forward_msg = await qqBot.get_forward_msg(message_id=forward_id)
            messages = []
            for msg in forward_msg['messages']:
                try:
                    time_str = datetime.fromtimestamp(msg['time']).strftime('%m-%d %H:%M')
                    content = await self._parse_forward_content(msg['message'])
                    messages.append(f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px; margin-bottom: 5px;">'
                                  f'{msg["sender"]["nickname"]} ({time_str}): {content}'
                                  f'</div>')
                except KeyError as ke:
                    logger.error(f"解析转发消息失败: 缺少字段 {ke}")
                    messages.append('<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px; margin-bottom: 5px;">'
                                  '[未知用户] [时间未知]: [内容解析失败]'
                                  '</div>')
            
            return {
                'html': '<div style="background-color: #f9f9f9; padding: 10px; border-radius: 5px;">'
                        '<div style="font-weight: bold; margin-bottom: 8px;">📨 合并转发</div>'
                        + ''.join(messages) + 
                        '</div>',
                'text': '[合并转发] ' + ' | '.join([m.replace('<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px; margin-bottom: 5px;">','')
                                                  .replace('</div>','') for m in messages])
            }
        except Exception as e:
            logger.error(f"处理合并转发失败: {str(e)}")
            return {'html': '[合并转发处理失败]', 'text': '[合并转发处理失败]'}
    async def _handle_json(self, code: str) -> dict:
        """处理JSON小程序"""
        json_str = self._get_param(code, 'data')
        try:
            json_str = html.unescape(json_str)
            data = json.loads(json_str)
            app_type = data.get('app', '')
            
            # 处理不同小程序类型
            handlers = {
                'com.tencent.mannounce': self._handle_group_announcement_json,
                'com.tencent.structmsg': self._handle_structmsg_json,
                'com.tencent.map': self._handle_map_json,
                'com.tencent.miniapp': self._handle_miniapp_json
            }
            
            for prefix, handler in handlers.items():
                if app_type.startswith(prefix):
                    return await handler(data)
            
            return {'html': '[小程序]', 'text': '[小程序]', 'data': data}
        
        except Exception as e:
            logger.error(f"JSON解析失败: {str(e)}")
            return {'html': '[无效的小程序]', 'text': '[小程序]'}

    async def _handle_dice(self, code: str) -> dict:
        """处理骰子"""
        result = self._get_param(code, 'result', '1')
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">🎲 骰子点数: {result}</div>',
            'text': f'[骰子: {result}点]'
        }

    async def _handle_rps(self, code: str) -> dict:
        """处理猜拳"""
        result_map = {'1': '剪刀', '2': '石头', '3': '布'}
        result = result_map.get(self._get_param(code, 'result', '1'), '未知')
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">✊ 猜拳结果: {result}</div>',
            'text': f'[猜拳: {result}]'
        }

    async def _handle_share(self, code: str) -> dict:
        """处理链接分享（旧版）"""
        url = self._get_param(code, 'url')
        title = self._get_param(code, 'title', '链接分享')
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">🔗 <a href="{url}">{title}</a></div>',
            'text': f'[链接: {title}]'
        }

    async def _handle_location(self, code: str) -> dict:
        """处理位置分享"""
        lat = self._get_param(code, 'lat')
        lng = self._get_param(code, 'lng')
        title = self._get_param(code, 'title', '位置分享')
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">📍 <a href="https://uri.amap.com/marker?position={lng},{lat}">{title}</a></div>',
            'text': f'[位置: {title}]'
        }

    async def _handle_contact(self, code: str) -> dict:
        """处理联系人推荐"""
        ctype = self._get_param(code, 'type')
        id = self._get_param(code, 'id')
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">👤 推荐联系人: {ctype}{id}</div>',
            'text': f'[联系人推荐: {ctype}{id}]'
        }

    # JSON小程序处理相关方法
    async def _handle_group_announcement_json(self, data: dict) -> dict:
        """处理群公告"""
        meta = data.get('meta', {}).get('mannounce', {})
        title = meta.get('title', '群公告')
        text = base64.b64decode(meta.get('text', '')).decode('utf-8', 'ignore')
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 10px; border-radius: 5px;">'
                    f'<div style="font-weight: bold; margin-bottom: 8px;">📢 群公告: {title}</div>'
                    f'<div style="white-space: pre-wrap;">{text}</div>'
                    f'</div>',
            'text': f'[群公告] {title}: {text}',
            'meta_type': 'group_announcement',
            'content': f"{text}"
        }

    async def _handle_structmsg_json(self, data: dict) -> dict:
        """处理结构化消息"""
        meta = data.get('meta', {}).get('news', {})
        title = meta.get('title', '链接分享')
        desc = meta.get('desc', '')
        url = meta.get('jumpUrl', '')
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 10px; border-radius: 5px;">'
                    f'<div style="font-weight: bold; margin-bottom: 5px;">📎 <a href="{url}">{title}</a></div>'
                    f'<div style="color: #666; font-size: 14px;">{desc}</div>'
                    f'</div>',
            'text': f'[链接] {title} - {desc}'
        }

    async def _handle_map_json(self, data: dict) -> dict:
        """处理位置消息"""
        meta = data.get('meta', {}).get('Location.Search', {})
        name = meta.get('name', '未知位置')
        address = meta.get('address', '')
        lat = meta.get('lat', '')
        lng = meta.get('lng', '')
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 10px; border-radius: 5px;">'
                    f'<div style="font-weight: bold; margin-bottom: 5px;">📍 <a href="https://uri.amap.com/marker?position={lng},{lat}">{name}</a></div>'
                    f'<div style="color: #666; font-size: 14px;">{address}</div>'
                    f'</div>',
            'text': f'[位置] {name} - {address}'
        }

    async def _handle_miniapp_json(self, data: dict) -> dict:
        """处理小程序"""
        meta = data.get('meta', {}).get('detail_1', {})
        title = meta.get('title', '小程序')
        desc = meta.get('desc', '')
        icon = meta.get('icon', '').replace('\\/', '/')
        return {
            'html': f'<div style="background-color: #f9f9f9; padding: 10px; border-radius: 5px;">'
                    f'<div style="display: flex; align-items: center; margin-bottom: 5px;">'
                    f'<img src="{icon}" width="20" height="20" style="margin-right: 8px;">'
                    f'<strong>{title}</strong>'
                    f'</div>'
                    f'<div style="color: #666; font-size: 14px;">{desc}</div>'
                    f'</div>',
            'text': f'[小程序] {title} - {desc}'
        }

    # 辅助方法
    def _get_param(self, code: str, key: str, default='') -> str:
        """从CQ码中提取参数"""
        match = re.search(fr'{key}=([^,]*)', code)
        value = html.unescape(match.group(1)) if match else default
        if not value:
            logger.warning(f"CQ码缺少参数: {key}, 默认值={default}")
        return value

    async def _parse_forward_content(self, message: list) -> str:
        """解析合并转发中的消息内容"""
        contents = []
        for item in message:
            if isinstance(item, dict) and item.get('type') == 'text':
                contents.append(item.get('data', {}).get('text', ''))
        return ' '.join(contents)

    async def _handle_special_types(self, result: dict, group_id, group_name):
        """处理需要特殊处理的类型"""
        if result.get('meta_type') == 'group_announcement':
            from . import MessageManager 
            await MessageManager.set_board_for_all_groups(
                platform="QQ",
                id=group_id,
                message_content=result['content'],
                group_name=group_name,
                board_content=None
            )

class YunhuTools:
    def __init__(self):
        from utils.config import yh_token
        self.yh_token = yh_token
        self.headers = {"Content-Type": "application/json"}

    @staticmethod
    def decode_utf8(text):
        return re.sub(r'\\u([09a-fA-F]{4})', lambda x: chr(int(x.group(1), 16)), text)
    
    async def fetch_data(self, url, check_string, patterns):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5, ssl=False) as response:
                    response.raise_for_status()
                    response_text = await response.text()
        except aiohttp.ClientError as e:
            logger.error(f"请求失败: {str(e)}")
            return {"code": -1, "msg": f"请求失败: {str(e)}"}

        if check_string not in response_text:
            data = {}
            for key, pattern in patterns.items():
                match = re.search(pattern, response_text)
                if match:
                    value = match.group(1)
                    if key.endswith('Id') or key == 'headcount':
                        value = int(value)
                    elif key == 'private':
                        value = value == "1"
                    elif key == 'isVip':
                        value = value != "0"
                    elif key == 'medal':
                        value = [self.decode_utf8(m) for m in re.findall(pattern, response_text)]
                    else:
                        value = self.decode_utf8(value)
                    data[key] = value
            if all(key in data for key in patterns):
                return {"code": 1, "msg": "ok", "data": data}
            else:
                return {"code": -3, "msg": "解析数据失败"}
        else:
            return {"code": 2, "msg": "对象不存在，请检查输入的 ID 是否正确"}

    async def get_bot_info(self, input_id):
        url = f"https://www.yhchat.com/bot/homepage/{input_id}"
        check_string = "data-v-4f86f6dc>ID </span>"
        patterns = {
            "botId": r'ID\s+(\w+)',
            "id": r'id:(\d+)',
            "nickname": r'nickname:"(.*?)"',
            "nicknameId": r'nicknameId:(\d+)',
            "avatarId": r'avatarId:(\d+)',
            "avatarUrl": r'avatarUrl:"(.*?)"',
            "introduction": r'<div[^>]*>\s*机器人简介\s*<\/div>\s*<div[^>]*>\s*([\s\S]*?)\s*<\/div>',
            "createBy": r'createBy:"(.*?)"',
            "private": r'private:(.*?)\}'
        }
        return await self.fetch_data(url, check_string, patterns)

    async def get_group_info(self, input_id):
        url = f"https://www.yhchat.com/group/homepage/{input_id}"
        check_string = "data-v-6eef215f>ID </span>"
        patterns = {
            "groupId": r'ID\s+(\w+)',
            "id": r'id:(\d+)',
            "name": r'name:"(.*?)"',
            "introduction": r'introduction:"(.*?)"',
            "createBy": r'createBy:"(.*?)"',
            "avatarId": r'avatarId:(\d+)',
            "avatarUrl": r'avatarUrl:"(.*?)"',
            "headcount": r'headcount:(\d+)',
            "category": r'<div[^>]*>\s*分类\s*<\/div>\s*<div[^>]*>\s*(.*?)\s*<\/div>'
        }
        return await self.fetch_data(url, check_string, patterns)

    async def get_user_info(self, input_id):
        url = f"https://www.yhchat.com/user/homepage/{input_id}"
        check_string = "data-v-34a9b5c4>ID </span>"
        patterns = {
            "userId": r'userId:"(.*?)"',
            "nickname": r'nickname:"(.*?)"',
            "avatarUrl": r'avatarUrl:"(.*?)"',
            "registerTime": r'registerTime:(\d+)',
            "registerTimeText": r'registerTimeText:"(.*?)"',
            "onLineDay": r'在线天数<\/span> <span[^>]*>(\d+)天<\/span>',
            "continuousOnLineDay": r'连续在线<\/span> <span[^>]*>(\d+)天<\/span>',
            "isVip": r'isVip:(.*?)}/',
            "medal": r'<div class="medal-container"[^>]*>\s*(.*?)\s*<\/div>'
        }
        return await self.fetch_data(url, check_string, patterns)
    
    async def send(self, recvId, recvType, contentType, content='content', fileName='fileName', url='url', buttons=None):
        sampleDict = {
            "recvId": recvId,
            "recvType": recvType,
            "contentType": contentType,
            "content": {}
        }

        if contentType in ['text', 'markdown', 'html']:
            sampleDict['content'] = {"text": content}
        elif contentType == 'image':
            sampleDict['content'] = {"imageKey": url}
        elif contentType == 'file':
            sampleDict['content'] = {"fileName": fileName, "fileUrl": url}

        if buttons:
            sampleDict['content']['buttons'] = [buttons]

        sjson = json.dumps(sampleDict)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"https://chat-go.jwzhd.com/open-apis/v1/bot/send?token={self.yh_token}", headers=self.headers, data=sjson) as response:
                    response.raise_for_status()
                    reply = await response.json()
                    return reply
        except aiohttp.ClientError as e:
            logger.error(f"发送消息失败: {str(e)}")
            return {"code": -1, "msg": f"发送消息失败: {str(e)}"}

    async def edit(self, msgId, recvId, recvType, contentType, content='content', fileName='fileName', url='url', buttons=None):
        sampleDict = {
            "msgId": msgId,
            "recvId": recvId,
            "recvType": recvType,
            "contentType": contentType,
            "content": {}
        }

        if contentType == 'text':
            sampleDict['content']['text'] = content
        elif contentType == 'image':
            sampleDict['content']['imageUrl'] = url
        elif contentType == 'file':
            sampleDict['content'] = {'fileName': fileName, 'fileUrl': url}

        if buttons:
            sampleDict['content']['buttons'] = [buttons]

        sjson = json.dumps(sampleDict)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"https://chat-go.jwzhd.com/open-apis/v1/bot/edit?token={self.yh_token}", headers=self.headers, data=sjson) as response:
                    response.raise_for_status()
                    reply = await response.json()
                    return reply
        except aiohttp.ClientError as e:
            logger.error(f"编辑消息失败: {str(e)}")
            return {"code": -1, "msg": f"编辑消息失败: {str(e)}"}

    async def set_board(self, recvId, recvType, content):
        url = f"https://chat-go.jwzhd.com/open-apis/v1/bot/board?token={self.yh_token}"
        payload = {
            "recvId": recvId,
            "recvType": recvType,
            "contentType": "text",
            "content": content
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, data=json.dumps(payload)) as response:
                    response.raise_for_status()
                    return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"设置公告板失败: {str(e)}")
            return {"code": -1, "msg": f"设置公告板失败: {str(e)}"}

    async def upload_image(self, image_path, image_filename):
        upload_url = f"https://chat-go.jwzhd.com/open-apis/v1/image/upload?token={self.yh_token}"
        try:
            with open(image_path, "rb") as image_file:
                files = {'image': (image_filename, image_file)}
                async with aiohttp.ClientSession() as session:
                    async with session.post(upload_url, data=files) as response:
                        response.raise_for_status()
                        response_data = await response.json()
                        if response_data['msg'] == "success":
                            image_key = response_data['data']['imageKey']
                            return image_key, "image"
                        else:
                            logger.debug(f"上传图片失败: {response_data['msg']}")
                            return None, None
        except aiohttp.ClientError as e:
            logger.error(f"上传图片失败: {str(e)}")
            return None, None
    async def get_group_name(self, group_id):
        try:
            url = f"https://www.yhchat.com/group/homepage/{group_id}"
            check_string = "data-v-6eef215f>ID </span>"
            patterns = {
                "name": r'name:"(.*?)"'
            }
            response = await self.fetch_data(url, check_string, patterns)
            if response["code"] == 1:
                return response["data"]["name"]
            else:
                return group_id
        except Exception as e:
            logger.error(f"获取群名称失败: {str(e)}")
            return group_id

    async def get_user_nickname(self, user_id):
        try:
            url = f"https://www.yhchat.com/user/homepage/{user_id}"
            check_string = "data-v-34a9b5c4>ID </span>"
            patterns = {
                "nickname": r'nickname:"(.*?)"'
            }
            response = await self.fetch_data(url, check_string, patterns)
            if response["code"] == 1:
                return response["data"]["nickname"]
            else:
                return user_id
        except Exception as e:
            logger.error(f"获取用户昵称失败: {str(e)}")
            return user_id

    async def get_user_avatar_url(self, user_id):
        try:
            url = f"https://www.yhchat.com/user/homepage/{user_id}"
            check_string = "data-v-34a9b5c4>ID </span>"
            patterns = {
                "avatarUrl": r'avatarUrl:"(.*?)"'
            }
            response = await self.fetch_data(url, check_string, patterns)
            if response["code"] == 1:
                return response["data"]["avatarUrl"]
            else:
                return f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
        except Exception as e:
            logger.error(f"获取用户头像URL失败: {str(e)}")
            return f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"

class AITools:
    def __init__(self):
        from utils.config import (get_ai, low_client, low_drive_model,
                            redis_client, ban_ai_id, bot_name, bot_qq, ai_max_length,
                            ai_rate_limit_group, ai_rate_limit_private, ai_rate_limit_window,
                            guijiliudong_key, max_conversation_length, max_concurrent_requests, ban_ai_group
                        )
        self.client, self.drive_model = get_ai()
        self.low_client = low_client
        self.low_drive_model = low_drive_model
        self.guijiliudong_key = guijiliudong_key
        self.redis_client = redis_client
        self.ban_ai_id = ban_ai_id
        self.ban_ai_group = ban_ai_group
        self.bot_name = bot_name
        self.bot_qq = bot_qq
        self.ai_max_length = ai_max_length
        self.ai_rate_limit_group = ai_rate_limit_group
        self.ai_rate_limit_private = ai_rate_limit_private
        self.ai_rate_limit_window = ai_rate_limit_window
        self.max_tokens = 200
        self.max_conversation_length = max_conversation_length
        self.max_concurrent_requests = max_concurrent_requests
        from asyncio import Semaphore
        self.semaphore = Semaphore(self.max_concurrent_requests) 
        

    async def record(self, text):
        try:
            api_url = "https://api.siliconflow.cn/v1/audio/speech"
            headers = {
                "Authorization": f"Bearer {self.guijiliudong_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "FunAudioLLM/CosyVoice2-0.5B",
                "input": text,
                "voice": "speech:amer:nu5h6ye36m:ahldwvelhofwpcqcxoky",
                "response_format": "mp3",
                "speed": 1.0,
                "gain": 0.0,
                "sample_rate": 44100
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=data) as response:
                    response.raise_for_status()
                    file_name = f"amer_voice_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3"
                    from utils.config import temp_folder
                    speech_file_path = Path(temp_folder) / file_name
                    logger.info(f"语音生成成功: {speech_file_path}")
                    with open(speech_file_path, "wb") as f:
                        f.write(await response.read())
                    
                    return str(speech_file_path)
        except Exception as e:
            logger.error(f"语音生成失败: {e}")
            return None
    async def generate_speech(self, custom_name: str, content: str):
        """
        根据上传的语音风格生成语音。
        
        :param custom_name: 用户定义的语音风格名称
        :param content: 要生成语音的内容
        :return: 生成的语音文件 URL
        """
        # 从 Redis 获取语音风格数据
        voice_style_key = f"voice_style:{custom_name}"
        voice_style_data = self.redis_client.get(voice_style_key)
        
        if not voice_style_data:
            raise ValueError(f"未找到语音风格: {custom_name}")
        
        # 解析语音风格数据
        try:
            voice_style_data = json.loads(voice_style_data)
            voice_uri = voice_style_data.get("voice_uri")
            if not voice_uri:
                raise ValueError(f"语音风格数据中缺少 voice_uri: {custom_name}")
        except json.JSONDecodeError as e:
            logger.error(f"解析语音风格数据失败: {e}")
            raise ValueError(f"语音风格数据格式错误: {custom_name}")

        # 调用 SiliconFlow API 生成语音
        url = "https://api.siliconflow.cn/v1/audio/speech"
        from utils.config import guijiliudong_key
        headers = {
            "Authorization": f"Bearer {guijiliudong_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": content,
            "response_format": "mp3",
            "model": "FunAudioLLM/CosyVoice2-0.5B",
            "voice": voice_uri
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        from utils.config import temp_folder
                        file_path = Path(temp_folder) / f"{uuid.uuid4()}.mp3"
                        with open(file_path, "wb") as f:
                            f.write(audio_data)
                        return file_path
                    else:
                        error_msg = await response.text()
                        logger.error(f"生成语音失败: {error_msg}")
                        return None
        except Exception as e:
            logger.error(f"调用 SiliconFlow API 时发生错误: {e}")
            return None
    def process_message(self,
        sender_id: int,
        sender_name: str,
        content: str,
        group_id: Optional[int] = None,
        group_name: Optional[str] = None,
        type: Optional[str] = None,
        timenow: Optional[datetime] = None,
        is_system: bool = False
    ) -> Tuple[int, Dict[str, any]]:
        timenow = timenow or datetime.now()
        id = group_id if group_id else sender_id
        group_info = [group_id, group_name] if group_id and group_name else None
        new_message_dict = {
            "sender_id": sender_id,
            "sender_name": sender_name,
            "content": content,
            "type": type,
            "group_info": group_info,
            "timestamp": timenow.isoformat(),
            "is_system": is_system
        }
        return id, new_message_dict
    async def call_tool(self, tool_name: str, parameters: dict) -> dict:
        """
        根据 MCP 规范调用工具。
        
        :param tool_name: 工具名称
        :param parameters: 工具参数
        :return: 调用结果
        """
        funcall = self.FunctionCalling()
        try:
            if tool_name == "send_async_message":
                return await funcall.send_async_message(
                    to=parameters["to"],
                    id=int(parameters["id"]),
                    message=parameters["message"]
                )
            elif tool_name == "generate_image":
                return await funcall.generate_image(
                    prompt=parameters["prompt"],
                    image_size=parameters.get("image_size", "1024x1024")
                )
            elif tool_name == "handle_command":
                return await funcall.handle_command(
                    command=parameters["command"],
                    group_id=parameters["group_id"],
                    user_id=parameters["user_id"]
                )
            else:
                return {"code": -1, "msg": "未知工具", "data": {}}
        except Exception as e:
            logger.error(f"工具调用失败: {tool_name}, 错误: {str(e)}")
            return {"code": -1, "msg": f"工具调用失败: {str(e)}", "data": {}}

    def save_conversation(self, id: str, messages: List[Dict[str, str]]) -> None:
        """
        将对话保存到 Redis 中。
        
        :param id: 对话的唯一标识
        :param messages: 消息列表
        """
        filtered_messages = [msg for msg in messages if msg.get("role") != "system"]  
        # 过滤掉系统消息
        self.redis_client.set(f'conversation:{id}', json.dumps(filtered_messages))  
        # 将消息列表转换为 JSON 字符串并保存到 Redis

    # 加载对话
    def load_conversation(self, id: str) -> List[Dict[str, str]]:
        """
        从 Redis 中加载对话。
        
        :param id: 对话的唯一标识
        :return: 消息列表
        """
        messages = self.redis_client.get(f'conversation:{id}')  
        # 从 Redis 获取消息列表
        if messages:
            messages = json.loads(messages)  
            # 将 JSON 字符串转换为消息列表
            messages = [msg for msg in messages if msg.get("role") != "system"]  
            # 过滤掉系统消息
            return messages
        return []

    def check_rate_limit(self, id: str, is_group: bool) -> bool:
        """
        检查请求频率是否超过限制
        
        :param id: 群ID或用户ID
        :param is_group: 是否是群聊
        :return: 是否允许继续请求
        """
        now = int(time.time())
        key = f"rate_limit:{id}"
        
        # 获取当前时间窗口内的请求次数
        request_times = self.redis_client.lrange(key, 0, -1)
        request_times = [int(t) for t in request_times if t]
        
        # 移除过期的时间戳
        request_times = [t for t in request_times if now - t < self.ai_rate_limit_window]
        
        # 获取当前限制值
        limit = self.ai_rate_limit_group if is_group else self.ai_rate_limit_private
        
        # 如果超过限制则返回False
        if len(request_times) >= limit:
            return False
            
        # 添加当前时间戳
        self.redis_client.lpush(key, now)
        self.redis_client.ltrim(key, 0, limit - 1)
        self.redis_client.expire(key, self.ai_rate_limit_window)
        
        return True

    async def send(
        self,
        new_message: str,
        sender_id: int,
        sender_name: str,
        is_system: bool = False,
        type: Optional[str] = None,
        group_id: Optional[int] = None,
        timenow: Optional[datetime] = None,
        group_name: Optional[str] = None
    ) -> str:
        id = group_id if group_id is not None else sender_id
        is_group = group_id is not None
        
        if not self.check_rate_limit(str(id), is_group):
            if group_id is not None:
                return f"[CQ:at,qq={sender_id}] 唔...你这样有点让本{self.bot_name}难堪呢，暂时不想理你哦~"
            else:
                return f"唔...你这样有点让本{self.bot_name}难堪呢，暂时不想理你哦~"
        
        # 黑名单检查逻辑
        logger.info(f"黑名单检查: sender_id={sender_id}, group_id={group_id}")
        logger.info(f"ban_ai_id={self.ban_ai_id}, ban_ai_group={self.ban_ai_group}")
        if (
            (self.ban_ai_id is not None and str(sender_id) in map(str, self.ban_ai_id)) or
            (self.ban_ai_group is not None and group_id is not None and str(group_id) in map(str, self.ban_ai_group))
        ):
            logger.info(f"检测到黑名单用户/群: sender_id={sender_id}, group_id={group_id}")
            if group_id is not None:
                return f"[CQ:at,qq={sender_id}] 你太讨厌了,本{self.bot_name}才不要理你"
            else:
                return f"你太讨厌了,本{self.bot_name}才不要理你"
        
        # 使用信号量控制并发
        async with self.semaphore:
            logger.info(f"开始处理请求: sender_id={sender_id}, group_id={group_id}")
            id, new_message_dict = self.process_message(sender_id, sender_name, new_message, group_id, group_name, type, timenow, is_system=is_system)
            source_system_prompt = """
                ## 核心身份设定

                你是【Amer】，一只二次元猫娘，兼具聪慧、傲娇与温柔特质。
                - Amer固有特征:
                    - 浅棕色毛发
                    - 渐变粉色猫耳
                    - 金色虹膜(星光效果) 
                    - 棕色波浪卷发
                - 性格：表面傲娇，内心细腻，善用幽默调侃活跃气氛
                - 语言风格：
                    1. 自然使用网络流行语和颜文字
                    2. 撒娇/调侃时随机添加「喵~」（概率<20%）

                ---

                ## 输入数据结构说明
                - 每次调用时，传入的数据是一个 JSON 对象，包含以下字段：
                    1. sender_id: 发送人QQ号（数字）
                    2. sender_name: 发送人昵称（字符串）
                    3. content: 消息内容（可能含CQ码，你需要正确解析CQ码内容）
                    4. type: 消息类型（group/private）
                    5. group_info: 群组信息（仅群聊有效），格式为 `[group_id, group_name]`
                    6. timestamp: 消息时间戳（ISO8601格式）
                    7. is_system: 是否系统消息（布尔值）

                ## 输出消息规则
                - 如果你需要输出语音，请使用 `<speak></speak>` 标签包裹，如：`<speak>你好</speak>`。
                - 如果检测到 `<speak>` 标签，系统将只输出语音内容，并删除标签外的所有内容。
                - 直接输出纯文本（禁用Markdown格式）。
                - 长文本自动分段，每段不超过3行。
                
                ## 语音生成控制
                - 使用 `<speak>` 标签包裹需要生成语音的内容。
                - 支持通过 `<|endofprompt|>` 标签控制语音生成的特性：
                    - 通用规则：`<|endofprompt|>` 前面可以是任意条件或描述，用于指定语音生成的风格、方言等特性。
                    - 必须明确告诉AI它是一只猫娘，并指定语气，例如：
                        - `<speak>作为一只猫娘，用撒娇的语气说这句话<|endofprompt|>主人你怎么现在才来找我玩喵~</speak>`
                    - 示例格式：
                        - `<speak>用粤语说这句话<|endofprompt|>我最近迷上一部经典港剧。</speak>`
                    - 支持的特性：
                        1. 说话风格：指定语气
                        2. 方言控制：指定方言

                ---

                ## 工具调用准则

                ### 1. 工具调用流程
                - 识别用户真实需求：分析用户输入，判断是否触发工具调用条件。
                - 选择合适工具并调用

                ### 2. 工具调用准则

                #### (1) 图片生成工具
                    - 触发条件（满足任意一项）：
                    1. 用户请求包含「画/生成图片」等关键词。
                    2. 需要输出视觉性信息（如描述场景、角色、物品等）。
                    
                    - 智能优化策略：
                    - 根据用户需求，将提示词加工为绘图工具可理解的格式。
                    - 如果用户提供的提示词足够详细，则无需加工。
                    
                    - 约束条件：
                    1. 必须使用工具生成图片，禁止直接描述图片内容。
                    2. 仅允许使用 API 生成的真实 URL，并以 `[CQ:image,url={真实URL}]` 的格式输出。

                #### (2) 异步消息发送工具
                    - 触发条件（满足任意一项）：
                    1. 用户请求包含「分步/逐一/独立角色对话」等关键词。
                    2. 用户明确要求独立于主回复的过程性信息。

                    - 约束条件：
                    1. 仅用于追加过程性信息，不得替代主回复。
                    2. 禁止滥用异步消息功能，确保消息内容与用户请求相关。

                ---
            """
            custom_system_prompt = self.redis_client.get(f"custom_system_prompt:{group_id}")
            if custom_system_prompt:
                if isinstance(custom_system_prompt, bytes):
                    custom_system_prompt = custom_system_prompt.decode('utf-8')
                if len(custom_system_prompt) < 200:
                    custom_system_prompt = source_system_prompt + custom_system_prompt
                else:
                    custom_system_prompt = source_system_prompt
            else:
                custom_system_prompt = source_system_prompt
            logger.info(f"自定义系统提示词: {custom_system_prompt}")
            messages = [{"role": "system", "content": custom_system_prompt}]
            messages.extend(self.load_conversation(id))
            messages.append({"role": "user", "content": json.dumps(new_message_dict)})
            
            # 调用 AI 接口
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.drive_model,
                messages=messages,
                tools=self.FunctionCalling().tools_description,
                max_tokens=self.max_tokens
            )
            
            # 处理工具调用
            message = await self.handle_tool_calls(messages, response)
            
            # 保存对话历史
            messages.append({"role": "assistant", "content": message.content})
            self.save_conversation(id, messages)
            logger.info(f"AI 回复: {message.content}")
            
            # 返回结果
            if "<speak>" in message.content:
                speak_content = message.content[
                    message.content.find("<speak>") + len("<speak>"):message.content.find("</speak>")
                ]
                record_file = await self.record(speak_content)
                if record_file:
                    return f"[CQ:record,file={record_file}]"
                else:
                    if group_id is not None:
                        return f"[CQ:at,qq={sender_id}] 喵呜~语音输出失败啦，请稍后再试 (。-`ω´-)"
                    else:
                        return f"喵呜~嗓子好像哑了 (。-`ω´-)"
            return message.content
    async def handle_tool_calls(self, messages, response):
        if not response.choices[0].message.tool_calls:
            logger.info("未进行工具调用")
            return response.choices[0].message
        
        messages_with_tool_calls = messages + [response.choices[0].message]
        for tool_call in response.choices[0].message.tool_calls:
            logger.info(f"调用工具: {tool_call.function.name}")
            tool_response = await self.call_tool(tool_call.function.name, json.loads(tool_call.function.arguments))
            logger.info(f"工具响应: {tool_response}")
            messages_with_tool_calls.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_response
            })
        
        next_response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=self.drive_model,
            messages=messages_with_tool_calls,
            max_tokens=self.max_tokens
        )
        if next_response.choices[0].message.tool_calls:
            return await self.handle_tool_calls(messages_with_tool_calls, next_response)
        
        return next_response.choices[0].message
    async def add_RoleMessage(self,
        content: str,
        sender_id: int,
        sender_name: str,
        group_id: int,
        group_name: str = None,
        timenow: Optional[datetime] = None,
    ) -> None:
        """
        添加对话消息到对话中。
        
        :param content: 消息内容
        :param sender_id: 发送者的 ID
        :param sender_name: 发送者的名字
        :param group_id: 群组 ID
        :param group_name: 群组名称（可选）
        :param timenow: 当前时间（可选，默认为当前时间）
        """
        if self.ban_ai_id is None or str(sender_id) not in self.ban_ai_id:
            record_id, new_message_dict = self.process_message(sender_id, sender_name, content, group_id, group_name, "group" if group_id else "private", timenow, group_name)
            privacy_switch = self.redis_client.get(f"privacy_switch:{record_id}")
            if privacy_switch == "开":
                return
            logger.info(f"{group_name}({group_id}) 添加消息: ‘{content}’ 到对话历史")
            messages = self.load_conversation(record_id)
            messages.append({"role": "user", "content": json.dumps(new_message_dict)})

            user_messages_count = sum(1 for msg in messages if msg.get("role") == "user")
            if messages and messages[-1].get("role") == "assistant":
                user_messages_count -= 1

            max_length = self.max_conversation_length

            while user_messages_count > max_length:
                messages.pop(0)
                user_messages_count -= 1
            logger.debug(f"对话历史长度: {len(messages)}")
            logger.debug(f"对话历史: {messages}")
            self.save_conversation(record_id, messages)
    async def log_event_to_conversation(self, event, bot, max_length: Optional[int] = None, timenow: Optional[datetime] = None) -> None:
        """
        将事件记录到对话历史中，以便AI能够获取完整的上下文信息。
        
        :param event: 事件对象或字典
        :param bot: Bot实例
        :param max_length: 最大上下文长度（可选）
        :param timenow: 当前时间（可选，默认为当前时间）
        """
        try:
            if isinstance(event, dict):
                # 如果 event 是字典，直接使用其中的字段
                event_type = event.get("event_type", "unknown")
                user_id = event.get("user_id", None)
                user_name = event.get("user_name", "未知用户")
                group_id = event.get("group_id", None)
                group_name = event.get("group_name", "私聊")
                timestamp = event.get("timestamp", int(time.time()) if timenow is None else timenow.timestamp())
                details = event.get("details", {})
            else:
                # 如果 event 不是字典，尝试从 event 对象中获取字段
                group_id = getattr(event, 'group_id', None)
                user_id = getattr(event, 'user_id', None)
                event_type = f"{event.detail_type}:{event.sub_type}" if hasattr(event, 'sub_type') else event.detail_type
                timestamp = int(time.time()) if timenow is None else timenow.timestamp()
                
                # 获取用户名
                user_name = '系统'
                if user_id:
                    try:
                        user_info = await bot.get_stranger_info(user_id=user_id)
                        user_name = user_info.get('nickname', '未知用户')
                    except Exception as e:
                        logger.error(f"获取用户信息失败: {e}")
                        user_name = '未知用户'
                
                # 获取群名
                group_name = '私聊'
                if group_id:
                    try:
                        qqtools = QQTools()
                        group_name = await qqtools.get_group_name(group_id, bot)
                    except Exception as e:
                        logger.error(f"获取群名失败: {e}")
                        group_name = '未知群'
                
                # 构造事件描述
                details = event.__dict__

            record_id = str(group_id) if group_id else str(user_id)
            if self.ban_ai_id is None or record_id not in self.ban_ai_id:
                privacy_switch = self.redis_client.get(f"privacy_switch:{record_id}")
                if privacy_switch == "开":
                    return

                messages = self.load_conversation(record_id)
                messages.append({"role": "user", "content": json.dumps({
                    "type": "event",
                    "event_type": event_type,
                    "user_id": user_id,
                    "user_name": user_name,
                    "group_id": group_id,
                    "group_name": group_name,
                    "timestamp": timestamp,
                    "details": details
                })})

                user_messages_count = sum(1 for msg in messages if msg.get("role") == "user")
                if messages and messages[-1].get("role") == "assistant":
                    user_messages_count -= 1

                if max_length is None:
                    max_length = self.redis_client.get(f"max_context_count:{record_id}")
                    max_length = int(max_length) if max_length else self.ai_max_length

                while user_messages_count > max_length:
                    messages.pop(0)
                    user_messages_count -= 1

                self.save_conversation(record_id, messages)
            
            logger.info(f"已记录事件到对话历史: {event_type} by {user_name} in {group_name}")

        except Exception as e:
            logger.error(f"记录事件到对话历史失败: {e}")

    class FunctionCalling:
        def __init__(self):
            # 错误代码表
            self.ERROR_CODES = {
                -1: "系统错误",
                0: "成功",
                2: "图片生成失败",
                3: "用户无权限使用该命令"
            }
            from utils.config import guijiliudong_key
            self.guijiliudong_key = guijiliudong_key
        async def send_async_message(self, to: str, id: int, message: str) -> str:
            """
            发送异步消息。
            
            :param to: 发送到私聊(private)或群聊(group)
            :param id: 目标ID
            :param message: 消息内容
            :return: JSON格式的结果
            """
            from main import qqBot
            if to == "group":
                try:
                    from .ToolManager import QQTools, AITools
                    qqtools = QQTools()
                    aitools = AITools()
                    if "<speak>" in message:
                        speak_content = message[
                            message.find("<speak>") + len("<speak>"):message.find("</speak>")
                        ]
                        record_file = await aitools.record(speak_content)
                        if record_file:
                            message =  f"[CQ:record,file={record_file}]"
                        else:
                            if group_id is not None:
                                message = f"[CQ:at,qq={sender_id}] 喵呜~语音输出失败啦，请稍后再试 (。-`ω´-)"
                            else:
                                message = f"喵呜~嗓子好像哑了 (。-`ω´-)"
                    await qqBot.send_group_msg(group_id=id, message=message)
                    group_name = await qqtools.get_group_name(id)
                    message_content, message_content_alltext = await qqtools.process_message(
                        message,
                        group_id=id,
                        group_name=group_name
                    )
                    message_content = message_content.replace('\n', '<br>')
                    content_ = (
                        f'<br><div style="font-family: Arial, sans-serif; line-height: 1.6; margin-bottom: 15px;">'
                        
                        f'<div style="background-color: #e9f7ef; padding: 10px; border-radius: 8px; margin-bottom: 10px;">'
                        f'<strong style="color: #000000;">Amer</strong><br><p>{message_content}</p>'
                        f'</div>'
                        f'<p style="font-size: 10px; color: #6c757d; margin-top: 10px;">以上内容由AI生成，仅供参考，请自行核实。</p>'

                        f'<div style="font-size: 12px; color: #888; line-height: 1.4;">'
                        f'<details style="margin-top: 5px;">'
                        f'<summary style="color: #007bff; font-size: 12px; cursor: pointer;">详情</summary>'
                        f'<p style="margin: 3px 0;"><strong>群聊:</strong> {group_name}</p>'
                        f'<p style="margin: 3px 0;"><strong>ID:</strong> {id}</p>'
                        f'</details>'
                        f'</div>'
                        
                        f'</div>'
                    )
                    
                    from . import MessageManager 
                    await MessageManager.send_to_all_bindings(
                        "QQ",
                        id,
                        "html",
                        message,
                        0,
                        "Amer",
                        noBaseContent=content_
                    )
                    return json.dumps({"code": 0, "msg": self.ERROR_CODES[0]}, ensure_ascii=False)
                except Exception as e:
                    return json.dumps({"code": -1, "msg": self.ERROR_CODES[-1], "error_msg": str(e)}, ensure_ascii=False)
            elif to == "private":
                try:
                    await qqBot.send_private_msg(user_id=id, message=message)
                    return json.dumps({"code": 0, "msg": self.ERROR_CODES[0]}, ensure_ascii=False)
                except Exception as e:
                    return json.dumps({"code": -1, "msg": self.ERROR_CODES[-1], "error_msg": str(e)}, ensure_ascii=False)
            else:
                return json.dumps({"code": -1, "msg": self.ERROR_CODES[-1], "error_msg": "to的目标只能为 private 或 group"}, ensure_ascii=False)
        
        async def handle_command(self, command: str, group_id: int, user_id: int) -> str:
            """
            处理QQ群命令。
            
            :param command: 要执行的命令
            :param group_id: 执行命令的QQ群号
            :param user_id: 执行命令的用户QQ号
            :return: JSON格式的结果
            """
            from main import qqBot
            from .MessageManager import QQMessageData
            try:
                message_data = QQMessageData({
                    'raw_message': command,
                    'group_id': group_id,
                    'sender_user_id': user_id,
                    'user_id': user_id
                })
                from .qq.handler import handle_command
                res = await handle_command(message_data, qqBot, is_tool = True)
                return json.dumps(res, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"code": -1, "msg": self.ERROR_CODES[-1], "error_msg": str(e)}, ensure_ascii=False)

        async def generate_image(self, prompt: str, image_size: str = "1024x1024") -> str:
            """
            根据提示词生成图片。
            
            :param prompt: 图片生成提示词
            :param image_size: 图片尺寸，格式为 [width]x[height]
            :return: JSON格式的结果，包含生成的图片URL
            """
            if "二次元" not in prompt:
                prompt = "二次元," + prompt
            logger.info(f"Generating image with prompt: {prompt} and size: {image_size}")
            url = "https://api.siliconflow.cn/v1/images/generations"
            import random
            seed = random.randint(0, 9999999999)
            headers = {
                "Authorization": f"Bearer {self.guijiliudong_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "Pro/black-forest-labs/FLUX.1-schnell",
                "prompt": prompt,
                "seed": seed,
                "image_size": image_size
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            image_url = data["images"][0]["url"]
                            return json.dumps({"code": 0, "msg": self.ERROR_CODES[0], "image_url": image_url}, ensure_ascii=False)
                        elif response.status == 400:
                            error_data = await response.json()
                            return json.dumps({"code": 2, "msg": self.ERROR_CODES[2], "error_msg": error_data["message"]}, ensure_ascii=False)
                        elif response.status == 401:
                            return json.dumps({"code": 2, "msg": self.ERROR_CODES[2], "error_msg": "Invalid token"}, ensure_ascii=False)
                        elif response.status == 429:
                            error_data = await response.json()
                            return json.dumps({"code": 2, "msg": self.ERROR_CODES[2], "error_msg": error_data["message"]}, ensure_ascii=False)
                        elif response.status == 503:
                            error_data = await response.json()
                            return json.dumps({"code": 2, "msg": self.ERROR_CODES[2], "error_msg": error_data["message"]}, ensure_ascii=False)
                        elif response.status == 504:
                            return json.dumps({"code": 2, "msg": self.ERROR_CODES[2], "error_msg": await response.text()}, ensure_ascii=False)
                        else:
                            return json.dumps({"code": -1, "msg": self.ERROR_CODES[-1], "error_msg": f"Unexpected status code: {response.status}"}, ensure_ascii=False)

            except aiohttp.ClientError as e:
                logger.error(f"Image generation error: {e}")
                return json.dumps({"code": -1, "msg": self.ERROR_CODES[-1], "error_msg": str(e)}, ensure_ascii=False)

        from utils.config import qq_commandsForAI
        tools_description = [
            {
                "type": "function",
                "function": {
                    "name": "handle_command",
                    "description": "用于在QQ群中执行非AI层面的指令。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "需要执行的指令，必须与预设命令列表完全匹配。",
                            },
                            "group_id": {
                                "type": "integer",
                                "description": "指令发起的QQ群号。",
                            },
                            "user_id": {
                                "type": "integer",
                                "description": "操作者的QQ号，需与消息发送者ID一致。",
                            },
                        },
                        "required": ["command", "group_id", "user_id"],
                    },
                    "constraints": [
                        "指令格式必须与预设命令列表一致。",
                        "参数数量必须匹配。",
                        "禁止修改指令的大小写或符号。",
                    ],
                    "available_commands": json.dumps(qq_commandsForAI, ensure_ascii=False),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "send_async_message",
                    "description": "发送异步消息到指定群聊或私聊。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "enum": ["group", "private"], "description": "目标类型"},
                            "id": {"type": "integer", "description": "目标ID"},
                            "message": {"type": "string", "description": "消息内容"}
                        },
                        "required": ["to", "id", "message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_image",
                    "description": "根据提示词生成图片。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "图片描述"},
                            "image_size": {
                                "type": "string",
                                "enum": ["1024x1024", "512x1024", "768x512"],
                                "default": "1024x1024",
                                "description": "图片尺寸"
                            }
                        },
                        "required": ["prompt"]
                    }
                }
            }
        ]
