# 典型故障案例库

## 案例1: PD协商失败 - VBUS电压未达到预期

### Bug ID
BUG-20261

### 故障描述
使用支持PD 3.0的充电器连接设备时，PD协商成功但在REQUEST请求9V/3A后，VBUS电压一直停留在5V。log显示SRC_CAP已发送包含9V的PDO，但REQUEST之后没有收到ACCEPT。

### Log片段
```
[10:12:01.100] [pd_protocol] SRC_CAP: 3 PDOs
[10:12:01.101] [pd_protocol]   PDO[0]: Fixed 5V/3A
[10:12:01.102] [pd_protocol]   PDO[1]: Fixed 9V/3A
[10:12:01.103] [pd_protocol]   PDO[2]: Fixed 20V/3A
[10:12:01.500] [pd_protocol] REQUEST: PDO[1] 9V/3000mA
[10:12:05.500] [pd_protocol] REQUEST timeout after 4000ms
[10:12:05.501] [pd_protocol] Retrying REQUEST (1/3)
[10:12:09.501] [pd_protocol] REQUEST timeout after 4000ms
[10:12:09.502] [pd_protocol] Retrying REQUEST (2/3)
[10:12:13.502] [pd_protocol] REQUEST timeout after 4000ms
[10:12:13.503] [pd_protocol] Max retries reached, initiating HARD_RESET
```

### 分析过程
1. SRC_CAP包含9V PDO，说明充电器支持9V
2. REQUEST无响应，超时4秒
3. 重试2次后仍无响应
4. 触发Hard Reset

### 根因
对端充电器虽然在其SRC_CAP中声明了9V PDO，但实际内部电源路径控制器有故障，无法提供9V输出。这是充电器的兼容性/固件bug。

### 解决方案
1. **临时方案**: 降级到PDO[0]的5V
2. **根本方案**: 联系充电器厂商更新固件
3. **防御性编码**: 在REQUEST后增加VBUS电压验证，如果电压未切换则自动降级

### 相关代码
- tcpm_state_machine.c: `tcpm_src_request()`
- pd_protocol/negotiate.c: `pd_negotiate_pdo()`
- vbus_control.c: `pd_vbus_verify_voltage()`

### 经验教训
PD协商需要双方配合，SRC_CAP声明的能力不一定都能正常工作。实现中应该增加电压验证和自动降级机制。

---

## 案例2: USB3.1枚举失败 - Config Descriptor读取超时

### Bug ID
BUG-20262

### 故障描述
USB3.1设备插入后，在读取Config Descriptor阶段超时。超时时间配置为500ms，但实际设备需要800ms才能响应。

### Log片段
```
[10:15:01.000] [usb_core] USB device connected: VID=0x0BDA, PID=0x8153
[10:15:01.100] [usb_core] SET_ADDRESS: addr=1
[10:15:01.200] [usb_core] GET_DESCRIPTOR(Device): OK (18 bytes)
[10:15:01.500] [usb_core] GET_DESCRIPTOR(Config): timeout after 500ms
[10:15:01.501] [usb_core] Retrying GET_DESCRIPTOR(Config) (1/3)
[10:15:02.001] [usb_core] GET_DESCRIPTOR(Config): timeout after 500ms
[10:15:02.002] [usb_core] Retrying GET_DESCRIPTOR(Config) (2/3)
[10:15:02.502] [usb_core] GET_DESCRIPTOR(Config): timeout after 500ms
[10:15:02.503] [usb_core] Max retries, enumeration FAILED
```

### 分析过程
1. Device Descriptor读取成功，说明物理连接正常
2. Config Descriptor读取失败，超时500ms
3. 重试2次后枚举彻底失败
4. 实际测量发现设备需要800ms响应

### 根因
USB设备在高速模式下处理Config Descriptor请求较慢，特别是Realtek RTL8153(USB3.1到Ethernet的桥接芯片)。USB控制器超时配置500ms不够。

### 解决方案
1. **增大超时**: 将descriptor读取超时从500ms增加到1000ms
2. **驱动补丁**: 在usb_core中添加针对已知慢速设备的特殊处理
3. **设备固件**: 联系Realtek更新RTL8153固件

### 相关代码
- usb/core/descriptor.c: `usb_get_descriptor()`
- usb/core/message.c: `usb_control_msg()`
- usb/core/hub.c: `hub_port_init()`

### 经验教训
USB设备的响应时间因厂商和型号而异。超时时间应该设置得足够宽松，并且对于已知慢速设备应该有特殊处理。

---

## 案例3: PD PR_SWAP死锁

### Bug ID
BUG-20263

### 故障描述
在Power Role Swap (PR_SWAP)协商时，源端和宿端同时发送REQUEST消息，导致死锁。PD Line状态机反复进入Hard Reset循环。

### Log片段
```
[14:30:01.000] [pd_protocol] PR_SWAP initiated by host
[14:30:01.100] [pd_protocol] ← PR_SWAP (Request power role swap)
[14:30:01.200] [pd_protocol] → ACCEPT
[14:30:01.300] [pd_protocol] State: Negotiate Capabilities
[14:30:01.500] [pd_protocol] → REQUEST (new source requesting power)
[14:30:01.600] [pd_protocol] ← REQUEST (original source also requesting)
[14:30:01.700] [pd_protocol] ERROR: Both sides sending REQUEST
[14:30:01.800] [pd_protocol] → HARD_RESET
[14:30:02.800] [pd_protocol] → HARD_RESET (repeated)
```

### 根因
PR_SWAP后双方状态机同步不同步，导致同时认为自己应该是source并发送REQUEST。需要在PR_SWAP后增加状态机同步延迟。

### 解决方案
在PR_SWAP ACCEPT后增加10ms同步延迟，确保双方状态机切换到新角色后再发送REQUEST。

---

## 案例4: PDO电压值跳变

### Bug ID
BUG-20265

### 故障描述
PD协商成功后VBUS电压在9.1V~9.5V之间跳变。分析发现SNK_CAP中Fixed PDO的电压范围设置过宽，导致 Negotiation 结果不确定。

### 解决方案
限制SNK_CAP的PDO范围，使用精确的电压值而非范围。
