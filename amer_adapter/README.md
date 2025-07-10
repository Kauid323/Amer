# 如何配置云湖机器人的指令？

1.打开你的云湖机器人控制台，在"指令列表"分别新建“绑定”，”解绑“，”同步模式“这三个自定义输入指令
![image](https://github.com/user-attachments/assets/6d5b3f5a-df88-4978-9808-695c868aa65e)

> Tips:“自定义输入指令”就是表单指令

2.在”绑定“这个自定义输入指令里面分别创建”单选框“和”输入框",照着下面填（显示效果是这样的）
![image](https://github.com/user-attachments/assets/94324cf4-5b70-4157-9839-8130efe4b678)

在"解绑"这个自定义输入指令里面分别创建”单选框“和”输入框",照着下面填（显示效果是这样的）
![image](https://github.com/user-attachments/assets/4788690c-bb5d-40fd-b3a2-c08ed822ec46)

在"同步模式"这个自定义输入指令里面分别创建"选择器",“单选框","输入框"",照着下面填（显示效果是这样的）
![image](https://github.com/user-attachments/assets/2b534fb7-84af-470f-9224-a87775d2cf58)

### 3.打开  存放Amer的目录\Amer-main\amer_adapter\yunhu\handler.py
找到第146行，这个146-161行是处理绑定指令的玩意

给这个 valid_setting_ids 里面的 uhorxv zsvovb 分别换上云湖控制台这个”绑定“指令的单选框和输入框的表单ID
![image](https://github.com/user-attachments/assets/ec1ba17b-ae63-42e0-8fca-4130fa4f3442)
> 下面的 uhorxv zsvovb 更换方法同理
> 
> (建议使用Ctrl+H把原来的全替换成你自己的表单ID（（（（（（（（（（

翻到第240行，这里第240-258行是处理解绑指令的部分，跟换绑定这部分也是同理，这里不再多说
![image](https://github.com/user-attachments/assets/89afdce3-1799-4df4-bc8b-65a7b2692890)
> 这个"yvybln"可能是关于一键解绑的指令，有兴趣可以自己研究一下
> 由于电脑配置的环境极佳，我就不再折腾了😂
> 建议使用Ctrl+H把原来的全替换成你自己的表单ID

翻到第313行，这里的第313-332行是处理同步模式指令的地方，跟换绑定这部分也是同理
![image](https://github.com/user-attachments/assets/33973502-31c2-4c1e-97a9-d23072f10463)
> 建议使用Ctrl+H把原来的全替换成你自己的表单ID

## 弄完之后保存，就OK了



















