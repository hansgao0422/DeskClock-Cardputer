<img width="1200" height="420" alt="deskclock-cardputer-hero" src="https://github.com/user-attachments/assets/b5c387ef-6df5-4d56-b121-2369fea6f1f0" />


# DeskClock for Cardputer ADV

基于 `UIFlow2 / MicroPython` 的 Cardputer ADV 桌面信息面板程序。

## 项目简介

这个程序运行在 `Cardputer ADV` 上，用于在主界面集中显示时间、日期、天气、日出日落、经纬度、梅登黑德网格以及当前通联呼号等信息。

当前版本以“稳定可用”为优先，适合作为日常值守和后续继续升级的基础版本。

## 主要功能

- 本地时间显示，按东八区校时
- UTC 时间显示
- 日期与星期显示
- 按经纬度拉取真实天气数据
- 显示实时温度
- 联网后拉取真实日出、日落时间
- 显示当前使用的经纬度
- 根据经纬度计算 6 位梅登黑德网格
- 通过 WS 显示当前正在通联的呼号
- 支持 WiFi 自动连接、扫描、保存
- 支持设置固定城市、固定经纬度、GPS 开关、WS 服务器 IP
- 支持亮度切换、熄屏、查看电量
- 支持手动刷新天气与 WS

## 主界面显示内容

- 本地时间
- UTC 时间
- 日期
- 星期
- 状态栏
- 温度
- 当前通联呼号
- Maidenhead 6 位网格
- 纬度 / 经度
- Sunrise / Sunset

## 按键说明

主界面下：

- `L`：切换亮度，共 4 档
  - `100%`
  - `75%`
  - `50%`
  - `25%`
- `ESC`：熄屏，再按一次亮屏
- `S`：进入设置页面
- `B`：显示当前电量
- `R`：刷新天气、温度、日出、日落
- `W`：重连 WS，刷新呼号数据

设置界面下：

- `;`：上移选择
- `.`：下移选择
- `Enter`：进入或编辑当前项
- `ESC`：返回主界面

## 设置页面

当前设置项包括：

- `City`
- `Lat`
- `Lon`
- `GPS`
- `IP`
- `WiFi Setup`
- `Back`

说明：

- `GPS = OFF` 时，天气按填写的固定经纬度拉取
- `GPS = ON` 时，优先使用 GPS 获取的经纬度
- `IP` 用于连接呼号 WS 服务

## WiFi 逻辑

开机后程序会先尝试连接已保存的 WiFi。

如果已保存 WiFi 不可用，则可进入 `WiFi Setup`：

1. 扫描周边 WiFi
2. 选择网络
3. 输入密码
4. 连接并保存

## 天气与位置逻辑

天气、温度、日出、日落均按“当前实际使用的经纬度”拉取：

- GPS 关闭：使用设置中填写的 `Lat / Lon`
- GPS 开启：优先使用 GPS 坐标

梅登黑德网格也按当前使用的经纬度实时计算。

## 呼号显示逻辑

主界面的 `Call:` 区域用于显示当前正在通联的呼号。

- WS 连接成功时，状态可显示为 `WS OK`
- 未连接时显示 `WS Off`
- 重连过程中可显示 `WS Try`

当前版本中，呼号字体颜色已设为红色。

## 状态栏常见含义

- `Boot`：启动中
- `Clock OK`：校时成功
- `Clock Loc`：使用本地时间
- `Wx OK`：天气刷新成功
- `Wx Off`：天气刷新失败
- `WS OK`：WS 已连接
- `WS Off`：WS 未连接
- `WS Try`：WS 重连中
- `Offline`：网络未连接
- `BATxx%`：当前电量
- `BL 100% / 75% / 50% / 25%`：亮度档位

<img width="4096" height="3072" alt="微信图片_20260709084930_572_307" src="https://github.com/user-attachments/assets/6e53b6da-139a-419f-8ffb-c21147544028" />

## 目录与主要文件

主程序：

- [cardputer_adv_dashboard_uiflow2.py](C:/Users/Hans/Documents/Codex/2026-07-03/an/outputs/cardputer_adv_dashboard_uiflow2.py)

当前推荐的用户文件系统镜像：

- [deskclock_cardputeradv_fs-user_clean.bin](C:/Users/Hans/Documents/Codex/2026-07-03/an/outputs/deskclock_cardputeradv_fs-user_clean.bin)

当前推荐的完整总固件：

- [deskclock_cardputeradv_full_8mb.bin](C:/Users/Hans/Documents/Codex/2026-07-03/an/outputs/deskclock_cardputeradv_full_8mb.bin)

刷写说明：

- [刷写说明_CardputerADV_DeskClock.txt](C:/Users/Hans/Documents/Codex/2026-07-03/an/outputs/刷写说明_CardputerADV_DeskClock.txt)

当前最佳版本备份：

- [backup_20260709_best_so_far](C:/Users/Hans/Documents/Codex/2026-07-03/an/outputs/backup_20260709_best_so_far)

## 刷写方式

### 方式一：刷完整总固件

适合一次性完整刷入。

- 写入地址：`0x0`
- 文件：`deskclock_cardputeradv_full_8mb.bin`

示例：

```bash
esptool.py --chip esp32s3 --port COMx --baud 1500000 write_flash 0x0 deskclock_cardputeradv_full_8mb.bin
```

### 方式二：只刷用户文件系统

适合设备已经有匹配版本 UIFlow2 固件，只更新程序。

- 写入地址：`0x641000`
- 文件：`deskclock_cardputeradv_fs-user_clean.bin`

示例：

```bash
esptool.py --chip esp32s3 --port COMx --baud 1500000 write_flash 0x641000 deskclock_cardputeradv_fs-user_clean.bin
```

说明：

- `COMx` 请替换为实际串口号
- 当前分区按本地 UIFlow2 源码确认：
  - `vfs offset = 0x641000`
  - `vfs size = 0x1BE000`

## 版本说明

当前版本重点：

- 主界面闪烁已明显减轻
- 时间区域刷新更稳定
- 日期与星期显示已恢复
- 天气刷新与 WS 刷新已拆分
- 呼号显示逻辑已按“当前正在通联的呼号”处理

## 使用建议

推荐首次使用流程：

1. 先刷完整总固件
2. 配置 WiFi
3. 配置固定经纬度或开启 GPS
4. 配置 WS 服务器 IP
5. 返回主界面观察时间、天气、日出日落和呼号状态

后续如果只是更新程序，优先只刷 `fs-user` 镜像即可。




<img width="4816" height="3210" alt="微信图片_20260706160020_552_307" src="https://github.com/user-attachments/assets/6cc131b8-dd77-47b6-a04d-6caf77bcd0bc" />
<img width="6000" height="4000" alt="微信图片_20260706160016_551_307" src="https://github.com/user-attachments/assets/e980306a-ddcb-4af7-a603-da534843f559" />
<img width="6000" height="4000" alt="微信图片_20260706160012_550_307" src="https://github.com/user-attachments/assets/749f00df-ddc7-413c-8162-b2855ed8dbe4" />
<img width="6000" height="4000" alt="微信图片_20260706160008_549_307" src="https://github.com/user-attachments/assets/f9fd38e1-5859-4bae-a811-f8aac34669cb" />

