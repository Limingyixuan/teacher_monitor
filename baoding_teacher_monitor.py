#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""保定地区初高中事业编教师招聘监控。兼容 Python 3.7+。"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config.json"
STATE_FILE = ROOT / "data" / "state.json"
REPORT_DIR = ROOT / "reports"
PUBLIC_DATA_FILE = ROOT / "docs" / "data" / "latest_jobs.json"
PWA_URL = "https://limingyixuan.github.io/teacher_monitor/"
WECHAT_NOTIFY_REGIONS = {
    "保定市", "市直", "莲池区", "竞秀区", "高新区",
}

REGION_ALIASES = [
    ("市直", ["市直"]),
    ("高新区", ["高新区", "高新技术产业开发区"]),
    ("白沟新城", ["白沟新城", "白沟"]),
    ("莲池区", ["莲池区", "莲池"]),
    ("竞秀区", ["竞秀区", "竞秀"]),
    ("满城区", ["满城区", "满城"]),
    ("清苑区", ["清苑区", "清苑"]),
    ("徐水区", ["徐水区", "徐水"]),
    ("涞水县", ["涞水县", "涞水"]),
    ("阜平县", ["阜平县", "阜平"]),
    ("定兴县", ["定兴县", "定兴"]),
    ("唐县", ["唐县"]),
    ("高阳县", ["高阳县", "高阳"]),
    ("涞源县", ["涞源县", "涞源"]),
    ("望都县", ["望都县", "望都"]),
    ("易县", ["易县"]),
    ("曲阳县", ["曲阳县", "曲阳"]),
    ("蠡县", ["蠡县"]),
    ("顺平县", ["顺平县", "顺平"]),
    ("博野县", ["博野县", "博野"]),
    ("涿州市", ["涿州市", "涿州"]),
    ("安国市", ["安国市", "安国"]),
    ("高碑店市", ["高碑店市", "高碑店"]),
    ("定州市", ["定州市", "定州"]),
    ("雄安新区", ["雄安新区", "雄安"]),
    ("容城县", ["容城县", "容城"]),
    ("安新县", ["安新县", "安新"]),
    ("雄县", ["雄县"]),
]
BAODING_WORDS = ["保定", "多县", "县市区"] + [
    alias for _, aliases in REGION_ALIASES for alias in aliases
]
SCHOOL_WORDS = [
    "教师", "中学", "初中", "高中", "完全中学", "教育事业单位",
    "教体局", "教育局", "学校", "教育类", "中小学", "教职", "教研员",
]
SUBJECT_WORDS = [
    "语文", "数学", "英语", "物理", "化学", "生物", "思想政治", "政治",
    "历史", "地理", "信息技术", "通用技术", "计算机", "科学", "体育",
    "音乐", "美术", "心理健康", "心理", "道德与法治", "劳动教育",
]
SCHOOL_NAME_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9·]{2,36}"
    r"(?:实验学校|高级中学|初级中学|完全中学|职业教育中心|职教中心|"
    r"中等专业学校|中等职业学校|中学|学校|一中|二中|三中|四中))"
)
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
EMPLOYMENT_PHRASES = {
    "民办": ["民办学校", "民办普通高中", "民办高级中学", "民办中学"],
    "私立": ["私立学校", "私立中学"],
    "培训机构": ["培训机构招聘", "教育培训机构"],
    "代课": ["代课教师", "招聘代课"],
    "合同制": ["合同制教师", "招聘合同制", "合同制工作人员"],
    "劳务派遣": ["劳务派遣", "派遣用工"],
    "人事代理": ["人事代理"],
    "购买服务": ["政府购买服务岗位", "购买服务人员", "购买服务教师"],
    "临聘": ["临聘教师", "招聘临聘"],
    "编外": ["编外教师", "编外人员"],
    "校聘": ["校聘教师"],
    "派遣制": ["派遣制教师", "派遣制工作人员"],
    "见习": ["见习岗位", "就业见习"],
    "实习": ["实习教师", "实习岗位"],
    "备案制": ["备案制教师", "人员备案制"],
    "控制数": ["人员控制数", "控制数教师"],
    "员额制": ["员额制教师", "员额制人员"],
    "聘用制": ["聘用制教师"],
}
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


