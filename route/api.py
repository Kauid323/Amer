import random
import string
from quart import request, jsonify, render_template_string, send_from_directory
from utils import logger
from amer_adapter import MessageManager, BindingManager , yhtools, qqtools
import datetime
from utils.config import redis_client
from captcha.image import ImageCaptcha
import base64
from io import BytesIO
from pathlib import Path
import json
import aiohttp
from .base_page import base_error_page, base_success_page
# 速率限制头
RATE_LIMIT_KEY_PREFIX = "rate_limit:"
MAX_REQUESTS_PER_MINUTE = 3
def generate_captcha():
    # 随机生成4位字符的验证码（仅包含小写字母和数字）
    captcha_text = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    # 使用ImageCaptcha生成验证码图片
    image = ImageCaptcha()
    data = image.generate(captcha_text)
    # 将验证码图片转换为Base64格式，方便嵌入HTML
    buffered = BytesIO()
    image.write(captcha_text, buffered)
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return captcha_text, img_base64

def register_routes(app, qqBot):
    @app.route('/favicon.ico')
    async def favicon():
        """
        返回网站图标文件
        """
        return await send_from_directory('route/icon', 'amer.jpeg', mimetype='image/jpeg')
    @app.route("/report", methods=['GET', 'POST'])
    async def report():
        try:
            client_ip = request.remote_addr
            rate_limit_key = f"{RATE_LIMIT_KEY_PREFIX}{client_ip}"
            current_requests = redis_client.get(rate_limit_key)

            if current_requests and int(current_requests) >= MAX_REQUESTS_PER_MINUTE:
                return await base_error_page("请求过于频繁", "您短时间内发送的请求过多，请稍后再试。"), 429

            if request.method == 'GET':
                if request.args.get("userid") is not None:
                    return await base_error_page("无法举报", "过期的消息"), 400
                msg_id = request.args.get("msgId")
                if not msg_id:
                    return await base_error_page("举报失败", "缺少必要参数，请检查您的请求。"), 400

                captcha_text, img_base64 = generate_captcha()
                captcha_key = f"captcha:{client_ip}"
                redis_client.set(captcha_key, captcha_text, ex=300)

                return await render_template_string(
                    """
                    <!DOCTYPE html>
                    <html lang="zh">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>举报验证</title>
                        <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
                        <style>
                            body {
                                font-family: 'Roboto', sans-serif;
                                background: linear-gradient(135deg, #f5f7fa, #c3cfe2);
                                color: #333;
                                margin: 0;
                                padding: 0;
                                display: flex;
                                justify-content: center;
                                align-items: center;
                                min-height: 100vh;
                            }
                            .container {
                                max-width: 500px;
                                width: 100%;
                                background: #fff;
                                border-radius: 12px;
                                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
                                padding: 30px;
                                text-align: center;
                                animation: fadeIn 0.5s ease;
                            }
                            h1 {
                                font-size: 24px;
                                color: #212529;
                                margin-bottom: 20px;
                                position: relative;
                                padding-bottom: 10px;
                            }
                            h1:after {
                                content: '';
                                position: absolute;
                                bottom: 0;
                                left: 50%;
                                transform: translateX(-50%);
                                width: 50px;
                                height: 3px;
                                background: #212529;
                            }
                            form {
                                display: flex;
                                flex-direction: column;
                                gap: 20px;
                            }
                            label {
                                font-weight: 600;
                                color: #212529;
                                text-align: left;
                                margin-bottom: -10px;
                            }
                            input[type="text"] {
                                padding: 12px;
                                border: 1px solid #ced4da;
                                border-radius: 8px;
                                background: #fff;
                                color: #495057;
                                transition: border-color 0.3s ease;
                            }
                            input[type="text"]:focus {
                                border-color: #212529;
                                outline: none;
                                box-shadow: 0 0 0 3px rgba(33, 37, 41, 0.1);
                            }
                            button {
                                padding: 12px;
                                border: none;
                                border-radius: 8px;
                                background: #212529;
                                color: #fff;
                                cursor: pointer;
                                font-weight: bold;
                                transition: all 0.3s ease;
                            }
                            button:hover {
                                background: #343a40;
                                transform: translateY(-2px);
                                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                            }
                            img {
                                max-width: 100%;
                                height: auto;
                                border-radius: 8px;
                                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
                                transition: transform 0.3s ease;
                            }
                            img:hover {
                                transform: scale(1.02);
                            }
                            @keyframes fadeIn {
                                from { opacity: 0; transform: translateY(20px); }
                                to { opacity: 1; transform: translateY(0); }
                            }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>举报验证</h1>
                            <form method="POST">
                                <input type="hidden" id="msgId" name="msgId" value="{{ msg_id }}">
                                <label for="captcha">请输入验证码:</label>
                                <img src="data:image/png;base64,{{ img_base64 }}" alt="验证码" onclick="this.src='data:image/png;base64,{{ img_base64 }}?t='+Date.now()">
                                <input type="text" id="captcha" name="captcha" placeholder="验证码" required>
                                <button type="submit">提交举报</button>
                            </form>
                        </div>
                    </body>
                    </html>
                    """,
                    msg_id=msg_id,
                    img_base64=img_base64
                )

            elif request.method == 'POST':
                # 获取表单数据
                msg_id = (await request.form).get("msgId")
                user_captcha = (await request.form).get("captcha")

                # 验证验证码
                captcha_key = f"captcha:{client_ip}"
                correct_captcha = redis_client.get(captcha_key)
                if not correct_captcha or user_captcha.upper() != correct_captcha.decode("utf-8").upper():
                    return await base_error_page("验证码错误", "请输入正确的验证码。"), 400

                # 删除已使用的验证码
                redis_client.delete(captcha_key)

                if not msg_id:
                    return await base_error_page("举报失败", "缺少必要参数，请检查您的请求。"), 400

                # 解析消息信息
                try:
                    from amer_adapter.ToolManager import BaseTools
                    basetools = BaseTools()
                    messages = await basetools.get_messages_by_msgid(msg_id)
                    if not messages:
                        return await base_error_page("举报失败", "未找到指定的消息ID，请检查您的请求。"), 404
                    message_info = messages[0]
                except Exception as e:
                    logger.error(f"解析消息信息失败: {e}")
                    return await base_error_page("解析失败", "无法解析消息信息，请稍后再试。"), 400

                # 更新 Redis 请求计数
                if not redis_client.exists(rate_limit_key):
                    redis_client.set(rate_limit_key, 1, ex=60)
                else:
                    redis_client.incr(rate_limit_key)
                
                # 获取被举报的用户ID
                reported_user_id = message_info.get('sender_id')
                if not reported_user_id:
                    return await base_error_page("举报失败", "无法获取被举报用户的ID，请稍后再试。"), 400

                # 记录举报次数
                report_count_key = f"report_count:{reported_user_id}"
                report_count = redis_client.get(report_count_key)
                if report_count:
                    report_count = int(report_count) + 1
                else:
                    report_count = 1
                redis_client.set(report_count_key, report_count, ex=86400)

                # 检查举报次数
                if report_count >= 3:
                    # 计算封禁时长
                    ban_duration = 1800 + (report_count - 3) * 600  # 第三次开始，每次增加10分钟

                    # 封禁用户
                    ban_reason = "被多次举报"
                    ban_status = await basetools.add_to_blacklist(reported_user_id, ban_reason, ban_duration)
                    if ban_status:
                        # 生成解封链接
                        unban_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                        unban_link = f"https://amer.bot.anran.xyz/unban?msgId={msg_id}&token={unban_token}"
                        unban_token_key = f"unban_token:{unban_token}"
                        redis_client.set(unban_token_key, reported_user_id, ex=86400)

                        # 获取用户名
                        platform = message_info.get('platform_from')
                        if platform == "QQ" or platform == "qq":
                            user_name = await qqtools.get_user_nickname(reported_user_id)
                        elif platform == "YH" or platform == "yh":
                            user_name = await yhtools.get_user_nickname(reported_user_id)
                        else:
                            user_name = reported_user_id

                        notify_message_text = (
                            f"【ฅ喵呜·封禁通知ฅ】\n"
                            f"✦{user_name} (ID: {reported_user_id}) 的小鱼干被没收啦~\n"
                            f"从现在起不会同步这个用户的消息了喵！\n"
                            f"✦封禁原因：{ban_reason}\n"
                            f"✦持续时间：{'直到吃完'+str(ban_duration//10)+'个猫罐头的时间(大概'+str(ban_duration)+'秒)喵~' if ban_duration >0 else '永久的喵~ (小爪爪盖上红印)'}\n"
                            f"✦自助解封链接：{unban_link}"
                        )

                        notify_message_html = (
                            # 消息容器：封禁通知内容
                            f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">{user_name} (ID: {reported_user_id}) 的小鱼干被没收啦~'
                            f'<p style="font-size: 12px; color: #8b0000; margin: 5px 0;">'
                            f'从现在起不会同步这个用户的消息了喵！'
                            f'</p>'
                            f'<p style="font-size: 12px; color: #333; margin: 5px 0;">'
                            f'✦封禁原因：{ban_reason}'
                            f'</p>'
                            f'<p style="font-size: 12px; color: #333; margin: 5px 0;">'
                            f'✦持续时间：{"直到吃完"+str(ban_duration//10)+"个猫罐头的时间(大概"+str(ban_duration)+"秒)喵~" if ban_duration > 0 else "永久的喵~ (小爪爪盖上红印)"}'
                            f'</p>'
                            f'<p style="font-size: 12px; color: #333; margin: 5px 0;">'
                            f'✦<a href="{unban_link}" target="_blank">自助解封</a>'
                            f'</p>'
                            f'</div>'
                        )

                        group_id = message_info.get('id_from')
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

                report_message = (
                    "【举报通知】\n"
                    f"平台: {message_info.get('platform_from')}\n"
                    f"群号: {message_info.get('id_from')}\n"
                    f"时间: {message_info.get('timestamp')}\n"
                    f"消息ID: {message_info.get('msg_id')}\n\n"
                    f"发送者ID: {message_info.get('sender_id')}\n"
                    f"发送者昵称: {message_info.get('sender_nickname')}\n\n"
                    f"消息内容: {message_info.get('message_content')}\n"
                )

                # 发送给开发者
                await qqBot.send_private_msg(user_id=2694611137, message=report_message)

                # 记录日志
                logger.info(f"收到举报: {report_message}")

                # 返回成功页面
                return await base_success_page("举报成功", "感谢您的反馈！我们会尽快处理。"), 200

        except Exception as e:
            logger.error(f"处理举报时发生错误: {e}")
            return await base_error_page("服务器错误", "抱歉，处理您的请求时发生了错误，请稍后再试。"), 500

    @app.route("/unban", methods=['GET'])
    async def unban():
        try:
            msg_id = request.args.get("msgId")
            token = request.args.get("token")
            if not msg_id or not token:
                return await base_error_page("参数错误", "缺少必要参数，请检查您的请求。"), 400

            from amer_adapter.ToolManager import BaseTools
            basetools = BaseTools()
            messages = await basetools.get_messages_by_msgid(msg_id)
            if not messages:
                return await base_error_page("解封失败", "未找到指定的消息ID，请检查您的请求。"), 404
            message_info = messages[0]

            # 获取被举报的用户ID
            user_id = message_info.get('sender_id')
            if not user_id:
                return await base_error_page("解封失败", "无法获取用户的ID，请稍后再试。"), 400

            # 验证解封令牌
            unban_token_key = f"unban_token:{token}"
            stored_user_id = redis_client.get(unban_token_key)
            if not stored_user_id or stored_user_id.decode("utf-8") != user_id:
                return await base_error_page("解封失败", "无效的解封令牌，请检查您的链接。"), 400

            # 检查当天解封次数
            unban_count_key = f"unban_count:{user_id}"
            unban_count = redis_client.get(unban_count_key)
            if unban_count and int(unban_count) >= 3:
                return await base_error_page("解封次数限制", "您今天已经解封了3次，请明天再试。"), 400

            # 增加解封次数
            if unban_count:
                unban_count = int(unban_count) + 1
            else:
                unban_count = 1
            redis_client.set(unban_count_key, unban_count, ex=86400)

            # 移除解封令牌
            redis_client.delete(unban_token_key)

            # 解封用户
            unban_status = await basetools.remove_from_blacklist(user_id)
            if unban_status:
                return await render_template_string(
                    """
                    <!DOCTYPE html>
                    <html lang="zh">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>解封成功</title>
                        <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
                        <style>
                            body {
                                font-family: 'Roboto', sans-serif;
                                background: linear-gradient(135deg, #f5f7fa, #c3cfe2);
                                color: #333;
                                margin: 0;
                                padding: 0;
                                display: flex;
                                justify-content: center;
                                align-items: center;
                                min-height: 100vh;
                            }
                            .container {
                                max-width: 500px;
                                width: 100%;
                                background: #fff;
                                border-radius: 12px;
                                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
                                padding: 30px;
                                text-align: center;
                                animation: fadeIn 0.5s ease;
                            }
                            h1 {
                                font-size: 24px;
                                color: #2ecc71;
                                margin-bottom: 20px;
                                position: relative;
                                padding-bottom: 10px;
                            }
                            h1:after {
                                content: '';
                                position: absolute;
                                bottom: 0;
                                left: 50%;
                                transform: translateX(-50%);
                                width: 50px;
                                height: 3px;
                                background: #2ecc71;
                            }
                            p {
                                font-size: 16px;
                                color: #555;
                                margin-bottom: 25px;
                                line-height: 1.6;
                            }
                            a {
                                display: inline-block;
                                padding: 12px 25px;
                                background: #2ecc71;
                                color: #fff;
                                text-decoration: none;
                                border-radius: 8px;
                                font-weight: bold;
                                transition: all 0.3s ease;
                                border: none;
                                cursor: pointer;
                            }
                            a:hover {
                                background: #27ae60;
                                transform: translateY(-2px);
                                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                            }
                            @keyframes fadeIn {
                                from { opacity: 0; transform: translateY(20px); }
                                to { opacity: 1; transform: translateY(0); }
                            }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>解封成功</h1>
                            <p>您已成功解封，请注意遵守社区规则。</p>
                            <a href="javascript:history.back();">返回</a>
                        </div>
                    </body>
                    </html>
                    """
                ), 200
            else:
                return await base_error_page("解封失败", "解封过程中发生错误，请稍后再试。"), 500

        except Exception as e:
            logger.error(f"处理解封时发生错误: {e}")
            return await base_error_page("服务器错误", "抱歉，处理您的请求时发生了错误，请稍后再试。"), 500
    
    @app.route("/api/v1/blacklist/status", methods=['GET', 'POST'])
    async def get_blacklist_status():
        try:
            # 获取查询参数
            user_id = request.args.get("user_id")

            # 参数校验
            if not user_id:
                return jsonify({"status": 400, "msg": "缺少必要参数"}), 400

            from amer_adapter.ToolManager import BaseTools
            basetools = BaseTools()
            result = await basetools.is_in_blacklist(user_id)

            # 返回结果
            return jsonify({"status": 0, "msg": "查询成功", "data": result}), 200

        except Exception as e:
            logger.error(f"查询黑名单状态失败: {e}")
            return jsonify({"status": 500, "msg": "服务器内部错误"}), 500

    @app.route("/api/v1/blacklist/list", methods=['GET', 'POST'])
    async def get_blacklist_list():
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 15))
            
            from amer_adapter.ToolManager import BaseTools
            base_tools = BaseTools()
            result = await base_tools.get_all_blacklist(page, page_size)

            return jsonify({"status": 0, "msg": "查询成功", "data": result}), 200
        
        except Exception as e:
            logger.error(f"查询黑名单列表失败: {e}")
            return jsonify({"status": 500, "msg": "服务器内部错误"}), 500
    @app.route("/sync/video", methods=['GET'])
    async def video_player():
        try:
            # 获取查询参数
            video_id = request.args.get("video_id")
            if not video_id:
                return await base_error_page("参数错误", "缺少必要参数，请检查您的请求。"), 400

            # 从 Redis 中获取视频信息
            video_key = f"video:{video_id}"
            video_info = redis_client.get(video_key)
            if not video_info:
                return await base_error_page("视频未找到", "未找到指定的视频信息，请检查您的请求。"), 404

            # 解析视频信息
            video_data = json.loads(video_info)
            video_url = video_data.get("url")
            from datetime import datetime
            file_size = video_data.get("file_size")

            # 返回视频播放页面
            return await render_template_string(
                """
                <!DOCTYPE html>
                <html lang="zh">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>视频播放</title>
                    <style>
                        body { 
                            font-family: Arial, sans-serif; 
                            background: #f5f5f5;
                            color: #333;
                            margin: 0;
                            padding: 0;
                        }
                        .container { 
                            max-width: 800px; 
                            margin: 50px auto; 
                            padding: 20px; 
                            background: #fff;
                            border-radius: 8px; 
                            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                            text-align: center; 
                        }
                        video { 
                            width: 100%; 
                            height: auto; 
                            margin-bottom: 20px; 
                        }
                        .disclaimer { 
                            font-size: 0.9em; 
                            color: #888; 
                            margin-top: 20px;
                        }
                        a { 
                            display: inline-block; 
                            padding: 10px 20px; 
                            background: #000; 
                            color: #fff; 
                            text-decoration: none; 
                            border-radius: 5px; 
                            font-weight: bold; 
                        }
                        a:hover { 
                            background: #333; 
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <video controls>
                            <source src="{{ video_url }}" type="video/mp4">
                            您的浏览器不支持视频播放。
                        </video>
                        <div class="disclaimer">
                            本视频由用户提供<br>Amer未存储任何相关数据,仅提供缓存服务<br>如有侵权，请联系管理员删除。
                        </div>
                    </div>
                </body>
                </html>
                """,
                video_url=video_url,
            )

        except Exception as e:
            logger.error(f"处理视频播放时发生错误: {e}")
            return await base_error_page("服务器错误", "抱歉，处理您的请求时发生了错误，请稍后再试。"), 500
    @app.route("/uploads/audio/voice", methods=['POST'])
    async def upload_voice():
        try:
            token = (await request.form).get("token")
            text_content = (await request.form).get("textContent")
            audio_file = (await request.files).get("audioFile")

            logger.info(f"上传语音 - 参数校验: token={token}, text_content={text_content}, audio_file_name={audio_file.filename if audio_file else None}")
            if not all([token, text_content, audio_file]):
                logger.error("上传语音 - 缺少必要参数")
                return jsonify({"status": 400, "msg": "缺少必要参数"}), 400
            
            token_key = f"voice_upload_token:{token}"
            custom_name_data = redis_client.get(token_key)
            if not custom_name_data:
                logger.error(f"上传语音 - 无效或过期的 Token: {token}")
                return jsonify({"status": 400, "msg": "无效或过期的 Token"}), 400

            try:
                data = json.loads(custom_name_data)
                custom_name = data.get("remark")
                user_id = data.get("user_id")
                user_name = data.get("user_name")
                logger.info(f"上传语音 - Token 数据解析成功: 上传用户 - user_id={user_id}, remark={custom_name}")
            except (json.JSONDecodeError, AttributeError):
                logger.error(f"上传语音 - Token 数据损坏: {custom_name_data}")
                return jsonify({"status": 400, "msg": "Token 数据损坏"}), 400
            
            ALLOWED_EXTENSIONS = {"mp3", "wav"}
            MAX_FILE_SIZE = 5 * 1024 * 1024

            file_extension = Path(audio_file.filename).suffix.lower()[1:]
            if file_extension not in ALLOWED_EXTENSIONS:
                logger.error(f"上传语音 - 不支持的文件格式: {file_extension}")
                return jsonify({"status": 400, "msg": "不支持的文件格式"}), 400

            file_bytes = audio_file.read()
            logger.info(f"上传语音 - 文件读取成功: 文件名={audio_file.filename}, 文件大小={len(file_bytes)} 字节")
            if len(file_bytes) > MAX_FILE_SIZE:
                logger.error(f"上传语音 - 文件大小超过限制: 实际大小={len(file_bytes)} 字节, 最大大小={MAX_FILE_SIZE} 字节")
                return jsonify({"status": 400, "msg": "文件大小超过限制"}), 400
            
            audio_file.seek(0)

            from utils.config import guijiliudong_key
            url = "https://api.siliconflow.cn/v1/uploads/audio/voice"
            headers = {
                "Authorization": f"Bearer {guijiliudong_key}",
            }
            form_data = aiohttp.FormData()
            form_data.add_field("customName", str(random.randint(1, 1000000)))
            form_data.add_field("text", text_content)
            form_data.add_field("model", "FunAudioLLM/CosyVoice2-0.5B")
            form_data.add_field(
                "file",
                file_bytes,
                filename=audio_file.filename,
                content_type="audio/mpeg"
            )

            logger.info(f"上传语音 - 准备调用外部 API: URL={url}, Headers={headers}")

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=form_data, headers=headers) as response:
                    response_text = await response.text()
                    logger.info(f"上传语音 - 外部 API 响应: Status={response.status}, Response={response_text}")
                    if response.status == 200:
                        result = json.loads(response_text)
                        voice_uri = result.get("uri")
                        
                        voice_style_data = {
                            "user_id": user_id,
                            "user_name": user_name,
                            "voice_uri": voice_uri
                        }
                        redis_client.set(f"voice_style:{custom_name}", json.dumps(voice_style_data))
                        redis_client.delete(token_key)

                        logger.info(f"上传语音 - 成功: Voice_URI={voice_uri}")
                        return jsonify({
                            "status": 0,
                            "msg": f"上传完毕",
                            "data": {"uri": voice_uri}
                        }), 200
                    else:
                        logger.error(f"上传语音 - 外部 API 调用失败: Status={response.status}, Response={response_text}")
                        return jsonify({"status": response.status, "msg": response_text}), response.status

        except Exception as e:
            logger.error(f"上传语音 - 处理过程中发生错误: {e}", exc_info=True)
            return jsonify({"status": 500, "msg": "服务器内部错误"}), 500
    @app.route("/upload-voice-page", methods=['GET'])
    async def upload_voice_combined():
        token = request.args.get("token")
        if not token:
            return await base_error_page("参数错误", "缺少必要参数 token，请检查您的请求。"), 400

        custom_name_key = f"voice_upload_token:{token}"
        custom_name_data = redis_client.get(custom_name_key)
        if not custom_name_data:
            return await base_error_page("无效或过期的 Token", "请重新生成上传链接。"), 400

        try:
            data = json.loads(custom_name_data)
            user_id = data.get("user_id")
            remark = data.get("remark")
        except (json.JSONDecodeError, AttributeError):
            return await base_error_page("Token 数据损坏", "请重新生成上传链接。"), 400

        # 随机语录列表
        quotes = [
            "生活不是等待风暴过去，而是学会在雨中起舞。",
            "成功的秘诀在于坚持不懈奋斗，最终实现自己的目标。",
            "不要因为走得太远，而忘记为什么出发。",
            "每一个不曾起舞的日子，都是对生命的辜负。",
            "人生没有彩排，每天都是现场直播。",
        ]
        random_quote = random.choice(quotes)

        return await render_template_string(
            """
            <!DOCTYPE html>
            <html lang="zh">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>参考语音上传</title>
                <style>
                    body {
                        font-family: 'Segoe UI', Arial, sans-serif;
                        background: linear-gradient(to bottom, #f8f9fa, #e9ecef);
                        color: #212529;
                        margin: 0;
                        padding: 0;
                        min-height: 100vh;
                    }
                    .container {
                        max-width: 600px;
                        margin: 40px auto;
                        padding: 30px;
                        background: #fff;
                        border-radius: 12px;
                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                        text-align: center;
                        transition: transform 0.3s ease;
                    }
                    .container:hover {
                        transform: translateY(-2px);
                    }
                    h1 {
                        color: #212529;
                        font-size: 2em;
                        margin-bottom: 20px;
                        position: relative;
                        padding-bottom: 10px;
                    }
                    h1:after {
                        content: '';
                        position: absolute;
                        bottom: 0;
                        left: 25%;
                        width: 50%;
                        height: 3px;
                        background: linear-gradient(to right, transparent, #212529, transparent);
                    }
                    .quote {
                        font-style: italic;
                        color: #495057;
                        margin-bottom: 25px;
                        padding: 15px;
                        background: #f8f9fa;
                        border-radius: 8px;
                        border-left: 4px solid #212529;
                    }
                    .tabs {
                        display: flex;
                        justify-content: center;
                        gap: 15px;
                        margin-bottom: 25px;
                    }
                    .tab-button {
                        padding: 12px 25px;
                        border: none;
                        border-radius: 8px;
                        background: #212529;
                        color: #fff;
                        cursor: pointer;
                        font-weight: bold;
                        transition: all 0.3s ease;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    }
                    .tab-button:hover {
                        background: #343a40;
                        transform: translateY(-2px);
                        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
                    }
                    .tab-button.active {
                        background: #343a40;
                        box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);
                    }
                    .tab-content {
                        display: none;
                        animation: fadeIn 0.5s ease;
                    }
                    @keyframes fadeIn {
                        from { opacity: 0; transform: translateY(10px); }
                        to { opacity: 1; transform: translateY(0); }
                    }
                    .tab-content.active {
                        display: block;
                    }
                    form {
                        display: flex;
                        flex-direction: column;
                        gap: 20px;
                    }
                    label {
                        font-weight: 600;
                        color: #212529;
                        text-align: left;
                        margin-bottom: -10px;
                    }
                    input[type="text"], textarea, input[type="file"] {
                        padding: 12px;
                        border: 1px solid #ced4da;
                        border-radius: 8px;
                        background: #fff;
                        color: #495057;
                        transition: border-color 0.3s ease;
                    }
                    input[type="text"]:focus, textarea:focus {
                        border-color: #212529;
                        outline: none;
                        box-shadow: 0 0 0 3px rgba(33, 37, 41, 0.1);
                    }
                    button {
                        padding: 12px;
                        border: none;
                        border-radius: 8px;
                        background: #212529;
                        color: #fff;
                        cursor: pointer;
                        font-weight: bold;
                        transition: all 0.3s ease;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    }
                    button:hover {
                        background: #343a40;
                        transform: translateY(-2px);
                        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
                    }
                    .info {
                        font-size: 0.9em;
                        color: #6c757d;
                        margin-top: 25px;
                        padding: 15px;
                        background: #f8f9fa;
                        border-radius: 8px;
                    }
                    audio {
                        width: 100%;
                        margin-top: 15px;
                        border-radius: 8px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    }
                    .audio-card {
                        background: #fff;
                        border-radius: 8px;
                        padding: 20px;
                        margin-top: 20px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                        transition: all 0.3s ease;
                    }
                    .audio-card:hover {
                        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="tabs">
                        <button class="tab-button active" onclick="switchTab('file')">文件上传</button>
                        <button class="tab-button" onclick="switchTab('record')">录音上传</button>
                    </div>
                    <div id="file" class="tab-content active">
                        <form id="uploadForm" enctype="multipart/form-data">
                            <input type="hidden" id="token" name="token" value="{{ token }}">
                            <label for="audioFile">选择音频文件:</label>
                            <input type="file" id="audioFile" name="audioFile" accept="audio/*" required>
                            <label for="textContent">对应的文字内容:</label>
                            <textarea id="textContent" name="textContent" rows="4" placeholder="请输入音频对应的文字内容" required></textarea>
                            <button type="submit">上传</button>
                        </form>
                        <div id="resultMessage" class="message"></div>
                    </div>
                    <div id="record" class="tab-content">
                        <div class="quote">请朗读以下语录：<br><strong>{{ quote }}</strong></div>
                        <button id="recordButton">开始录音</button>
                        <div id="statusMessage" class="message"></div>

                        <div class="audio-card" style="display: none;">
                            <div class="card-header">
                                <span>语音试听</span>
                            </div>
                            <div class="card-body">
                                <audio id="audioPreview" controls style="width: 100%;"></audio>
                                <div id="statusMessage" class="message" style="margin-top: 10px;"></div>
                                <button id="uploadButton" style="margin-top: 10px;">上传录音</button>
                            </div>
                        </div>
                    </div>
                    <div class="info">
                        上传完成后，您可以通过以下命令生成语音：<br>
                        <code>/生成语音 {{ remark }} &lt;文本内容&gt;</code>
                    </div>
                </div>

                <script>
                    // 切换选项卡
                    function switchTab(tabId) {
                        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
                        document.querySelectorAll('.tab-button').forEach(button => button.classList.remove('active'));
                        document.getElementById(tabId).classList.add('active');
                        event.target.classList.add('active');
                    }

                    // 文件上传逻辑
                    document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                        e.preventDefault();

                        const formData = new FormData();
                        formData.append('token', document.getElementById('token').value);
                        formData.append('audioFile', document.getElementById('audioFile').files[0]);
                        formData.append('textContent', document.getElementById('textContent').value);

                        const response = await fetch('/uploads/audio/voice', {
                            method: 'POST',
                            body: formData
                        });

                        const result = await response.json();
                        const resultMessage = document.getElementById('resultMessage');
                        if (response.ok) {
                            resultMessage.textContent = result.msg;
                            resultMessage.style.color = '#2ecc71';
                        } else {
                            resultMessage.textContent = '上传失败: ' + result.msg;
                            resultMessage.style.color = '#e74c3c';
                        }
                    });

                    // 录音上传逻辑
                    let mediaRecorder;
                    let audioChunks = [];
                    let isRecording = false;
                    const statusMessage = document.getElementById('statusMessage');
                    const recordButton = document.getElementById('recordButton');
                    const audioPreview = document.getElementById('audioPreview');
                    const uploadButton = document.getElementById('uploadButton');

                    async function checkMicrophonePermission() {
                        try {
                            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                            stream.getTracks().forEach(track => track.stop());
                            return true;
                        } catch (error) {
                            statusMessage.textContent = '无法访问麦克风，请检查权限设置。';
                            statusMessage.style.color = '#e74c3c';
                            return false;
                        }
                    }

                    recordButton.addEventListener('click', async () => {
                        if (!isRecording) {
                            const hasPermission = await checkMicrophonePermission();
                            if (!hasPermission) return;

                            statusMessage.textContent = '正在录音...';
                            recordButton.textContent = '停止录音';

                            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                            mediaRecorder = new MediaRecorder(stream);

                            mediaRecorder.ondataavailable = event => {
                                audioChunks.push(event.data);
                            };

                            mediaRecorder.onstop = () => {
                                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                                const audioUrl = URL.createObjectURL(audioBlob);

                                const audioCard = document.querySelector('.audio-card');
                                const audioPreview = document.getElementById('audioPreview');
                                audioPreview.src = audioUrl;
                                audioCard.style.display = 'block';

                                statusMessage.textContent = '';
                                isRecording = false;
                                recordButton.textContent = '重新录音';
                            };

                            mediaRecorder.start();
                            isRecording = true;
                        } else {
                            mediaRecorder.stop();
                            mediaRecorder.stream.getTracks().forEach(track => track.stop());
                            audioChunks = [];
                            isRecording = false;
                        }
                    });

                    uploadButton.addEventListener('click', async () => {
                        statusMessage.textContent = '正在上传录音...';

                        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                        const formData = new FormData();
                        formData.append('token', '{{ token }}');
                        formData.append('textContent', '{{ quote }}');
                        formData.append('audioFile', audioBlob, 'recording.wav');

                        const response = await fetch('/uploads/audio/voice', {
                            method: 'POST',
                            body: formData
                        });

                        const result = await response.json();
                        if (response.ok) {
                            statusMessage.textContent = '上传成功！';
                            statusMessage.style.color = '#2ecc71';
                        } else {
                            statusMessage.textContent = '上传失败: ' + result.msg;
                            statusMessage.style.color = '#e74c3c';
                        }
                    });
                </script>
            </body>
            </html>
            """,
            token=token,
            remark=remark,
            quote=random_quote
        )
