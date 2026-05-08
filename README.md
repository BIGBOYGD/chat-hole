# Chat Hole

一个局域网终端聊天工具，支持多人在线、私聊、群聊、改名、文件/图片传输和 Windows 消息提醒。

## 功能

- 一台服务器，多台客户端连接
- 客户端自动发现局域网服务器，不必手动输入服务器 IP
- 在线联系人动态编号，用户离线后序号自动重排
- 私聊和群聊
- 修改自己的显示名字，其他人会收到系统提示
- 发送图片或普通文件，文件按分片传输，避免大文件卡死
- 收到消息时触发终端铃声和 Windows Terminal/PowerShell 任务栏提醒
- 中文交互，同时提供短命令

## 目录结构

```text
chat/
  lan_chat.py              # 兼容启动入口
  README.md                # 使用说明
  lan_chat/
    __init__.py
    cli.py                 # 命令行入口
    client.py              # 客户端逻辑、命令解析、文件收发
    config.py              # 默认端口、路径、分片大小
    discovery.py           # UDP 广播和局域网服务器自动发现
    protocol.py            # JSON Lines 网络协议
    server.py              # 服务器、用户管理、消息转发
    terminal.py            # 终端输入行、提醒、输出重绘
    utils.py               # IP 检测、命令参数解析等工具函数
```

## 环境要求

- Python 3.9+
- Windows PowerShell / Windows Terminal / VS Code 终端均可
- 所有客户端和服务器在同一个局域网内

安装包会自动安装 Rich 和 prompt_toolkit。Windows 下 `/ui cyber` 使用 Rich 做终端美化，输入控制沿用默认界面的固定底部输入逻辑；默认 `plain` 界面仍保持原来的轻量文本风格。

## 安装

在项目目录中执行：

```powershell
pip install .
```

安装后可以直接使用命令：

```powershell
chat-hole --help
```

如果你想边改代码边使用，可以安装为可编辑模式：

```powershell
pip install -e .
```

不想安装时，也可以继续使用兼容入口：

```powershell
python .\lan_chat.py --help
```

如果当前电脑没有 Python 目录写入权限，可以使用本地安装脚本：

```powershell
.\install.ps1
```

它会在项目目录创建 `.venv`，安装本项目，并生成两个启动脚本：

```powershell
.\run-server.ps1
.\run-client.ps1 --name 小高
```

也可以直接安装已经构建好的 wheel：

```powershell
pip install .\dist\chat_hole-0.2.0-py3-none-any.whl
```

## 启动服务器

选择一台电脑作为服务器：

```powershell
chat-hole --server
```

启动后会显示类似：

```text
聊天服务器已启动。端口: 9000
本机IP: 192.168.19.14
客户端现在可以直接运行: python .\lan_chat.py
按 Ctrl+C 关闭服务器。
```

服务器会通过 UDP 广播自己的地址，其他客户端启动后会自动发现并连接。

如果端口被占用，可以换端口：

```powershell
chat-hole --server --port 9001
```

## 连接服务器

客户端连接服务器：

```powershell
chat-hole --name 一条咸鱼
```

如果发现到多个服务器，客户端会列出服务器并让你选择编号。

如果服务器改了端口，客户端也要指定同样端口用于发现：

```powershell
chat-hole --port 9001 --name 一条咸鱼
```

如果 UDP 广播被防火墙或网络策略拦截，仍然可以手动指定服务器 IP：

```powershell
chat-hole 192.168.19.14 --port 9001 --name 一条咸鱼
```

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `/l` | 查看在线联系人和群聊 |
| `/p 名字或序号` | 切换到某个人的私聊 |
| `/g 群名` | 切换到群聊 |
| `/c 群名 成员1 成员2` | 创建群聊 |
| `/img 文件路径` | 向当前会话发送图片或文件 |
| `/ui [plain\|cyber]` | 切换终端界面样式，默认 plain |
| `/clear` | 清除当前终端文本 |
| `/n 新名字` | 修改自己的显示名字 |
| `/t` | 测试消息提醒 |
| `/h` | 查看帮助 |
| `/q` | 退出客户端 |