def detect_regions(title_context, body=""):
    """优先用标题判断地区，避免正文导航栏中的区县名造成误判。"""
    primary = title_context or ""
    regions = [
        name for name, aliases in REGION_ALIASES
        if any(alias in primary for alias in aliases)
    ]
    if regions:
        return list(dict.fromkeys(regions))
    if "市直" in primary:
        return ["市直"]
    if "保定" in primary:
        return ["保定市"]
    if not regions:
        secondary = (body or "")[:6000]
        regions = [
            name for name, aliases in REGION_ALIASES
            if any(alias in secondary for alias in aliases)
        ]
    regions = list(dict.fromkeys(regions))
    if len(regions) >= 4 or any(word in primary for word in ["多县", "七县", "县市区"]):
        return ["多县区"]
    if regions:
        return regions
    return ["地区待核实"]


def detect_school_levels(title_text, main_text=""):
    """识别公告覆盖的学段；仅写“教师/教育类”的公告暂标为待核实。"""
    text = normalize((title_text or "") + " " + (main_text or "")[:8000])
    has_junior = any(word in text for word in [
        "初中", "初级中学", "九年一贯制", "义务教育阶段",
    ])
    has_senior = any(word in text for word in [
        "高中", "高级中学", "普通高中", "完全中学", "职教中心",
        "职业高中", "中等职业学校", "中职",
    ])
    if has_junior and has_senior:
        return ["初中", "高中"]
    if has_junior:
        return ["初中"]
    if has_senior:
        return ["高中"]
    if "中学" in text or "中小学" in text:
        return ["中学未细分"]
    return ["学段待核实"]


def detect_subjects(title_text, main_text=""):
    text = normalize((title_text or "") + " " + (main_text or "")[:12000])
    text = text.replace("教育和体育局", "教育局")
    text = text.replace("教育体育局", "教育局")
    text = text.replace("科学技术", "科技")
    return sorted(set(subject for subject in SUBJECT_WORDS if subject in text))


def detect_school_names(title_text, main_text=""):
    """提取明确出现的学校名称；统一招聘未列学校时返回空列表。"""
    text = normalize((title_text or "") + " " + (main_text or "")[:12000])
    matches = []
    for match in SCHOOL_NAME_RE.findall(text):
        name = re.sub(r"^20\d{2}年", "", match)
        name = re.sub(r"^(?:河北省|保定市|雄安新区)", "", name)
        name = re.sub(
            r"^(?:关于|年度|年|公开招聘|公开选聘|招聘|选聘)+", "", name
        )
        for _, aliases in REGION_ALIASES:
            for alias in sorted(aliases, key=len, reverse=True):
                if name.startswith(alias) and len(name) - len(alias) >= 6:
                    name = name[len(alias):]
                    break
        if any(bad in name for bad in ["事业单位", "人力资源", "教育和体育局"]):
            continue
        if 3 <= len(name) <= 40 and name not in matches:
            matches.append(name)
    return matches[:5]


def should_notify_wechat(item):
    return bool(
        WECHAT_NOTIFY_REGIONS.intersection(item.get("regions", []))
    )


def detect_employment_terms(title_text, main_text=""):
    found = set(word for word in EXCLUDE_WORDS + UNCERTAIN_WORDS if word in title_text)
    for label, phrases in EMPLOYMENT_PHRASES.items():
        if any(phrase in main_text for phrase in phrases):
            found.add(label)
    return sorted(found)


