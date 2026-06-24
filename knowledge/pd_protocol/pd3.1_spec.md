# PD 3.1 协议关键规范

## 1. PD 消息类型

### 1.1 标准消息 (Standard Messages)

| 消息名称 | Header | 方向 | 描述 |
|---------|--------|------|------|
| SOF | 0x0000 | - | Start of Frame |
| EOF | 0x0003 | - | End of Frame |
| HARD_RESET | 0x0004 | TX/RX | 硬复位 |
| PS_RDY | 0x0005 | TX/RX | 电源已就绪 |
| GET_SRC_CAPABILITIES | 0x0006 | RX→TX | 请求源端能力 |
| SRC_CAPABILITIES | 0x0007 | TX | 源端能力列表 |
| GET_SNK_CAPABILITIES | 0x0008 | TX→RX | 请求宿端能力 |
| SNK_CAPABILITIES | 0x0009 | RX | 宿端能力列表 |
| REQUEST | 0x000A | TX→RX | 功率请求 |
| ACCEPT | 0x000B | RX→TX | 接受请求 |
| REJECT | 0x000C | RX→TX | 拒绝请求 |
| PING | 0x000D | TX→RX | Ping信号 |
| WAIT | 0x000E | RX→TX | 等待 |
| PS_REQUEST | 0x000F | RX→TX | 电源切换请求 |
| GOTO_MIN | 0x0010 | RX→TX | 回到最小值 |
| BIST | 0x0014 | TX | BIST测试 |
| SRC_CAPABILITIES_EXT | 0x0015 | TX | 扩展源端能力 |
| BATT_CAPABILITIES | 0x0016 | TX | 电池能力 |
| ALERT | 0x0017 | RX→TX | 告警 |
| GET_COUNTRY_CAPABILITIES | 0x0018 | RX→TX | 获取国家能力 |
| ENTER_USB | 0x0019 | RX→TX | 进入USB模式 |
| ATTENTION | 0x001A | RX→TX | 注意信号 |
| DRIVER_CAPABILITIES | 0x001B | TX→RX | 驱动器能力 |
| POWER_RESET | 0x001C | RX→TX | 电源复位 |
| LOG_DISCONNECT | 0x001D | RX→TX | 断开日志 |
| DR_SWAP | 0x001E | TX→RX | 数据角色交换 |
| soft_RESET | 0x001F | TX→RX | 软复位 |

### 1.2 供应商消息 (Supplier Messages)

| 消息名称 | Header | 方向 | 描述 |
|---------|--------|------|------|
| VCONN_SWAP | 0x0081 | TX→RX | VCONN交换 |
| PR_SWAP | 0x0082 | TX→RX | 功率角色交换 |
| GET_SRC_CAPABILITIES_EXT | 0x0083 | RX→TX | 扩展源端能力请求 |
| GET_BATT_CAPABILITIES | 0x0084 | RX→TX | 电池能力请求 |
| GET_COUNTRY_CAP | 0x0085 | RX→TX | 国家能力请求 |
| HOST_CAP | 0x0086 | TX→RX | 主机能力 |
| STARTUP | 0x0087 | TX→RX | 启动 |
| BIST_DATA | 0x0088 | RX | BIST数据 |
| GET_DRIVER_CAP | 0x0089 | RX→TX | 驱动器能力请求 |
| SET_SETTINGS | 0x008A | TX→RX | 设置参数 |
| GET_SETTINGS | 0x008B | RX→TX | 获取参数 |

## 2. PD Message Header (16-bit)

```
Bits [15]: Extended (0=Standard, 1=Extended)
Bits [14:12]: Number of Data Objects (0-7)
Bits [11:9]: Message ID (0-7, rolling counter)
Bits [8]: Port Power Role (0=Sink, 1=Source)
Bits [7:6]: Specification Revision (00=Rev1.0, 01=Rev2.0, 10=Rev3.0, 11=Reserved)
Bits [5]: Port Data Role (0=UFP/Device, 1=DFP/Host)
Bits [4]: Reserved (0)
Bits [3:0]: Message Type (see message type table)
```

### Header 解码示例

| Header Hex | Binary | Extended | #DO | MsgID | Power Role | Spec Rev | Data Role | Msg Type | 含义 |
|-----------|--------|----------|-----|-------|------------|----------|-----------|----------|------|
| 0x61a1 | 0110 0001 1010 0001 | 0 | 6 | 1 | Source(1) | Rev3.0(10) | UFP(0) | 0x1=SRC_CAP | SRC_CAP, 6 PDOs, Rev3.0 |
| 0x1082 | 0001 0000 1000 0010 | 0 | 1 | 0 | Sink(0) | Rev3.0(10) | UFP(0) | 0x2=REQUEST | REQUEST, 1 PDO, Rev3.0 |
| 0x03a3 | 0000 0011 1010 0011 | 0 | 0 | 3 | Source(1) | Rev3.0(10) | UFP(0) | 0x3=ACCEPT | ACCEPT, Rev3.0 |
| 0x05a6 | 0000 0101 1010 0110 | 0 | 0 | 5 | Source(1) | Rev3.0(10) | UFP(0) | 0x6=PS_RDY | PS_RDY, Rev3.0 |
| 0x1282 | 0001 0010 1000 0010 | 0 | 1 | 2 | Sink(0) | Rev3.0(10) | UFP(0) | 0x2=REQUEST | REQUEST(PPS), Rev3.0 |

## 3. RDO (Request Data Object, 32-bit)

