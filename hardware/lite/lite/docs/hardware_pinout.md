# STM32F103C8T6 模块接线表

本工程当前已经改为 FreeRTOS 架构，贴近论文中的 `SensorTask / CommTask / DisplayTask` 思路。STM32F103C8T6 资源比论文使用的 STM32H743 小很多，所以这里只接入最小 FreeRTOS 内核：任务、队列、互斥量、软件定时器和 `heap_4`。

## 示例/PDF 依据

我按你给的 `配套传感器资料` 目录，以及同一资料包里的 EEPROM 例程查过。最终引脚不是完全照搬某一个例程，而是在例程/PDF 约束下避开冲突后的分配。

| 模块 | 示例或 PDF 中看到的信息 | 本项目取舍 |
| --- | --- | --- |
| OLED 0.96 IIC | OLED 的 STM32F103C8 IIC 示例实际用 PA5 作 SCL、PA7 作 SDA；OLED IIC PDF 写 D0 为 IIC 时钟线、D1 为 IIC 数据线，SSD1306，常用地址 0x78/0x7A | PA5/PA7 与 W25Q32 的 SPI1 冲突，所以改用硬件 I2C1 的 PB6/PB7 |
| AT24C08 | HAL EEPROM 例程用 PB10/PB11 软件 IIC；标准库例程说明里也是 B10 接 SCL、B11 接 SDA，100 kHz | PB10/PB11 留给 ESP8266 的 USART3，所以 AT24C08 和 OLED 共用 PB6/PB7 |
| W25Q32 | Winbond PDF 写 W25Q32JV 是 2.7V 到 3.6V 供电，Standard SPI 使用 CLK、/CS、DI、DO | 使用 STM32F103C8T6 标准 SPI1：PA4/PA5/PA6/PA7 |
| JDY-31/JDY-3x 蓝牙 | JDY-31 PDF 写通信接口 UART，VCC 1.8V 到 3.6V、建议 3.3V，TXD/RXD 为 TTL 电平，默认波特率 9600 | 使用 USART1：PA9/PA10，波特率 9600 |
| ESP8266 | ESP8266 PDF 写 VCC 3.0V 到 3.6V，EN/CH_PD 高电平有效，RST 低电平有效，AT 固件默认 115200 | 使用 USART3：PB10/PB11，另给 EN/RST 分配 PB12/PB13 |
| DHT11 | DHT11 PDF 写单线双向 DATA，供电 3V 到 5.5V，短线建议 5K 上拉，上电后等待 1s；示例是 51 单片机 P2.0 | STM32 侧用 PB0，驱动中按时序切换输出/输入 |
| DS18B20 | DS18B20 PDF 写 1-Wire 只需一根 DQ 数据线，DQ 为开漏接口，需要弱上拉，供电 3.0V 到 5.5V；示例是 51 单片机 P3.6 | STM32 侧用 PB1，建议外接 4.7K 上拉到 3.3V |
| 红外遥控 | 红外 PDF 写 NEC 编码、38 kHz，Arduino 示例接 D11，串口 9600 打印键值 | STM32 侧用 PA0/EXTI0 捕获边沿，TIM2 做微秒计时 |

## 调试口

| 功能 | STM32 引脚 | 说明 |
| --- | --- | --- |
| SWDIO | PA13 | 保留下载调试 |
| SWCLK | PA14 | 保留下载调试 |
| JTAG | PB3/PB4/PA15 | 已禁用 JTAG，释放为普通 GPIO 备用 |

## I2C1 总线

OLED 0.96 寸 4 针 IIC 和 AT24C08 共用 I2C1。两个模块地址不同，可以挂在同一条总线上。OLED 示例里的 PA5/PA7 已让给 W25Q32，AT24C08 示例里的 PB10/PB11 已让给 ESP8266。

| 模块 | 模块引脚 | STM32 引脚 | 备注 |
| --- | --- | --- | --- |
| OLED | SCL | PB6 / I2C1_SCL | 100 kHz |
| OLED | SDA | PB7 / I2C1_SDA | 需要上拉，模块通常自带 |
| AT24C08 | SCL | PB6 / I2C1_SCL | 与 OLED 共线 |
| AT24C08 | SDA | PB7 / I2C1_SDA | 与 OLED 共线 |
| OLED/AT24C08 | VCC | 3.3V | 不建议接 5V |
| OLED/AT24C08 | GND | GND | 共地 |

## W25Q32 NOR Flash

| 模块引脚 | STM32 引脚 | 说明 |
| --- | --- | --- |
| CS / NSS | PA4 | 软件片选，空闲高电平 |
| SCK / CLK | PA5 / SPI1_SCK | SPI1 |
| DO / MISO | PA6 / SPI1_MISO | Flash 输出到 MCU |
| DI / MOSI | PA7 / SPI1_MOSI | MCU 输出到 Flash |
| WP / HOLD | 3.3V | 如果模块已板载上拉则不用另接 |
| VCC | 3.3V | W25Q32 只能 3.3V |
| GND | GND | 共地 |

## 串口模块

| 模块 | 模块引脚 | STM32 引脚 | 串口 | 默认波特率 |
| --- | --- | --- | --- | --- |
| JDY-3x 蓝牙 | TXD | PA10 / USART1_RX | USART1 | 9600 |
| JDY-3x 蓝牙 | RXD | PA9 / USART1_TX | USART1 | 9600 |
| ESP8266 | TXD | PB11 / USART3_RX | USART3 | 115200 |
| ESP8266 | RXD | PB10 / USART3_TX | USART3 | 115200 |
| ESP8266 | EN / CH_PD | PB12 | 高电平使能 |
| ESP8266 | RST | PB13 | 默认拉高，低电平复位 |