def extract_main_text(soup):
    selectors = [
        "article", ".TRS_Editor", ".article-content", ".article_content",
        ".content-detail", ".detail-content", ".news-content", ".zwxl-content",
        "#zoom", "#content",
    ]
    candidates = []
    for selector in selectors:
        for node in soup.select(selector):
            text = normalize(node.get_text(" ", strip=True))
            if len(text) >= 100:
                candidates.append(text)
    return max(candidates, key=len) if candidates else ""


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
        if source.get("mode") == "baoding_rsj_api":
            return self.links_from_baoding_rsj_api(source)
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
            if source.get("source_type") == "aggregator":
                if url.rstrip("/") == source["url"].rstrip("/") or "/list/" in parsed.path:
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
                "source_type": source.get("source_type", "official"),
                "source_url": source["url"],
                "listing_context": normalize(context)[:1000],
            }
        limit = int(source.get("max_detail_pages", 30))
        return list(candidates.values())[:limit]

    def links_from_baoding_rsj_api(self, source):
        endpoint = source["api_url"]
        response = self.session.post(
            endpoint,
            json={"pageNum": 1, "pageSize": int(source.get("max_items", 100)),
                  "publishOrNot": "1"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        records = ((payload.get("data") or {}).get("list") or [])
        items = []
        for record in records:
            title = normalize(record.get("noticeTitle", ""))
            if not title or not self.looks_like_recruitment(title):
                continue
            notice_id = record.get("id")
            url = "{0}?noticeId={1}#/examinee/mobileHostPage/home".format(
                source["url"].rstrip("/"), notice_id
            )
            raw = json.dumps(record, ensure_ascii=False, sort_keys=True)
            items.append({
                "title": title,
                "url": url,
                "source": source["name"],
                "source_type": source.get("source_type", "official"),
                "source_url": source["url"],
                "listing_context": title + " " + (record.get("publishTime") or ""),
                "api_record": record,
                "api_hash": stable_hash(raw),
            })
        return items

    @staticmethod
    def looks_like_recruitment(text):
        has_school = any(word in text for word in SCHOOL_WORDS)
        has_recruit = any(word in text for word in RECRUIT_WORDS + FOLLOWUP_WORDS)
        return has_school and has_recruit

    def inspect_item(self, item):
        if item.get("api_record"):
            title_context = normalize(
                item["title"] + " " + item["listing_context"] + " " + item["source"]
            )
            combined = title_context
            result = dict(item)
            result.pop("api_record", None)
            result.update({
                "date": extract_date(item["listing_context"]),
                "classification": self.classify(combined),
                "matched_terms": self.matched_terms(combined),
                "employment_terms": detect_employment_terms(title_context),
                "regions": detect_regions(item["title"] + " " + item["source"]),
                "school_levels": detect_school_levels(item["title"]),
                "subjects": detect_subjects(item["title"]),
                "school_names": detect_school_names(item["title"]),
                "content_hash": item["api_hash"],
                "checked_at": datetime.now().isoformat(timespec="seconds"),
            })
            return result
        try:
            html = self.fetch(item["url"])
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            body = normalize(soup.get_text(" ", strip=True))
            main_text = extract_main_text(soup)
            title = item["title"]
            page_title = normalize(soup.title.get_text(" ", strip=True)) if soup.title else ""
            if len(title) < 10 and page_title:
                title = page_title
            title_context = normalize(title + " " + item["source"])
            combined = normalize(
                title_context + " " + item["listing_context"] + " " + body
            )
            result = dict(item)
            employment_context = title
            if item.get("source_type") != "aggregator":
                employment_context += " " + item["listing_context"]
            result.update({
                "title": title,
                "date": extract_date(item["listing_context"] + " " + body[:2000]),
                "classification": self.classify(combined),
                "matched_terms": self.matched_terms(combined),
                "employment_terms": detect_employment_terms(
                    employment_context, main_text
                ),
                "regions": detect_regions(title_context, body),
                "school_levels": detect_school_levels(title, main_text),
                "subjects": detect_subjects(title, main_text),
                "school_names": detect_school_names(title, main_text),
                "content_hash": stable_hash(body),
                "checked_at": datetime.now().isoformat(timespec="seconds"),
            })
            return result
        except Exception as exc:
            self.log("  正文读取失败：{0} ({1})".format(item["url"], exc))
            combined = item["title"] + " " + item["listing_context"] + " " + item["source"]
            result = dict(item)
            employment_context = item["title"]
            if item.get("source_type") != "aggregator":
                employment_context += " " + item["listing_context"]
            result.update({
                "date": extract_date(combined),
                "classification": self.classify(combined),
                "matched_terms": self.matched_terms(combined),
                "employment_terms": detect_employment_terms(employment_context),
                "regions": detect_regions(item["title"] + " " + item["source"]),
                "school_levels": detect_school_levels(item["title"]),
                "subjects": detect_subjects(item["title"]),
                "school_names": detect_school_names(item["title"]),
                "content_hash": stable_hash(combined),
                "checked_at": datetime.now().isoformat(timespec="seconds"),
                "detail_error": str(exc),
            })
            return result

    @staticmethod
    def matched_terms(text):
        groups = STRONG_COMPILE_WORDS + LIKELY_COMPILE_WORDS + UNCERTAIN_WORDS
        groups += RECRUIT_WORDS + FOLLOWUP_WORDS
        return sorted(set(word for word in groups if word in text))

    @staticmethod
    def classify(text):
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
                    if inspected["classification"] != "irrelevant":
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
            "source_type": item.get("source_type", "official"),
            "source_url": item.get("source_url", ""),
            "date": item.get("date", ""),
            "classification": item.get("classification", "needs_review"),
            "matched_terms": item.get("matched_terms", []),
            "employment_terms": item.get("employment_terms", []),
            "regions": item.get("regions", ["地区待核实"]),
            "school_levels": item.get("school_levels", ["学段待核实"]),
            "subjects": item.get("subjects", []),
            "school_names": item.get("school_names", []),
            "checked_at": item.get("checked_at", ""),
        })
    save_json(PUBLIC_DATA_FILE, {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(public_items),
        "items": public_items,
        "source_failures": failures,
    })


