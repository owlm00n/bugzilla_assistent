// ============================================================
// Level 3: 修复建议 - 生产级补丁代码
// 适用场景: 问题定位后的修复, 包含边界条件、性能和安全分析
// 说明: 可直接提交的补丁级代码 + 回归测试方案
// ============================================================

// --- 修复场景: PD协商时VBUS电压未达到预期值 ---
// Bug描述: 在PD SRC_CAP -> REQUEST -> NEGOTIATE流程中, 请求9V/3A
// 但VBUS停留在5V, 可能是电源路径控制器未正确切换或PDO能力不匹配

// --- 模块: tcpm/vbus.c (VBUS电压稳定检测与自动恢复) ---

/* VBUS电压稳定阈值 (mV) */
#define VBUS_STABLE_TOLERANCE	200
#define VBUS_STABLE_DELAY_MS	100

/* 新增: VBUS稳定检查与自动恢复机制 */
static int pd_vbus_stable_check(struct tcpm_port *port,
				enum tcpm_state state)
{
	int vbus_uv = tcpm_get_vbus_uvoltage(port);
	int expected_mv = tcpm_get_expected_voltage(port);
	int expected_uv = expected_mv * 1000;
	int deviation_uv = abs(vbus_uv - expected_uv);

	/* 正常情况: VBUS在容忍范围内 */
	if (deviation_uv <= VBUS_STABLE_TOLERANCE * 1000)
		return 0;

	/* 特殊情况: PR_SWAP期间不报错 */
	if (state == tcpm_pr_swap)
		return 0;

	/* 异常情况: VBUS偏差过大 */
	pr_warn("[PD-FIX] VBUS unstable: expected=%dmV actual=%dmV dev=%dmV\n",
		expected_mv, vbus_uv / 1000, deviation_uv / 1000);

	/* 重试计数: 避免瞬时波动误报 */
	port->vbus_unstable_cnt++;
	if (port->vbus_unstable_cnt < 3) {
		pr_warn("[PD-FIX] VBUS unstable, retry %d/3\n",
			port->vbus_unstable_cnt);
		/* 启动延迟恢复定时器 */
		mod_timer(&port->vbus_recovery_timer,
			  jiffies + msecs_to_jiffies(VBUS_STABLE_DELAY_MS));
		return -EAGAIN; /* 触发重试 */
	}

	/* 超过重试次数, 触发Hard Reset */
	port->vbus_unstable_cnt = 0;
	pr_err("[PD-FIX] VBUS still unstable after 3 retries, triggering Hard Reset\n");
	tcpm_initiate_hard_reset(port, 0);

	return -EIO;
}

// --- 修复场景2: PD协商超时增强处理 ---

/* 新增: 增强型PD协商超时处理 */
static int pd_enhanced_negotiate(struct tcpm_port *port, u32 mv, u32 ma)
{
	unsigned long timeout = jiffies + msecs_to_jiffies(PD_NEGO_TIMEOUT_MS);
	int ret;
	int attempt = 0;
	const int max_attempts = 2;

	while (time_before(jiffies, timeout) && attempt < max_attempts) {
		attempt++;

		pr_info("[PD-FIX] Negotiate attempt %d/%d: %dmV %dma\n",
			attempt, max_attempts, mv, ma);

		ret = pd_send_request(port, mv, ma);
		if (ret < 0) {
			pr_warn("[PD-FIX] REQUEST attempt %d failed: %d, retrying...\n",
				attempt, ret);
			msleep(10); /* 短暂延迟后重试 */
			continue;
		}

		/* 等待ACCEPT */
		ret = pd_wait_frs(port, timeout - jiffies);
		if (ret > 0) {
			/* Got ACCEPT, wait PS_RDY */
			ret = pd_wait_psrdy(port, timeout - jiffies);
			if (!ret) {
				pr_info("[PD-FIX] Negotiation succeeded on attempt %d\n",
					attempt);
				return 0;
			}
			pr_warn("[PD-FIX] PS_RDY timeout on attempt %d\n", attempt);
		} else if (ret == 0) {
			pr_warn("[PD-FIX] REJECTED on attempt %d\n", attempt);
			break; /* REJECT不再重试, 进入失败处理 */
		} else {
			pr_warn("[PD-FIX] REQUEST error %d on attempt %d\n",
				ret, attempt);
		}
	}

	if (attempt >= max_attempts) {
		pr_err("[PD-FIX] Negotiation FAILED after %d attempts, PDO mismatch?\n",
			max_attempts);
		/* 建议降级到最低PDO */
		port->nego_strategy = PDO_NEGO_MIN;
	}

	return -ETIMEDOUT;
}

