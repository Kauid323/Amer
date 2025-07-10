Amer是一个QQ与云湖消息互通的机器人，使用Onebot V11协议和反向Websocket

# 食用方法：

## 安装依赖
开启命令行，然后键入 

pip install uvicorn redis openai requests aiocqhttp aiohttp markdown Pillow captcha

回车，然后等待依赖安装完成
## 配置
打开 Amer目录/utils/config.py 

admin_user_id 处填写机器人的主人QQ号，可以是你的

bot_qq 处填写机器人的QQ号

blocked_words 是黑名单词汇，可以添加你的黑名单词汇

token 处填写你云湖机器人的token

写完了就保存
## 安装Redis数据库
安装Redis数据库，地址端口不动，并启动它

[Redis下载](https://redis.io/downloads/)

## 配置Onebot
使用支持Onebot V11协议的服务端进行配置，比如

[Napcat (推荐)](https://github.com/NapNeko/NapCatQQ)，[NoneBot](https://github.com/nonebot/adapter-onebot)等，这里以Napcat为例

登入Napcat后台（记得登录你事先准备的QQ机器人账号！），进入网络配置选项，新建一个Websocket客户端，名称随便填，

URL填写 ws://localhost:端口/ws（你可以在Amer目录/utils/config.py 里的server项自定义端口，这里默认ws://localhost:5888/ws），启用和上报自身消息都打开，消息格式选择Array，并保存。

这样就可以了，然后你就可以把Napcat扔后台

## 配置Amer数据库

打开命令行执行

py Amer存放目录\Amer-main\utils\sqlite\initialize_yh_bind_db.py

就可以了
## 启动Amer
打开Amer目录

执行 py ./main.py

记得把 localhost 映射到公网，Websocket端口和机器人消息订阅端口也是一样的，

在云湖控制台机器人里写上http://你的公网ip:端口/yh/webhook

后面这个/yh/webhook地址可以在Amer目录/utils/config.py 里的yh项下的path更改。这里默认/yh/webhook

记得保存地址！还要记得在云湖控制台设置一个直发指令，指令:"帮助"，以便你更好的使用Amer

把消息订阅内的 普通消息事件 和 指令消息事件 打开，这样就可以使用你的Amer了

> 这是最基础的消息转发功能，其实还能在config.py里面设置openai，实现QQ Amer AI对话（（（（（（（（（（（（（（

# [配置云湖机器人的指令](amer_adapter/README.md)

# [对Config.py内配置的一些解释](utils/README.md)
 