def send_wechat_push(items):
    token = os.getenv("PUSHPLUS_TOKEN")
    if not token:
        print("未配置 PUSHPLUS_TOKEN，已跳过微信推送。")
        return False

    title = "保定市区/市直招聘有更新（{0}条）".format(len(items))
    lines = [
        "## 保定市区或市直有新的招聘信息",
        "",
    ]
    for index, item in enumerate(items[:10], 1):
        regions = "、".join(item.get("regions", [])) or "地区待核实"
        levels = "＋".join(item.get("school_levels", [])) or "学段待核实"
        schools = "、".join(item.get("school_names", [])) or "岗位表中查看"
        source_kind = "第三方线索" if item.get("source_type") == "aggregator" else "官方来源"
        change_kind = item.get("notification_status", "新增或更新")
        lines.extend([
            "### {0}. {1}｜{2}".format(index, change_kind, schools),
            "- 地区：{0}".format(regions),
            "- 学段：{0}".format(levels),
            "- 日期：{0}".format(item.get("date") or "未识别"),
            "- 公告：{0}".format(item.get("title", "未命名公告")),
            "- 来源：{0}（{1}）".format(item.get("source", ""), source_kind),
            "- [查看原文]({0})".format(item.get("url", PWA_URL)),
            "",
        ])
    if len(items) > 10:
        lines.extend([
            "另外还有 {0} 条，请在网页中查看。".format(len(items) - 10),
            "",
        ])
    lines.extend([
        "[查看全部招聘信息]({0})".format(PWA_URL),
    ])

    response = requests.post(
        "https://www.pushplus.plus/send",
        json={
            "token": token,
            "title": title,
            "content": "\n".join(lines),
            "template": "markdown",
            "channel": "wechat",
        },
        timeout=20,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("code") != 200:
        raise RuntimeError(
            "PushPlus 请求失败：{0}".format(result.get("msg") or result)
        )
    print("微信推送请求已提交，消息流水号：{0}".format(result.get("data", "")))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notify-existing", action="store_true", help="首次运行也提醒已有公告")
    parser.add_argument("--dry-run", action="store_true", help="生成报告但不发邮件、不更新状态")
    parser.add_argument("--test-push", action="store_true", help="仅发送一条微信测试消息")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.test_push:
        test_item = {
            "title": "保定教师招聘微信通知测试",
            "school_names": ["测试学校"],
            "regions": ["保定市"],
            "school_levels": ["高中"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "保定教师编监控程序",
            "source_type": "official",
            "url": PWA_URL,
        }
        if send_wechat_push([test_item]):
            print("微信测试消息已提交。")
            return 0
        return 1

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
            changed_item = dict(item)
            changed_item["notification_status"] = (
                "新增公告" if previous is None else "公告更新"
            )
            changed.append(changed_item)

    first_run = not old_state.get("initialized", False)
    notify_items = [
        item for item in changed if should_notify_wechat(item)
    ]
    skipped_regions = len(changed) - len(notify_items)
    if skipped_regions:
        print(
            "有 {0} 条新增/更新不属于市区或市直，仅更新网页，不发微信。".format(
                skipped_regions
            )
        )
    if first_run and not args.notify_existing:
        notify_items = []
        print("首次运行：已建立基线，本次不提醒历史公告。")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "{0}.md".format(datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    report = build_report(notify_items, failures)
    report_path.write_text(report, encoding="utf-8")
    print("报告：{0}".format(report_path))

    if notify_items and not args.dry_run:
        try:
            send_wechat_push(notify_items)
        except Exception as exc:
            print("微信推送失败：{0}".format(exc), file=sys.stderr)

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