// --- 模块: usb/core/endpoint.c (USB端点配置增强) ---

/* 修复: 端点配置失败时的重试机制 */
static int usb_enhanced_set_config(struct usb_device *udev, int config)
{
	int ret, retries = 3;
	int delay_ms = 50;

	while (retries--) {
		ret = usb_set_configuration(udev, config);
		if (!ret)
			return 0;

		pr_warn("[USB-FIX] set_config(%d) failed: ret=%d, retries left=%d\n",
			config, ret, retries);
		msleep(delay_ms);
		delay_ms *= 2; /* 指数退避 */
	}

	/* 全部重试失败, 尝试reset设备 */
	pr_err("[USB-FIX] set_config(%d) permanently failed, resetting device\n",
		config);
	usb_reset_device(udev);

	return -ENODEV;
}

// --- 模块: i2c/charger.c (I2C充电控制器超时修复) ---

/* 修复: I2C传输超时增强 */
static int charger_i2c_transfer_safe(struct i2c_client *client,
				     struct i2c_msg *msgs, int num)
{
	int ret;
	unsigned long timeout;

	timeout = jiffies + msecs_to_jiffies(I2C_TIMEOUT_MS);
	ret = i2c_transfer(client->adapter, msgs, num);

	if (ret < 0) {
		if (time_after(jiffies, timeout)) {
			pr_err("[CHGR-FIX] I2C timeout: adapter=%d msg=%d ret=%d\n",
				client->adapter->nr, num, ret);
			/* 触发I2C bus recovery */
			i2c_recovery_needed(client->adapter);
		} else {
			pr_warn("[CHGR-FIX] I2C error: ret=%d (not timeout)\n", ret);
		}
	}

	return ret;
}

// ============================================================
// 补丁提交模板
// ============================================================
// Commit message:
//   [PD-FIX] Add VBUS voltage stability check and auto-recovery
//
//   When PD negotiation requests a voltage change, VBUS may not
//   reach the target value due to:
//   1. Power path controller not switching correctly
//   2. PDO capability mismatch between source and sink
//   3. Line drop exceeding tolerance
//
//   This patch adds:
//   - VBUS stable check after state transition
//   - 3-retry mechanism before triggering Hard Reset
//   - Enhanced negotiation timeout with retry strategy
//   - USB endpoint config retry with exponential backoff
//
//   Signed-off-by: Developer <dev@example.com>
//
// ============================================================
// 回归测试方案
// ============================================================
// 1. 正常PD协商: SRC_CAP -> REQUEST -> ACCEPT -> PS_RDY, VBUS正确切换
// 2. PDO不匹配: 请求超出SRC_CAP范围, 应REJECT后降级
// 3. VBUS偏差: 模拟VBUS偏差>200mV, 应3次重试后触发Hard Reset
// 4. 协商超时: 模拟PS_RDY不响应, 应超时重试后降级到最低PDO
// 5. USB枚举失败: 模拟Config Descriptor读取失败, 应3次重试后reset
// 6. I2C偶发失败: 模拟I2C传输错误, 应正常error路径
// 7. 性能测试: 确认debug日志不影响正常时序(Timing budget OK)
