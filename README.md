# AI读书
## 效果展示：
[夸克网盘「皮囊_曹操.wav」](https://pan.quark.cn/s/b0729ae59829)

[夸克网盘「皮囊_女儿国国王.wav」](https://pan.quark.cn/s/55293cb79611)

基于Maskgct做的AI读书项目。

给我一本电子书，再给一段参考音频，直接生成特定声音的讲书音频。

书籍阅读部分支持本地Ollama和外部API，这里主要是考虑一般情况下外部API那些所谓的满血版大语言模型确实能力更强，而且更重要的是现在API都是白菜价，不，可能比白菜更便宜。而本地Ollama如果不能用到14B以上的模型，那阅读能力真是难以评价，我本地的Ollama最大也就能运行14B的Deepseek，效果只能说还行。
语音合成部分采用Maskgct，实际测试中有6G显存就够了，低于6G显存未测试。

## 项目流程图
![项目流程图](./readme/tree.png)

## 界面图
![环境自检](./readme/launch.png)
![](./readme/readout.png)
![](./readme/ttsprocess.png)
![](./readme/ttsout.png)

## 技术交流：
[知识星球【AI改变生活】](https://t.zsxq.com/hu930)
![微信](./readme/weixin.jpg)

