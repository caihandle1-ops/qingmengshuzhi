# 电脑端动效验收记录

这个工具建立验收清单，不启动浏览器，也不自动宣布视觉通过。AppTest 与 Node 回归只能证明它们实际执行的逻辑，不能替代页面截图、真实操作或帧率测量。

从项目根目录执行：

```powershell
python tools/desktop_motion_review.py init ../desktop-motion-review.json
python tools/desktop_motion_review.py check ../desktop-motion-review.json
```

`init` 默认读取 `RELEASE.json` 版本，也可传 `--version`。文件存在时拒绝覆盖，避免抹掉既有观察。`check` 返回码：`0` 表示记录完整且全部人工/官方工具观察通过；`1` 表示记录有误；`2` 表示格式完整但验收仍未完成。格式通过不能证明观察真实。

清单包含 52 项：两个 CSS 像素尺寸（1366×768、1920×1080），三种模式（展示、研究、系统减弱动效），六个页面，以及各尺寸下的八组交互场景。系统减弱动效必须在系统/浏览器实际开启，不能只把应用设为研究模式。记录浏览器缩放与实际 viewport；不能得到指定尺寸时，该项保持 pending 并在环境备注写明。

使用官方 `cua_repl`、官方 computer-use，或由人直接操作浏览器。工具初始化失败时，将错误记入顶层 `browser_attempts`，页面项保持 pending。不要用 shell Playwright、CDP 或自写浏览器连接代替官方工具。

先填写 `environment` 中的验收人、浏览器与设备。观察完对应项后，保留原有 case 元数据，填写 `status` 为 `passed`、`failed` 或 `blocked`，并填写：

```json
{
  "method": "human-browser",
  "observed_at": "2026-10-09T15:00:00+08:00",
  "notes": "填写实际执行步骤、观察结果及差异，不能照抄预期。",
  "evidence": ["填写实际截图/录屏绝对路径，或官方工具调用记录编号"]
}
```

method 可选 `human-browser`、`official-cua`、`official-computer-use`。时间必须带时区。不要把上例原样粘贴为真实验收。任何失败都应保留记录并在修复后重新观察。

帧率项需要用浏览器性能面板等真实采样方式对六页分别采样至少 5 秒，在 observation 的 `performance` 数组中各写一行 `page`、`duration_seconds`、`average_fps`、`p95_frame_ms`，同时在 notes 说明采样方式。没有测量则保持 pending；不要填估计数值，不要把模拟 RAF 测试当作真实帧率。

可用的只读运行状态接口用于辅助解释暂停与清理，不能证明视觉观感：

- Hero iframe：`window.__qmImmersiveHero.getState()`。关注 playback、showTime、act、currentPose 与 quality。
- 主页面：`window.__qmStudioMotion.getFeatureState()`。关注每个 scene 的 phase、animations、connected、visible 与 visit。

状态读取也必须通过官方工具允许的浏览器接口或人工 DevTools。接口名称仅作为验收提示，不要求绕过工具限制。遇到未提供该接口的旧版本，应记录版本不匹配后停止该项。
