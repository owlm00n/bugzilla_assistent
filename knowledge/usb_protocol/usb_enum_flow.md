# USB 枚举流程知识

## 1. USB 枚举阶段

### 1.1 完整枚举流程
```
Connect → USB Reset → Address Assignment → Device Descriptor Read
  → Config Descriptor Read → Interface Descriptor Read → Endpoint Descriptor Read
  → String Descriptor Read (optional) → Configuration → Ready
```

### 1.2 各阶段详解

#### Connect (连接)
- USB Host 检测到 D+/D- 线路变化
- Full-Speed: D+ 上拉
- Low-Speed: D- 上拉
- High-Speed: 通过 Configurable PHY 检测

#### USB Reset (复位)
- Host 发送 20ms 的 PRST (Port Reset)
- Device 在 10-100ms 内完成恢复
- 速率检测: PRDY12(高速), PRDYSNGL(全速)

#### Address Assignment (地址分配)
- Host 发送 SET_ADDRESS 请求
- Device 在 8ms 内响应 ACK
- Device 获得唯一 7-bit 地址 (0-127)
- 地址 0 用于默认端点

#### Device Descriptor Read (设备描述符读取)
- GET_DESCRIPTOR (Device) on EP0
- 描述符长度: 18 bytes
- 关键字段:
  - bLength: 18
  - bDescriptorType: 1 (Device)
  - bcdUSB: 0x0200/0x0300 (USB 2.0/3.0)
  - bDeviceClass/SubClass/Protocol
  - bMaxPacketSize0: 8/16/32/64
  - idVendor / idProduct
  - bNumConfigurations

#### Config Descriptor Read (配置描述符读取)
- GET_DESCRIPTOR (Config) on EP0
- 描述符长度: 可变
- 关键字段:
  - wTotalLength: 总长度
  - bNumInterfaces: 接口数
  - bConfigurationValue
  - MaxPower: 所需电流 (2mA units)

#### Interface Descriptor Read (接口描述符读取)
- GET_DESCRIPTOR (Interface) on EP0
- 关键字段:
  - bInterfaceNumber
  - bAlternateSetting
  - bNumEndpoints
  - bInterfaceClass: USB/Comm/HID/Video/Vendor
  - bInterfaceSubClass / bInterfaceProtocol

#### Endpoint Descriptor Read (端点描述符读取)
- GET_DESCRIPTOR (Endpoint) on EP0
- 关键字段:
  - wMaxPacketSize: 最大数据包大小
  - bInterval: 轮询间隔

#### String Descriptor Read (字符串描述符读取, 可选)
- GET_DESCRIPTOR (String) on EP0
- 包含: 语言ID, 厂商名, 产品名, 序列号

#### Configuration (配置)
- SET_CONFIGURATION 请求
- 激活配置, 端点可用
- Device Ready

## 2. USB 描述符结构

### Device Descriptor (18 bytes)
```c
struct usb_device_descriptor {
    u8  bLength;            // 18
    u8  bDescriptorType;    // 1
    u16 bcdUSB;             // USB版本
    u8  bDeviceClass;       // 设备类
    u8  bDeviceSubClass;    // 设备子类
    u8  bDeviceProtocol;    // 设备协议
    u8  bMaxPacketSize0;    // EP0最大包大小
    u16 idVendor;           // 厂商ID
    u16 idProduct;          // 产品ID
    u16 bcdDevice;          // 设备版本
    u8  iManufacturer;      // 厂商字符串索引
    u8  iProduct;           // 产品字符串索引
    u8  iSerialNumber;      // 序列号字符串索引
    u8  bNumConfigurations; // 配置数
};
```

### Config Descriptor (10+n bytes)
```c
struct usb_config_descriptor {
    u8  bLength;            // 10
    u8  bDescriptorType;    // 2
    u16 wTotalLength;       // 总长度
    u8  bNumInterfaces;     // 接口数
    u8  bConfigurationValue;
    u8  iConfiguration;     // 配置字符串索引
    u8  bmAttributes;       // 属性 (bus/self powered)
    u8  MaxPower;           // 最大电流 (2mA units)
};
```

### Interface Descriptor (9 bytes)
```c
struct usb_interface_descriptor {
    u8  bLength;            // 9
    u8  bDescriptorType;    // 4
    u8  bInterfaceNumber;
    u8  bAlternateSetting;
    u8  bNumEndpoints;
    u8  bInterfaceClass;
    u8  bInterfaceSubClass;
    u8  bInterfaceProtocol;
    u8  iInterface;         // 接口字符串索引
};
```

### Endpoint Descriptor (7 bytes)
```c
struct usb_endpoint_descriptor {
    u8  bLength;            // 7
    u8  bDescriptorType;    // 5
    u8  bEndpointAddress;   // 端点地址和方向
    u8  bmAttributes;       // 传输类型 (ctrl/iso/bulk/int)
    u16 wMaxPacketSize;     // 最大包大小
    u8  bInterval;          // 轮询间隔
};
```

## 3. USB 传输类型

| 类型 | bmAttributes | 特点 | 适用场景 |
|------|-------------|------|---------|
| Control | 0 | 可靠, 双向 | 配置/控制 |
| Isochronous | 1 | 实时, 不保证 | 音频/视频 |
| Bulk | 2 | 可靠, 最大带宽 | 打印机/存储 |
| Interrupt | 3 | 定时轮询 | 键盘/鼠标/HID |

## 4. USB 速率

| 速率 | 带宽 | 线缆 | 连接器 | 检测方式 |
|------|------|------|--------|---------|
| Low-Speed | 1.5 Mbps | 屏蔽双绞 | A/B/Mini | D- 上拉 |
| Full-Speed | 12 Mbps | 屏蔽双绞 | A/B/Mini/Micro | D+ 上拉 |
| High-Speed | 480 Mbps | 屏蔽双绞 | A/B/Mini/Micro | Configurable PHY |
| SuperSpeed | 5 Gbps | 4对差分线 | USB-C | CC1/CC2 + SS Tx/Rx |
| SuperSpeed+ | 10/20 Gbps | 屏蔽双绞 | USB-C | USB PD + SS |

## 5. USB 常见故障

| 故障 | 症状 | 可能原因 | 排查方向 |
|------|------|---------|---------|
| 枚举失败 | Device not recognized | 供电不足 | 检查 Hub 供电 |
| Descriptor timeout | 描述符读取超时 | 线缆过长/质量差 | 缩短线缆/换质量好的 |
| 反复重置 | Device reconnect loop | 驱动冲突/USB 3兼容 | 换 USB 2.0 端口 |
| 速度降级 | HS → FS | 线缆不支持 HS | 检查线缆 E-Marker |
| 间歇断开 | Intermittent disconnect | 端口松动/供电不稳 | 检查物理连接 |
| 描述符异常 | 描述符校验失败 | 固件 bug | 检查设备固件 |