串口接线要交叉：模块 TXD 接 MCU RX，模块 RXD 接 MCU TX。JDY-3x、ESP8266 都按 3.3V TTL 电平处理。

## 单总线/数据 GPIO

| 模块 | 模块引脚 | STM32 引脚 | 说明 |
| --- | --- | --- | --- |
| DHT11 | DATA | PB0 | 默认上拉输入，驱动读写时切换开漏/输入 |
| DS18B20 | DQ | PB1 | 默认上拉输入，建议外接 4.7k 上拉到 3.3V |

DHT11 上电后先等 1 秒再读；DS18B20 的 DQ 是开漏 1-Wire，总线空闲必须被上拉。

## 蜂鸣器与红外

| 模块 | 模块引脚 | STM32 引脚 | 说明 |
| --- | --- | --- | --- |
| 高电平触发蜂鸣器 | SIG | PA8 | 输出高电平响，默认低电平关闭 |
| 红外接收模块 | OUT | PA0 / EXTI0 | 双边沿中断，用 TIM2 做微秒计时 |

红外接收模块建议优先接 3.3V 供电；如果你的模块只能 5V 供电，OUT 到 PA0 前加分压或电平转换。

## 当前 OLED 可视化固件

当前工程已经烧录为 FreeRTOS 版“樱桃供应链溯源终端”演示固件。论文里的 STM32H743、SHT31、MH-Z19B、ATECC608A、ESP8266、LoRa、FreeRTOS 架构，在这块 STM32F103C8T6 小板上做了等价裁剪：

| 论文功能 | 本板实现 |
| --- | --- |
| 多源环境采集 | DHT11 显示环境温湿度，DS18B20 显示果品温度 |
| 数据哈希/签名链路 | FNV-1a 生成 32 位演示哈希，在 OLED 上显示批次和 HASH |
| 本地存储 | W25Q32 JEDEC ID 自检，AT24C08 地址 0x50 自检 |
| 通信上报 | ESP8266 通过 USART3 发 AT 探测，JDY-3x 通过 USART1 发送启动提示 |
| 人机交互 | OLED 多页面仪表盘，红外遥控切页/采样/自动轮播，蜂鸣器提示 |

FreeRTOS 任务：

| 任务 | 优先级 | 栈深度 | 功能 |
| --- | --- | --- | --- |
| `IRTask` | 5 | 160 words | 从红外中断队列接收 NEC 按键，切换页面、触发采样、蜂鸣器和自动轮播 |
| `SensorTask` | 4 | 192 words | 周期读取 DHT11、DS18B20，更新质量评分和演示哈希 |
| `UITask` | 3 | 256 words | 250ms 刷新 OLED 多页面可视化界面，处理自动轮播 |
| `SelfTestTask` | 2 | 192 words | 周期检测 W25Q32、AT24C08、ESP8266 和 OLED 状态 |
| `CommTask` | 1 | 160 words | 周期通过 JDY-3x 蓝牙串口发送节点在线提示 |
| `BuzzerTask` | 1 | 96 words | 让 PC13 状态灯 1 秒闪烁，表示 FreeRTOS 调度器正在运行 |

红外接收仍由 PA0/EXTI0 捕获边沿，EXTI0 优先级设为 5，ISR 只解码并用 `xQueueSendFromISR()` 投递队列，实际动作在 `IRTask` 中执行。SVC、PendSV、SysTick 已接入 FreeRTOS 的 Cortex-M3 端口；SysTick 同时调用 `HAL_IncTick()`，所以 HAL 延时和 RTOS tick 都能工作。

验证 FreeRTOS 是否运行：

| 现象 | 含义 |
| --- | --- |
| OLED 正常刷新 | `UITask` 正在运行 |
| PC13 约 1 秒翻转一次 | `BuzzerTask` 正在运行，调度器已经启动 |
| 遥控器能切页 | EXTI0 ISR 到 `IRTask` 队列链路正常 |
| 传感器数值周期变化或显示 WAIT/ERR | `SensorTask` 正在周期采样 |

OLED 页面：

| 页面 | 内容 |
| --- | --- |
| P1 `CHERRY TRACE` | 温湿度、果温、质量评分、进度条 |
| P2 `BLOCK CHAIN` | 批次、样本号、演示 HASH、采集到上链流程 |
| P3 `STORAGE` | W25Q32、AT24C08 状态和 Flash ID |
| P4 `COMMS` | ESP8266、JDY-3x、红外键值和动作 |
| P5 `TRACE FLOW` | 传感器、哈希、网络、链端流程可视化 |
| P6 `SELF TEST` | OLED、IR、DHT11、DS18B20、Flash、EEPROM 自检 |

红外遥控默认兼容配套资料里的 NEC 21 键遥控：

| 按键 | 功能 |
| --- | --- |
| 1-6 | 直接跳到 P1-P6 |
| 左/下 | 上一页 |
| 右/上 | 下一页 |
| OK | 立即采样并短响蜂鸣器 |
| `*` | 蜂鸣器响一下 |
| `#` | 开关自动轮播 |

如果你的遥控器键值不一样，先切到 `COMMS` 页面，按键后看 `IR KEY 0X..` 显示的十六进制键值，再在 `Core/Src/trace_app.c` 的 `handle_key()` 里补映射。

## 备用引脚

PB3、PB4、PA15、PB2、PB5、PB8、PB9、PC13-PC15 目前未分配。PC13 可接板载 LED 或状态灯，但驱动能力较弱，不适合直接带蜂鸣器等负载。