中文命令也可用：

```text
/联系人
/私聊 小王
/群聊 项目组
/建群 项目组 小王 小李
/图片 D:\test\a.png
/美化 cyber
/清屏
/改名 新名字
/提醒测试
/退出
```

## 终端界面样式

默认界面是 `plain`，也就是原来的无美化文本界面。进入客户端后可以切换到基于 Rich 和 prompt_toolkit 的炫酷终端风格：

```text
/ui cyber
```

恢复默认界面：

```text
/ui plain
```

也可以只输入 `/ui`，在 `plain` 和 `cyber` 之间来回切换。`/ui fancy` 会作为 `cyber` 的兼容别名；中文命令 `/美化 cyber`、`/界面 plain` 也可用。

`cyber` 模式会清屏并绘制 CHAT-HOLE CYBERLINK 横幅，聊天记录会以 Rich 霓虹卡片显示。Windows 下输入栏沿用和 `plain` 相同的固定底部控制逻辑，避免第三方输入渲染和聊天输出互相覆盖。

聊天输入行会固定在终端底部，新的聊天记录和系统消息会在上方滚动显示。

## 私聊

查看联系人：

```text
/l
```

示例输出：

```text
在线联系人:
  1. 小高  192.168.19.14
  2. 小王  192.168.19.23
```

进入私聊：

```text
/p 2
```

或者：

```text
/p 小王
```

底部提示会显示当前会话：

```text
[私聊:小王] >
```

之后直接输入消息并回车发送。

## 群聊

创建群聊：

```text
/c 项目组 小高 小王
```

进入群聊：

```text
/g 项目组
```

底部提示会显示：

```text
[群聊:项目组] >
```

之后直接输入消息并回车发送到群里。

## 发送图片或文件

先进入私聊或群聊，然后发送文件：

```text
/img "D:\笔记\cmake\硬件工程师炼成之路笔记-2024-09-21.pdf"
```

路径有空格时请加引号。单引号和双引号都支持：

```text
/img 'D:\图片\截图 1.png'
```

收到的文件会保存到：

```text
%USERPROFILE%\.chat-hole\received_files
```

可以通过环境变量修改保存目录：

```powershell
$env:CHAT_HOLE_DATA_DIR="D:\Tool_miracle\chat"
chat-hole 192.168.19.14 --name 小高
```

说明：

- 当前只支持发送单个文件，不支持直接发送文件夹
- 文件会按 48KB 分片传输
- 大文件发送时客户端不会阻塞输入界面

## 消息提醒

收到别人发来的消息时，程序会触发：

- 终端铃声
- Windows Terminal / PowerShell 任务栏闪烁
- Windows Terminal 标签页提醒状态

手动测试：

```text
/t
```

注意：

- 当前窗口在前台时，Windows 可能不会明显闪烁
- 窗口最小化或在后台时提醒更明显
- 按任意键后会清除 Windows Terminal 标签页上的提醒状态

## 退出

客户端退出：

```text
/q
```

服务器退出：

```text
Ctrl+C
```

## 常见问题

### 连接失败

检查：

- 服务器是否已经启动
- 客户端是否发现了服务器；如果发现不到，可临时手动指定服务器 IP
- 服务器和客户端端口是否一致
- Windows 防火墙是否允许 Python 进行 TCP/UDP 局域网通信

### 文件不存在

确认路径存在：

```powershell
Test-Path "D:\test\1.png"
```

返回 `True` 后再发送：

```text
/img "D:\test\1.png"
```

### 为什么联系人序号会变化

联系人序号是当前在线列表的临时编号。有人离线后，序号会重新从 1 排列，方便用 `/p 1`、`/p 2` 快速选择。

### 能不能不开服务器

当前新版是服务器/客户端模式。多人私聊、群聊、改名同步、文件转发都依赖服务器，所以需要先开服务器。
