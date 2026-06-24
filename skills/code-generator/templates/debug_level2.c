// ============================================================
// Level 2: 完整诊断 - 条件断点 + 状态收集 + 自动上报
// 适用场景: 系统性排查, 15分钟可用
// 说明: 增加完整的时序追踪和状态机快照
// ============================================================

// --- 模块: tcpm (PD时序追踪) ---

/* 定义追踪缓冲区 */
#define PD_TRACE_ENTRIES 64
static struct pd_trace_entry {
	u64 timestamp_ns;
	enum tcpm_state state;
	u32 vbus_mv;
	u32 current_ma;
	u16 msg_header;
	u8 msg_type;
	u8 event;
	u8 reserved;
} pd_trace[PD_TRACE_ENTRIES];
static atomic_t pd_trace_idx = ATOMIC_INIT(0);
static bool pd_trace_active = false;

static inline void pd_trace_snapshot(struct tcpm_port *port)
{
	struct pd_trace_entry *entry;
	int idx;

	if (!pd_trace_active)
		return;

	idx = atomic_inc_return(&pd_trace_idx) % PD_TRACE_ENTRIES;
	entry = &pd_trace[idx];

	entry->timestamp_ns = ktime_get_ns();
	entry->state = port->state;
	entry->vbus_mv = tcpm_get_vbus_voltage(port);
	entry->current_ma = port->current_limit_ma;
	entry->msg_header = port->last_msg.header;
	entry->msg_type = PD_MSG_TYPE(port->last_msg.header);

	pr_info("[PD-TRACE] idx=%d state=%s VBUS=%dmV I=%dmV type=0x%02x\n",
		idx, tcpm_state_name(entry->state), entry->vbus_mv,
		entry->current_ma, entry->msg_type);
}

/* 在状态转换点调用 */
static void tcpm_set_state(struct tcpm_port *port, enum tcpm_state state,
			   bool logged)
{
	u32 delay_ns;
	u64 last_time;

	last_time = port->trace_last_ns;
	port->trace_last_ns = ktime_get_ns();
	delay_ns = (u32)((port->trace_last_ns - last_time) / 1000); /* us */

	tcpm_fw_entering_state(port, state);
	if (state != port->state) {
		pr_info("[PD-DIAG] %s -> %s (delay=%uus)\n",
			tcpm_state_name(port->state),
			tcpm_state_name(state), delay_ns);
		pd_trace_snapshot(port);
	}
	port->state = state;
	port->in_transaction = false;
}

/* REQUEST发送失败时的完整上下文上报 */
static int pd_diag_request_full(struct tcpm_port *port, u32 mv, u32 ma)
{
	int ret;

	pr_info("[PD-DIAG] === REQUEST Full Context ===\n");
	pr_info("[PD-DIAG]   Request: %dmV %dma\n", mv, ma);
	pr_info("[PD-DIAG]   Current State: %s\n",
		tcpm_state_name(port->state));
	pr_info("[PD-DIAG]   VBUS: %dmV, Current: %dma\n",
		tcpm_get_vbus_voltage(port), port->current_limit_ma);
	pr_info("[PD-DIAG]   PDO Count: %d, Last SRC_CAP: 0x%04x\n",
		port->src_caps.count, port->last_msg.header);

	/* 打印所有PDO能力 */
	if (port->src_caps.data && port->src_caps.count) {
		int i;
		pr_info("[PD-DIAG]   SRC_CAP PDOs:\n");
		for (i = 0; i < port->src_caps.count; i++) {
			u32 pdo = port->src_caps.data[i];
			pr_info("[PD-DIAG]     PDO[%d]: 0x%08x (%s)\n",
				i, pdo, pd_pdo_name(pdo));
		}
	}

	ret = pd_send_request(port, mv, ma);
	if (ret)
		pr_err("[PD-DIAG] REQUEST returned %d\n", ret);
	else
		pr_info("[PD-DIAG] REQUEST sent OK\n");

	return ret;
}

/* 在HARD_RESET时记录完整状态 */
static void pd_diag_hard_reset(struct tcpm_port *port)
{
	pr_info("[PD-DIAG] !!! HARD_RESET triggered !!!\n");
	pr_info("[PD-DIAG]   Previous State: %s\n",
		tcpm_state_name(port->state));
	pr_info("[PD-DIAG]   VBUS: %dmV\n",
		tcpm_get_vbus_voltage(port));
	pr_info("[PD-DIAG]   Error counter: %d\n",
		port->error_cnt);
	pr_info("[PD-DIAG]   Retry counter: %d\n",
		port->retry_cnt);

	/* 输出Trace缓冲区摘要 */
	if (pd_trace_active && atomic_read(&pd_trace_idx)) {
		pr_info("[PD-DIAG] Trace buffer (%d entries):\n",
			atomic_read(&pd_trace_idx));
		int i, idx = atomic_read(&pd_trace_idx) % PD_TRACE_ENTRIES;
		int start = (idx >= PD_TRACE_ENTRIES / 2) ? 0 : idx - PD_TRACE_ENTRIES / 2;
		if (start < 0) start += PD_TRACE_ENTRIES;
		for (i = 0; i < PD_TRACE_ENTRIES / 2; i++) {
			struct pd_trace_entry *e = &pd_trace[(start + i) % PD_TRACE_ENTRIES];
			pr_info("[PD-DIAG]   [%3d] t=%llu us state=%s VBUS=%d\n",
				i, (unsigned long long)(e->timestamp_ns / 1000),
				tcpm_state_name(e->state), e->vbus_mv);
		}
	}
}

// --- 模块: usb_core (枚举诊断) ---

/* USB枚举状态追踪 */
struct usb_enum_diag {
	ktime_t timestamps[USB_ENUM_STAGES];
	int errors[USB_ENUM_STAGES];
	u32 retransmit_count;
	u32 total_timeout;
} __packed;

static struct usb_enum_diag usb_diag_state;

static void usb_diag_enum_stage(enum usb_enum_stage stage, int ret,
				ktime_t start)
{
	u64 elapsed_us = ktime_us_delta(ktime_get(), start);

	usb_diag_state.timestamps[stage] = start;
	if (ret < 0) {
		usb_diag_state.errors[stage] = ret;
		usb_diag_state.retransmit_count++;

		pr_info("[USB-DIAG] STAGE_%d FAILED: ret=%d elapsed=%lluus retransmit#%d\n",
			stage, ret, elapsed_us,
			usb_diag_state.retransmit_count);

		/* 打印当前设备状态 */
		pr_info("[USB-DIAG]   Port status: 0x%08x Hub status: 0x%08x\n",
			port->port_status, port->hub_status);
	} else {
		pr_info("[USB-DIAG] STAGE_%d OK: %lluus\n",
			stage, elapsed_us);
	}
}

// === 使用说明 ===
// 1. 编译时启用: CONFIG_PD_TRACE=y 和 CONFIG_USB_DIAG=y
// 2. 动态控制追踪开关:
//    echo 1 > /sys/kernel/debug/pd_trace/enable
//    echo 0 > /sys/kernel/debug/pd_trace/enable
// 3. 读取追踪数据:
//    dmesg | grep "\[PD-DIAG\]"
//    dmesg | grep "\[USB-DIAG\]"
// 4. 重置追踪:
//    echo reset > /sys/kernel/debug/pd_trace/control

// === 回归测试 ===
// - 正常PD协商: 确认Trace完整记录所有状态转换
// - PD协商失败: 确认错误上下文完整上报
// - USB枚举超时: 确认各阶段耗时统计正确
// - 多次HARD_RESET: 确认Trace缓冲区正确覆盖和输出
