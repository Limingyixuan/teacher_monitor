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

## 3. 邮件提醒

以 QQ 邮箱为例，先在邮箱设置中开启 SMTP 并取得“授权码”（不是登录密码），然后重新打开 PowerShell：

```powershell
setx SMTP_USER "你的QQ邮箱@qq.com"
setx SMTP_PASS "你的SMTP授权码"
setx MAIL_TO "接收提醒的邮箱@qq.com"
```

默认使用 `smtp.qq.com:465`。其他邮箱可另设 `SMTP_HOST` 和 `SMTP_PORT`。

## 4. 设置每天 8:30 自动运行

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
