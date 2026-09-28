# -*- coding: utf-8 -*-
"""历史记录模块：把每次自查结果保存到本地 JSON，支持趋势对比。

存储位置：项目目录下的 .datacheck_history.json（已加入 .gitignore）。
注意：部署到 Streamlit Cloud 等托管平台时，本地文件是临时存储，
重启后历史会丢失，属正常现象。
"""

import json
import os
from datetime import datetime

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".datacheck_history.json")

# 最多保留的历史记录条数
MAX_RECORDS = 50


def _load_all():
    """读取全部历史记录，文件不存在或损坏时返回空列表。"""
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_record(answers, hits, score, rating, dim_scores):
    """保存一次自查结果，返回新记录 dict。"""
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "score": score,
        "rating": rating,
        "industry": answers.get("industry", "通用"),
        "dau_scale": answers.get("dau_scale", ""),
        "counts": {
            "高": sum(1 for h in hits if h["level"] == "高"),
            "中": sum(1 for h in hits if h["level"] == "中"),
            "低": sum(1 for h in hits if h["level"] == "低"),
        },
        "dim_scores": dim_scores,
        "rule_ids": [h["rule_id"] for h in hits],
    }
    records = _load_all()
    records.append(record)
    records = records[-MAX_RECORDS:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return record


def list_records():
    """返回全部历史记录（按时间升序）。"""
    return _load_all()


def clear_records():
    """清空历史记录。"""
    try:
        os.remove(HISTORY_FILE)
    except OSError:
        pass


def compare_with_last(score):
    """与上一次自查比较，返回 (上次分数, 分差)；无历史时返回 (None, None)。"""
    records = _load_all()
    if len(records) < 2:
        return None, None
    last = records[-2]["score"]
    return last, score - last
