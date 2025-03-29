from utils import logger
from utils.config import redis_client
from quart import jsonify, render_template_string
from .base_page import base_error_page
import json
from amer_adapter import basetools
def register_routes(app, qqBot):
    async def get_stats_data():
        try:
            # 获取各平台消息数量
            platform_stats = {"QQ": 0, "YH": 0, "MC": 0}
            group_stats = {}
            for platform in platform_stats.keys():
                keys = [key.decode('utf-8') for key in redis_client.keys(f"{platform}:*:{platform}:*")]
                for key in keys:
                    messages = [msg.decode('utf-8') for msg in redis_client.lrange(key, 0, -1)]
                    count = len(messages) if messages else 0
                    platform_stats[platform] += count
                    
                    # 提取群组ID并统计
                    parts = key.split(':')
                    group_id = parts[1]
                    group_key = f"{platform}:{group_id}"
                    group_stats[group_key] = group_stats.get(group_key, 0) + count

            # 总消息数等于各平台消息数之和
            total_messages = sum(platform_stats.values())

            # 获取活跃群组TOP5 (所有平台)
            top_groups = sorted(group_stats.items(), key=lambda x: x[1], reverse=True)[:5]
            
            # 获取按平台分类的TOP5群组
            platform_top_groups = {}
            for platform in platform_stats.keys():
                platform_groups = [(k, v) for k, v in group_stats.items() if k.startswith(platform)]
                platform_top_groups[platform] = sorted(platform_groups, key=lambda x: x[1], reverse=True)[:5]

            # 获取消息频率数据
            freq_keys = [key.decode('utf-8') for key in redis_client.keys("message_frequency:*")]
            freq_stats = []
            for key in freq_keys:
                parts = key.split(':')
                count = int(redis_client.get(key).decode('utf-8') or 0)
                freq_stats.append({
                    "platform": parts[1],
                    "user_id": parts[2],
                    "count": count
                })
            top_freq_users = sorted(freq_stats, key=lambda x: x["count"], reverse=True)[:5]

            # 获取近期违规消息
            sensitive_keys = [key.decode('utf-8') for key in redis_client.keys("sensitive_messages:*")]
            violations = []
            for key in sensitive_keys:
                # 检查键类型是否为列表
                if redis_client.type(key).decode('utf-8') == 'list':
                    sensitive_messages = [msg.decode('utf-8') for msg in redis_client.lrange(key, 0, 10)]
                    for msg in sensitive_messages:
                        try:
                            message = json.loads(msg)
                            violations.append({
                                "sender_nickname": message.get("sender_nickname"),
                                "message_content": message.get("message_content"),
                                "timestamp": message.get("timestamp"),
                                "id_from": message.get("id_from"),
                                "platform_from": message.get("platform_from")
                            })
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.error(f"解析敏感消息失败: {e}")
            
            # 按时间戳倒序排列违规消息
            violations = sorted(violations, key=lambda x: x["timestamp"], reverse=True)[:5]

            # 获取群组名称
            group_names = {}
            for group_key in group_stats.keys():
                platform, group_id = group_key.split(':')
                if platform == "QQ":
                    group_names[group_key] = f"QQ群 - {group_id}"
                elif platform == "MC":
                    group_names[group_key] = f"MC群 - {group_id}"
                else:
                    group_names[group_key] = f"云湖群 - {group_id}"
            
            # 返回统计数据
            return {
                "total_messages": total_messages,
                "platform_stats": platform_stats,
                "recent_violations": violations,
                "top_groups": [(group_names[g[0]], g[1]) for g in top_groups],
                "platform_top_groups": {
                    platform: [(group_names[g[0]], g[1]) for g in groups]
                    for platform, groups in platform_top_groups.items()
                }
            }

        except Exception as e:
            logger.error(f"获取统计数据失败: {e}")
            raise

    @app.route("/api/stats", methods=['GET'])
    async def stats_api():
        try:
            stats_data = await get_stats_data()
            return jsonify({
                "status": 0,
                "msg": "查询成功",
                "data": stats_data
            }), 200
        except Exception as e:
            logger.error(f"获取统计数据失败: {e}")
            return jsonify({"status": 500, "msg": "服务器内部错误"}), 500

    @app.route("/", methods=['GET'])
    async def home():
        """项目主页"""
        try:
            stats_data = await get_stats_data()
            total_messages = stats_data["total_messages"]
            platform_stats = stats_data["platform_stats"]
            violations = stats_data["recent_violations"]
            top_groups = stats_data["top_groups"]

            platform_top_groups = stats_data["platform_top_groups"]
            return await render_template_string(
                """
                <!DOCTYPE html>
                <html lang="zh">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Amer 消息同步机器人</title>
                    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                    <style>
                        body {
                            font-family: 'Roboto', sans-serif;
                            margin: 0;
                            padding: 0;
                            background: #f5f7fa;
                            color: #333;
                        }
                        .container {
                            max-width: 1200px;
                            margin: 0 auto;
                            padding: 20px;
                        }
                        header {
                            background: linear-gradient(135deg, #6e8efb, #a777e3);
                            color: white;
                            padding: 40px 20px;
                            text-align: center;
                            border-radius: 10px;
                            margin-bottom: 30px;
                            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                        }
                        h1 {
                            margin: 0;
                            font-size: 2.5em;
                        }
                        .description {
                            max-width: 800px;
                            margin: 20px auto;
                            line-height: 1.6;
                        }
                        .features-container {
                            display: flex;
                            flex-wrap: wrap;
                            gap: 20px;
                            margin-bottom: 30px;
                        }
                        .feature-card {
                            flex: 1;
                            min-width: 250px;
                            background: white;
                            border-radius: 10px;
                            padding: 20px;
                            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
                        }
                        .feature-card h3 {
                            color: #6e8efb;
                            margin-top: 0;
                        }
                        .stats-container {
                            background: white;
                            border-radius: 10px;
                            padding: 20px;
                            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
                            margin-bottom: 30px;
                        }
                        .stat-card {
                            margin-bottom: 20px;
                        }
                        .stat-value {
                            font-size: 1.5em;
                            font-weight: bold;
                            color: #6e8efb;
                            margin: 10px 0;
                        }
                        .violations-container {
                            background: white;
                            border-radius: 10px;
                            padding: 20px;
                            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
                        }
                        .violation-item {
                            border-bottom: 1px solid #eee;
                            padding: 15px 0;
                        }
                        .violation-item:last-child {
                            border-bottom: none;
                        }
                        .violation-content {
                            color: #666;
                            margin-top: 5px;
                        }
                        .violation-meta {
                            font-size: 0.9em;
                            color: #999;
                            margin-top: 5px;
                        }
                        .contact-info {
                            margin-top: 20px;
                            font-size: 0.9em;
                            color: #ccc;
                            text-align: center;
                        }
                        .contact-info p {
                            margin: 0;
                            padding: 0;
                        }
                        .contact-info ul {
                            list-style: none;
                            padding: 0;
                            margin: 5px 0 0;
                        }
                        .contact-info li {
                            display: inline-block;
                            margin-right: 15px;
                        }
                        .contact-info a {
                            color: #ddd;
                            text-decoration: none;
                            font-weight: normal;
                        }
                        .contact-info a:hover {
                            text-decoration: underline;
                            color: #fff;
                        }
                        /* 平台统计样式 */
                        .platform-stats {
                            display: flex;
                            gap: 15px;
                            flex-wrap: wrap;
                        }
                        .platform-badge {
                            padding: 8px 15px;
                            border-radius: 20px;
                            font-weight: bold;
                            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                            transition: all 0.3s ease;
                        }
                        .platform-badge.qq {
                            background: #12b7f5;
                            color: white;
                        }
                        .platform-badge.yunhu {
                            background: #8a2be2;
                            color: white;
                        }
                        .platform-tabs {
                            display: flex;
                            gap: 10px;
                            margin-bottom: 15px;
                        }
                        .platform-tab {
                            padding: 8px 15px;
                            border-radius: 20px;
                            background: #eee;
                            cursor: pointer;
                            transition: all 0.3s ease;
                        }
                        .platform-tab.active {
                            background: #6e8efb;
                            color: white;
                        }
                        .platform-badge.mc {
                            background: #5cb85c;
                            color: white;
                        }

                        /* 活跃群组样式 */
                        .top-groups {
                            list-style: none;
                            padding: 0;
                        }
                        .top-groups li {
                            margin-bottom: 10px;
                            display: flex;
                            align-items: center;
                        }
                        .group-name {
                            min-width: 200px;
                            font-weight: bold;
                        }
                        .message-bar {
                            height: 30px;
                            background: linear-gradient(90deg, #6e8efb, #a777e3);
                            border-radius: 15px;
                            display: flex;
                            align-items: center;
                            justify-content: flex-end;
                            padding-right: 10px;
                            color: white;
                            font-weight: bold;
                            transition: width 0.5s ease;
                        }
                        .message-bar .count {
                            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
                        }

                        @media (max-width: 768px) {
                            .features-container {
                                flex-direction: column;
                            }
                            .top-groups li {
                                flex-direction: column;
                                align-items: flex-start;
                            }
                            .group-name {
                                margin-bottom: 5px;
                            }
                            .message-bar {
                                width: 100% !important;
                            }
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <header>
                            <h1>Amer 消息同步机器人</h1>
                            <div class="description">
                                跨平台消息同步与管理机器人，支持云湖群、QQ群和Minecraft服务器之间的消息双向或单向同步。
                            </div>
                            <div class="contact-info">
                                <ul>
                                    <li>Email: <a href="mailto:wsu2059@qq.com">wsu2059@qq.com</a></li>
                                    <li>GitHub: <a href="https://github.com/wsu2059q/amer" target="_blank">Amer Bot Repository</a></li>
                                </ul>
                            </div>
                        </header>

                        <!-- 机器人功能介绍 -->
                        <div class="features-container">
                            <div class="feature-card">
                                <h3>跨平台同步</h3>
                                <p>支持云湖群、QQ群和Minecraft服务器之间的消息双向或单向同步，打破平台壁垒。</p>
                            </div>
                            <div class="feature-card">
                                <h3>消息管理</h3>
                                <p>提供消息统计、敏感词过滤、违规消息记录等功能，帮助管理员更好地管理群组。</p>
                            </div>
                            <div class="feature-card">
                                <h3>高可用性</h3>
                                <p>基于Redis实现消息队列和持久化，确保消息不丢失，系统稳定运行。</p>
                            </div>
                        </div>

                        <!-- 统计信息 -->
                        <div class="stats-container">
                            <h2>统计信息</h2>
                            <div class="stat-card">
                                <h3>总消息数</h3>
                                <div class="stat-value">{{ total_messages }}</div>
                            </div>
                            <div class="stat-card">
                                <h3>平台消息分布</h3>
                                <div class="platform-stats">
                                    <span class="platform-badge yunhu">云湖: {{ platform_stats.YH }}</span>
                                    <span class="platform-badge qq">QQ: {{ platform_stats.QQ }}</span>
                                    <span class="platform-badge mc">MC: {{ platform_stats.MC }}</span>
                                </div>
                            </div>
                            <div class="stat-card">
                                <h3>活跃群组TOP5</h3>
                                <div class="platform-tabs">
                                    <div class="platform-tab active" data-platform="all">总排行</div>
                                    <div class="platform-tab" data-platform="YH">云湖</div>
                                    <div class="platform-tab" data-platform="QQ">QQ</div>
                                    <div class="platform-tab" data-platform="MC">MC</div>
                                </div>
                                <div class="groups-container">
                                    <!-- 总排行 -->
                                    <div class="group-list" data-platform="all">
                                        <ul class="top-groups">
                                            {% set max_messages = top_groups[0][1] if top_groups else 1 %}
                                            {% for group in top_groups %}
                                            <li>
                                                <span class="group-name">{{ group[0] }}</span>
                                                <div class="message-bar" style="width: {{ (group[1]/max_messages)*100 }}%">
                                                    <span class="count">{{ group[1] }}</span>
                                                </div>
                                            </li>
                                            {% endfor %}
                                        </ul>
                                    </div>
                                    <!-- QQ群 -->
                                    <div class="group-list" data-platform="QQ" style="display:none">
                                        <ul class="top-groups">
                                            {% set qq_max = platform_top_groups.QQ[0][1] if platform_top_groups.QQ else 1 %}
                                            {% for group in platform_top_groups.QQ %}
                                            <li>
                                                <span class="group-name">{{ group[0] }}</span>
                                                <div class="message-bar" style="width: {{ (group[1]/qq_max)*100 }}%">
                                                    <span class="count">{{ group[1] }}</span>
                                                </div>
                                            </li>
                                            {% endfor %}
                                        </ul>
                                    </div>
                                    <!-- 云湖群 -->
                                    <div class="group-list" data-platform="YH" style="display:none">
                                        <ul class="top-groups">
                                            {% set yh_max = platform_top_groups.YH[0][1] if platform_top_groups.YH else 1 %}
                                            {% for group in platform_top_groups.YH %}
                                            <li>
                                                <span class="group-name">{{ group[0] }}</span>
                                                <div class="message-bar" style="width: {{ (group[1]/yh_max)*100 }}%">
                                                    <span class="count">{{ group[1] }}</span>
                                                </div>
                                            </li>
                                            {% endfor %}
                                        </ul>
                                    </div>
                                    <!-- MC群 -->
                                    <div class="group-list" data-platform="MC" style="display:none">
                                        <ul class="top-groups">
                                            {% set mc_max = platform_top_groups.MC[0][1] if platform_top_groups.MC else 1 %}
                                            {% for group in platform_top_groups.MC %}
                                            <li>
                                                <span class="group-name">{{ group[0] }}</span>
                                                <div class="message-bar" style="width: {{ (group[1]/mc_max)*100 }}%">
                                                    <span class="count">{{ group[1] }}</span>
                                                </div>
                                            </li>
                                            {% endfor %}
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            <script>
                                document.querySelectorAll('.platform-tab').forEach(tab => {
                                    tab.addEventListener('click', function() {
                                        // 更新标签状态
                                        document.querySelectorAll('.platform-tab').forEach(t => {
                                            t.classList.remove('active');
                                        });
                                        this.classList.add('active');
                                        
                                        // 显示对应的群组列表
                                        const platform = this.dataset.platform;
                                        document.querySelectorAll('.group-list').forEach(list => {
                                            list.style.display = 'none';
                                        });
                                        document.querySelector(`.group-list[data-platform="${platform}"]`).style.display = 'block';
                                    });
                                });
                            </script>
                        </div>

                        <!-- 违规消息 -->
                        <div class="violations-container">
                            <h2>近期违规公示</h2>
                            {% if violations %}
                                {% for violation in violations %}
                                    <div class="violation-item">
                                        <div class="violation-meta">
                                            <strong>{{ violation.sender_nickname }}</strong> ({{ violation.platform_from }})
                                        </div>
                                        <div class="violation-content">
                                            {{ violation.message_content }}
                                        </div>
                                        <div class="violation-meta">
                                            {{ violation.timestamp }} · 群组: {{ violation.id_from }}
                                        </div>
                                    </div>
                                {% endfor %}
                            {% else %}
                                <p>暂无违规消息</p>
                            {% endif %}
                        </div>
                    </div>
                </body>
                </html>
                """,
                total_messages=total_messages,
                platform_stats=platform_stats,
                violations=violations,
                top_groups=top_groups,
                platform_top_groups=platform_top_groups
            )
        except Exception as e:
            logger.error(f"加载主页失败: {e}")
            return await base_error_page("服务器错误", "加载主页时发生错误，请稍后再试"), 500