### 3.1 Fixed RDO (Object Position != 0)
```
Bits [31:28]: Object Position (1-7)
Bits [27]: Reserved (0)
Bits [26]: Capability Mismatch (0=No, 1=Yes)
Bits [25]: USB Communications Capable (0=No, 1=Yes)
Bits [24]: No USB Suspend (0=Allow, 1=No Suspend)
Bits [23]: Unconstrained Power (0=No, 1=Yes)
Bits [22:20]: Reserved (0)
Bits [19:10]: Operating Current (10mA units)
Bits [9:0]: Max/Min Operating Current (10mA units)
```

### 3.2 PPS RDO (Object Position = APDO index)
```
Bits [31:28]: Object Position (APDO index)
Bits [27]: Reserved (0)
Bits [26]: Capability Mismatch (0=No, 1=Yes)
Bits [25]: USB Communications Capable
Bits [24]: No USB Suspend
Bits [23:20]: Reserved (0)
Bits [19:10]: Operating Current (50mA units)
Bits [9:0]: Output Voltage (20mV units)
```

### RDO 解码示例

| RDO Hex | 类型 | Obj Pos | Op Current | Output Voltage | 含义 |
|---------|------|---------|------------|----------------|------|
| 0x0b12c | Fixed | 0 | 3000mA | — | Request PDO 0: 5V/3A |
| 0x1304 | Fixed | 0 | 3000mA | — | (同上, data[1]) |
| 0x2d12c | PPS | 2 | 3000mA | 7960mV | Request APDO 2: 7.96V/3A |

## 4. PDO (Power Data Object)

### 2.1 Fixed PDO
```
Bits [31:28]: Not Used (0)
Bits [27:18]: Voltage (mV) - Offset 5000
Bits [17:16]: Max Current (10mA units)
Bits [15:13]: Unconstrained Power (0=No, 1=Yes)
Bits [12:11]: USB Suspend Exit (00=Default, 01=USB3, 10=USB2, 11=HS)
Bits [10:9]: Dual-Role Data (00=No DRP, 01=DRP in Source, 10=DRP in Sink)
Bits [8]: AU (Augmented USB)
Bits [7:4]: Reserved (0)
Bit [3]: USB Comm (0=Not supported, 1=Supported)
Bit [2]: Unchunksed Extended Message Supported
Bits [1:0]: Reserved (0)
```

### 2.2 Battery PDO
```
Bits [31:28]: Maximum Allowed Power (mW)
Bits [27:18]: Minimum Voltage (mV) - Offset 5000
Bits [17:9]: Maximum Current (10mA units)
Bits [8:0]: Minimum Current (10mA units)
```

### 2.3 Variable PDO
```
Bits [31:28]: Operating Power (mW)
Bits [27:18]: Minimum Voltage (mV) - Offset 5000
Bits [17:9]: Maximum Current (10mA units)
Bits [8:0]: Minimum Current (10mA units)
```

### 2.4 APDO (Augmented PDO)
```
Bits [31:28]: Max Power (mW)
Bits [27:18]: Min Voltage (mV) - Offset 5000
Bits [17:0]: Max Current (mA units)
```

APDO Types:
- Type 0: E-Marker Cable
- Type 1: Programmable Power Supply (PPS)
- Type 2: Battery
- Type 3: Dual-Port Copper
- Type 4: Dual-Port Opto

## 3. PD 状态机

### 3.1 Source State Machine
```
Default → Startup → Source.Identity → Source.Wait Caps
  → Source.Sink Cap'd → Source.Request → Source.On
  → Source.Soft Reset (error path)
  → Source.Hard Reset (error path)
  → Source.Disable (shutdown)
```

### 3.2 Sink State Machine
```
Default → Startup → Sink.Identity → Sink.Wait Caps
  → Sink.Capable → Sink.Request → Sink.Switch Source Cap
  → Sink.On → Sink.Standby
  → Sink.Soft Reset (error path)
  → Sink.Hard Reset (error path)
  → Sink.Disable (shutdown)
```

## 4. PD 时序要求

| 参数 | 最小值 | 典型值 | 最大值 | 单位 |
|------|--------|--------|--------|------|
| tACST | - | - | 65 | μs (Command ACK) |
| tCCDebounce | 200 | 400 | 600 | ms (CC Debounce) |
| tCDGDischarge | - | - | 3 | s (CC Discharge) |
| tDRPHold | 40 | - | - | μs (DRP Role Swap) |
| tHardReset | 100 | - | 500 | ms (Hard Reset) |
| tPSOn | 400 | - | 800 | ms (Power On after PS_RDY) |
| tPSChange | 200 | - | 750 | ms (PS Change) |
| tReact | - | - | 100 | ms (Response to Request) |
| tSrcTransition | - | - | 80 | ms (Source Transition) |
| tSinkTransition | - | - | 80 | ms (Sink Transition) |

## 5. PD 常见故障模式

| 故障 | 症状 | 可能原因 | 排查方向 |
|------|------|---------|---------|
| PDO不匹配 | REJECT after REQUEST | 电压/电流超出范围 | 检查SRC_CAP和REQUEST PDO |
| VBUS偏差 | 预期9V实际5.2V | 线路压降/负载调整 | 检查线缆质量和负载 |
| Hard Reset循环 | 反复HARD_RESET | 持续故障条件 | 检查短路/过流 |
| PR_SWAP死锁 | 双方互相发送REQUEST | 时序竞争 | 检查状态机同步 |
| PR_SWAP死锁 | 双方互相发送REQUEST | 时序竞争 | 检查状态机同步 |
| 协商超时 | PS_RDY未收到 | 对端无响应 | 检查PD Line和时序 |
