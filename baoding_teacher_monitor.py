#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""保定地区初高中事业编教师招聘监控。兼容 Python 3.7+。"""

import argparse
import hashlib
import json
import os
import re
import smtplib
import ssl
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config.json"
STATE_FILE = ROOT / "data" / "state.json"
REPORT_DIR = ROOT / "reports"
PUBLIC_DATA_FILE = ROOT / "docs" / "data" / "latest_jobs.json"

BAODING_WORDS = [
    "保定", "莲池", "竞秀", "满城", "清苑", "徐水", "涞水", "定兴",
    "唐县", "高阳", "容城", "涞源", "望都", "安新", "易县", "曲阳",
    "蠡县", "顺平", "博野", "雄县", "涿州", "安国", "高碑店",
    "白沟", "阜平", "定州",
]
SCHOOL_WORDS = [
    "教师", "中学", "初中", "高中", "完全中学", "教育事业单位",
    "教体局", "教育局", "学校",
]
RECRUIT_WORDS = [
    "公开招聘", "公开选聘", "专项招聘", "招聘教师", "选聘教师",
    "事业单位招聘", "招聘工作人员", "人才引进", "校园招聘",
]
STRONG_COMPILE_WORDS = [
    "纳入事业编制", "列入事业编制", "使用事业编制", "占用事业编制",
    "事业编制管理", "全额事业编制", "正式事业编制", "事业单位编制",
    "财政全额拨款事业单位", "全额拨款事业单位",
]
LIKELY_COMPILE_WORDS = [
    "事业单位人事管理条例", "事业单位公开招聘", "事业单位工作人员",
    "办理聘用手续", "列入事业单位", "教育事业单位",
]
UNCERTAIN_WORDS = [
    "备案制", "控制数", "人员控制数", "员额制", "聘用制",
]
EXCLUDE_WORDS = [
    "民办", "私立", "培训机构", "代课", "合同制", "劳务派遣",
    "人事代理", "购买服务", "政府购买服务", "临聘", "编外", "校聘",
    "派遣制", "见习", "实习", "劳务外包",
]
FOLLOWUP_WORDS = [
    "资格复审", "面试", "笔试", "体检", "考察", "公示", "递补",
    "岗位取消", "岗位核减", "拟聘用", "报名",
]
DATE_RE = re.compile(
    r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?"
)


def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip()


def stable_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
    temporary.replace(path)


def extract_date(text):
    match = DATE_RE.search(text or "")
    if not match:
        return ""
    return "{0}-{1:02d}-{2:02d}".format(
        int(match.group(1)), int(match.group(2)), int(match.group(3))
    )


class Monitor(object):
    def __init__(self, config, verbose=False):
        self.config = config
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.get(
                "user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            )
        })
        self.timeout = int(config.get("timeout_seconds", 20))
        self.delay = float(config.get("request_delay_seconds", 0.5))

    def log(self, message):
        print(message, flush=True)

    def fetch(self, url):
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        time.sleep(self.delay)
        return response.text

    def links_from_source(self, source):
        html = self.fetch(source["url"])
        soup = BeautifulSoup(html, "lxml")
        host = urlparse(source["url"]).netloc
        candidates = {}
        for anchor in soup.find_all("a", href=True):
            title = normalize(anchor.get_text(" ", strip=True))
            if len(title) < 6:
                continue
            url = urljoin(source["url"], anchor["href"]).split("#", 1)[0]
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or parsed.netloc != host:
                continue
            context = title
            if anchor.parent:
                context += " " + normalize(anchor.parent.get_text(" ", strip=True))
            if not self.looks_like_recruitment(context):
                continue
            candidates[url] = {
                "title": title,
                "url": url,
                "source": source["name"],
                "listing_context": normalize(context)[:1000],
            }
        limit = int(source.get("max_detail_pages", 30))
        return list(candidates.values())[:limit]

    @staticmethod
    def looks_like_recruitment(text):
        has_school = any(word in text for word in SCHOOL_WORDS)
        has_recruit = any(word in text for word in RECRUIT_WORDS + FOLLOWUP_WORDS)
        return has_school and has_recruit

    def inspect_item(self, item):
        try:
            html = self.fetch(item["url"])
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            body = normalize(soup.get_text(" ", strip=True))
            title = item["title"]
            page_title = normalize(soup.title.get_text(" ", strip=True)) if soup.title else ""
            if len(title) < 10 and page_title:
                title = page_title
            combined = normalize(title + " " + item["listing_context"] + " " + body)
            result = dict(item)
            result.update({
                "title": title,
                "date": extract_date(item["listing_context"] + " " + body[:2000]),
                "classification": self.classify(combined),
                "matched_terms": self.matched_terms(combined),
                "content_hash": stable_hash(body),
                "checked_at": datetime.now().isoformat(timespec="seconds"),
            })
            return result
        except Exception as exc:
            self.log("  正文读取失败：{0} ({1})".format(item["url"], exc))
            combined = item["title"] + " " + item["listing_context"]
            result = dict(item)
            result.update({
                "date": extract_date(combined),
                "classification": self.classify(combined),
                "matched_terms": self.matched_terms(combined),
                "content_hash": stable_hash(combined),
                "checked_at": datetime.now().isoformat(timespec="seconds"),
                "detail_error": str(exc),
            })
            return result

    @staticmethod
    def matched_terms(text):
        groups = STRONG_COMPILE_WORDS + LIKELY_COMPILE_WORDS + UNCERTAIN_WORDS
        groups += EXCLUDE_WORDS + RECRUIT_WORDS + FOLLOWUP_WORDS
        return sorted(set(word for word in groups if word in text))

    @staticmethod
    def classify(text):
        if any(word in text for word in EXCLUDE_WORDS):
            return "excluded"
        in_baoding = any(word in text for word in BAODING_WORDS)
        is_school = any(word in text for word in SCHOOL_WORDS)
        is_recruitment = any(word in text for word in RECRUIT_WORDS + FOLLOWUP_WORDS)
        if not (in_baoding and is_school and is_recruitment):
            return "irrelevant"
        if any(word in text for word in UNCERTAIN_WORDS):
            return "uncertain"
        if any(word in text for word in STRONG_COMPILE_WORDS):
            return "confirmed"
        if any(word in text for word in LIKELY_COMPILE_WORDS):
            return "likely"
        return "needs_review"

    def run(self):
        results = []
        failures = []
        for source in self.config.get("sources", []):
            if not source.get("enabled", True):
                continue
            self.log("检查：{0}".format(source["name"]))
            try:
                links = self.links_from_source(source)
                self.log("  找到 {0} 个候选公告".format(len(links)))
                for item in links:
                    inspected = self.inspect_item(item)
                    if inspected["classification"] not in ("irrelevant", "excluded"):
                        results.append(inspected)
            except Exception as exc:
                failures.append({"source": source["name"], "error": str(exc)})
                self.log("  来源失败：{0}".format(exc))
        unique = {}
        for item in results:
            unique[item["url"]] = item
        return list(unique.values()), failures


