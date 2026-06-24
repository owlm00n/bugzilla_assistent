// ============================================================
// Level 1: 快速调试 - 添加关键日志点
// 适用场景: 快速定位问题点, 5分钟可用
// 说明: 只添加pr_debug/pr_info/pr_err, 不改变程序逻辑
// ============================================================

// --- 模块: tcpm (PD协议状态机) ---

// 在 tcpm_pd_rx_msg() 中添加 PD消息接收日志
static void tcpm_pd_debug_rx(const struct tcpm_port *port,
			     const struct pd_msg *msg)
{
	const char *msg_name = pd_msg_name(msg->header);
	u16 snk_caps = pd_pdo_type(msg->header);

	pr_info("[PD-DBG] RX %s (header=0x%04x) VBUS=%dmV\n",
		msg_name, msg->header,
		tcpm_get_vbus_voltage(port));
}

// 在 tcpm_src_state_machine() 中添加状态转换日志
static void tcpm_src_state_debug(struct tcpm_port *port,
				 enum tcpm_state next)
{
	pr_debug("[PD-DBG-_SRC] State: %s -> %s\n",
		 tcpm_state_name(port->state),
		 tcpm_state_name(next));
}

// 在 pd_protocol/src/negotiate.c 的 pd_negotiate_pdo() 中
static int pd_negotiate_pdo_debug(struct pd_source *src, u32 requested_mv,
				  u32 requested_ma)
{
	int ret;

	pr_info("[PD-DBG] Negotiate: request %dmV/%dma\n",
		requested_mv, requested_ma);

	ret = pd_send_request(src, requested_mv, requested_ma);
	if (ret) {
		pr_err("[PD-DBG] REQUEST failed: ret=%d\n", ret);
		return ret;
	}

	/* 检查ACCEPT vs REJECT */
	ret = pd_wait_frs(src);
	if (ret < 0) {
		pr_err("[PD-DBG] No ACCEPT, got error %d\n", ret);
	} else if (ret == 0) {
		pr_warn("[PD-DBG] Got REJECT for %dmV/%dma\n",
			requested_mv, requested_ma);
	} else {
		pr_info("[PD-DBG] ACCEPTED, waiting PS_RDY\n");
	}

	return ret;
}

// 在 vbus_control.c 的电压读取函数中添加
static int pd_vbus_ctrl_debug_read(struct tcpm_port *port)
{
	int raw_voltage = pd_hw_read_vbus(port);
	int expected_voltage = port->requested_mv;
	int deviation = abs(raw_voltage - expected_voltage);

	pr_info("[PD-DBG-VBUS] raw=%dmV expected=%dmV deviation=%dmV\n",
		raw_voltage, expected_voltage, deviation);

	if (deviation > VBUS_TOLERANCE_MV) {
		pr_warn("[PD-DBG-VBUS] VBUS deviation exceeded! tolerance=%d\n",
			VBUS_TOLERANCE_MV);
	}

	return raw_voltage;
}

// --- 模块: usb_core (USB枚举) ---

// 在 usb_enum.c 的描述符读取函数中添加
static int usb_enum_descriptor_debug(struct usb_device *udev, int depth)
{
	struct usb_device_descriptor *desc = &udev->descriptor;
	int ret;

	pr_info("[USB-DBG] Depth=%d VID=0x%04x PID=0x%04x bcdUSB=0x%04x\n",
		depth, desc->idVendor, desc->idProduct, desc->bcdUSB);
	pr_info("[USB-DBG] bDeviceClass=%d bDeviceSubClass=%d bMaxPacketSize0=%d\n",
		desc->bDeviceClass, desc->bDeviceSubClass,
		desc->bMaxPacketSize0);

	ret = usb_get_descriptor(udev, USB_DT_DEVICE, 0,
				(u8 *)desc, sizeof(*desc));
	if (ret < 0) {
		pr_err("[USB-DBG] Device Descriptor read FAILED: ret=%d\n",
			ret);
		return ret;
	}

	pr_debug("[USB-DBG] Device Descriptor OK: %s\n",
		 usb_device_speed_name(udev->speed));

	return ret;
}

// === 使用说明 ===
// 1. 将上述函数添加到对应模块的源文件中
// 2. 编译内核模块
// 3. 重现问题场景
// 4. dmesg | grep "\[PD-DBG\]" 或 dmesg | grep "\[USB-DBG\]"
// 5. 根据日志输出定位问题点
// 6. 问题定位后可删除或添加 #undef DBG_ENABLE 关闭日志

// === 回归测试 ===
// - 正常PD协商场景: 确认日志完整输出协商流程
// - VBUS异常场景: 确认偏差告警正常触发
// - USB枚举场景: 确认描述符读取日志正常
