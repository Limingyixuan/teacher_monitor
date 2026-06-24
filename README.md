# 保定初高中事业编教师招聘监控

每天抓取保定市教育局及部分区县政府官方页面，进入公告正文后判断招聘是否属于：

- **明确事业编**：正文出现“纳入/使用/列入事业编制”等强证据；
- **事业单位招聘**：按事业单位公开招聘程序发布，但仍建议核对岗位表；
- **编制性质不确定**：备案制、控制数、员额制等；
- 自动排除民办、代课、合同制、劳务派遣、购买服务、编外等岗位。

## 1. 安装

当前电脑是 Python 3.7，可直接执行：

```powershell
python -m pip install -r requirements.txt
```

## 2. 第一次运行

```powershell
python baoding_teacher_monitor.py
```

第一次运行只建立历史基线，不发送旧公告。若希望立即查看并提醒当前已有公告：

```powershell
python baoding_teacher_monitor.py --notify-existing
```

每次运行都会在 `reports` 目录生成 Markdown 报告，状态保存在 `data/state.json`。

只测试抓取、不发邮件也不更新状态：

```powershell
python baoding_teacher_monitor.py --dry-run --notify-existing
```

## 3. 微信提醒

程序通过 PushPlus 微信公众号发送通知。先使用自己的微信登录
[PushPlus](https://www.pushplus.plus/)，关注其微信服务号并取得个人 token。

在 GitHub 仓库进入：

`Settings → Secrets and variables → Actions → New repository secret`

新增 Secret：

- Name：`PUSHPLUS_TOKEN`
- Secret：你的 PushPlus token

token 与登录 PushPlus 的微信绑定，不要把 token 写进代码、提交到仓库或发送给别人。
程序仅在发现新增或内容更新的公告时推送微信，没有变化时不会发送。

## 4. 设置自动运行

GitHub Actions 默认每 6 小时运行一次，对应北京时间每天
`02:30、08:30、14:30、20:30`。电脑无需开机。

下面是可选的 Windows 本地定时任务设置：

用普通 PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_task.ps1
```

自定义时间：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_task.ps1 -Time "07:30"
```

电脑关机时任务无法运行；再次开机后，任务计划会尽快补跑。

## 5. 增加官方信息源

编辑 `config.json`，按现有格式加入区县政府、人社局或教育局的“公告公示/招聘”栏目页。程序会自动从栏目页找候选链接并读取正文。

政府网站经常改版或启用反爬机制，所以运行报告中的“抓取异常”也值得关注。筛选结果是辅助判断，报名前务必打开原公告和岗位表核实编制、学段、学科及资格条件。

## 6. iPhone PWA

仓库包含 `docs` 目录，GitHub Actions 会把它发布到 GitHub Pages。首次上传后：

1. 打开仓库 `Settings → Pages`；
2. `Build and deployment` 的来源选择 **GitHub Actions**；
3. 在 `Actions` 页面手动运行一次 `Baoding teacher job monitor`；
4. 部署完成后打开工作流显示的 Pages 地址；
5. iPhone 使用 Safari 打开地址，点“分享 → 添加到主屏幕”。

PWA 显示的数据来自 `docs/data/latest_jobs.json`，监控脚本每次运行都会自动更新它。

### PWA 筛选

- 按市直、市区、各县市区以及定州、雄安新区筛选；
- 按“官方来源 / 第三方线索”筛选；
- 可自行勾选排除民办、合同制、代课、劳务派遣、编外、备案制等类型；
- 默认不排除任何类型，抓取程序会尽量保留所有教师招聘线索。

### 来源稳定性

保定市人社局招聘专题使用其网页公开接口抓取；教育局、区县政府和多数聚合站使用网页解析。部分网站可能采用动态加载、旧版 TLS 或反爬策略，因此不能保证每个来源每天都成功。单一来源失败不会中断其他来源，PWA 会显示本次不可用来源数量。第三方信息仅作为线索，报名条件和编制性质以官方原文为准。