def build_report(items, failures):
    labels = {
        "confirmed": "明确事业编",
        "likely": "事业单位招聘（建议核对岗位表）",
        "uncertain": "编制性质不确定",
        "needs_review": "需人工核对",
    }
    lines = [
        "# 保定初高中教师招聘监控",
        "",
        "生成时间：{0}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "",
    ]
    if not items:
        lines += ["本次没有发现新的相关公告。", ""]
    for item in sorted(items, key=lambda value: (value.get("date", ""), value["title"]), reverse=True):
        lines += [
            "## {0}".format(item["title"]),
            "",
            "- 判断：{0}".format(labels.get(item["classification"], item["classification"])),
            "- 来源：{0}".format(item["source"]),
            "- 日期：{0}".format(item.get("date") or "网页未识别"),
            "- 链接：{0}".format(item["url"]),
            "- 命中词：{0}".format("、".join(item.get("matched_terms", [])) or "无"),
            "",
        ]
    if failures:
        lines += ["## 抓取异常", ""]
        for failure in failures:
            lines.append("- {0}：{1}".format(failure["source"], failure["error"]))
        lines.append("")
    return "\n".join(lines)


def save_public_data(items, failures):
    """输出给 PWA 使用的公开数据，不包含邮箱、密码等配置。"""
    public_items = []
    for item in sorted(
        items,
        key=lambda value: (value.get("date", ""), value.get("title", "")),
        reverse=True,
    ):
        public_items.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "source": item.get("source", ""),
            "date": item.get("date", ""),
            "classification": item.get("classification", "needs_review"),
            "matched_terms": item.get("matched_terms", []),
            "checked_at": item.get("checked_at", ""),
        })
    save_json(PUBLIC_DATA_FILE, {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(public_items),
        "items": public_items,
        "source_failures": failures,
    })


def send_email(subject, report):
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    recipients = os.getenv("MAIL_TO", user or "")
    if not user or not password or not recipients:
        print("未配置 SMTP_USER/SMTP_PASS/MAIL_TO，已跳过邮件。")
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = user
    message["To"] = recipients
    message.set_content(report)
    host = os.getenv("SMTP_HOST", "smtp.qq.com")
    port = int(os.getenv("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as server:
        server.login(user, password)
        server.send_message(message)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notify-existing", action="store_true", help="首次运行也提醒已有公告")
    parser.add_argument("--dry-run", action="store_true", help="生成报告但不发邮件、不更新状态")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not CONFIG_FILE.exists():
        print("缺少配置文件：{0}".format(CONFIG_FILE), file=sys.stderr)
        return 2

    config = load_json(CONFIG_FILE, {})
    old_state = load_json(STATE_FILE, {"initialized": False, "items": {}})
    monitor = Monitor(config, args.verbose)
    items, failures = monitor.run()
    save_public_data(items, failures)

    old_items = old_state.get("items", {})
    changed = []
    for item in items:
        previous = old_items.get(item["url"])
        if previous is None or previous.get("content_hash") != item.get("content_hash"):
            changed.append(item)

    first_run = not old_state.get("initialized", False)
    notify_items = changed
    if first_run and not args.notify_existing:
        notify_items = []
        print("首次运行：已建立基线，本次不提醒历史公告。")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "{0}.md".format(datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    report = build_report(notify_items, failures)
    report_path.write_text(report, encoding="utf-8")
    print("报告：{0}".format(report_path))

    if notify_items and not args.dry_run:
        subject = "保定初高中事业编招聘：发现 {0} 条新增/更新".format(len(notify_items))
        try:
            if send_email(subject, report):
                print("邮件已发送。")
        except Exception as exc:
            print("邮件发送失败：{0}".format(exc), file=sys.stderr)

    if not args.dry_run:
        merged = dict(old_items)
        for item in items:
            merged[item["url"]] = item
        save_json(STATE_FILE, {
            "initialized": True,
            "last_run": datetime.now().isoformat(timespec="seconds"),
            "items": merged,
            "failures": failures,
        })

    print("有效公告 {0} 条；新增或更新 {1} 条。".format(len(items), len(changed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
