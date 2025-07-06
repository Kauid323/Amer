config.py 内配置的解释

admin_user_id ：机器人主人的QQ号

temp_folde ：缓存目录

server ：服务器开启地址

token ：云湖机器人的Token

webhook下的path ：云湖机器人消息订阅地址，这个是地址后面配置的订阅路径，云湖控制台消息订阅必填这个路径，当然也可以自定义

blocked_words ：屏蔽词

OpenAI ：AI对话配置

Redis ：Redis数据库连接地址，最好不要动

SQLite ：SQL数据库路径，最好不要动

> 后记:OpenAI配置
> config里找到get_ai类
> 找到其中一个子类drive_model，填上你AI模型的Model ID
> 这里以PPIO欧派云为例
> ![Screenshot_2025-07-06-13-56-10-833_mark via-edit](https://github.com/user-attachments/assets/2fc947f8-d66f-47f3-a3f5-894b1026ef69)
> 图中画橙色线的就是Model id，然后记住drive_model所属的AI_drive的累名，是这样的："AI_drive == "aliyun""里的aliyun
>
> 翻到get_ai类的上面，有个
> AI_drive = "114514"
> low_AI_deive = "114514"
> 把里面的114514换成你刚才的AI_drive == "后面的字
> 回到config上面，有个OpenAI的配置
> 把和刚才Ai_drive类名有关的url填上你的AI提供商给的url
> key填上你在AI提供商控制台给的api key
> 最后保存
