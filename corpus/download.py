#!/usr/bin/env python3
"""批量下载资治通鉴白话版并转换为Markdown"""

import os
import time
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://chinesebooks.github.io/shishu/zizhitongjian/{}.html"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# 章节映射：页码范围 -> (纪名, 起始卷号)
SECTIONS = [
    (80337, 80333, "周纪", 1),
    (80332, 80330, "秦纪", 1),
    (80329, 80270, "汉纪", 1),
    (80269, 80260, "魏纪", 1),
    (80259, 80220, "晋纪", 1),
    (80219, 80204, "宋纪", 1),
    (80203, 80194, "齐纪", 1),
    (80193, 80172, "梁纪", 1),
    (80171, 80162, "陈纪", 1),
    (80161, 80154, "隋纪", 1),
    (80153, 80073, "唐纪", 1),
    (80072, 80067, "后梁纪", 1),
    (80066, 80059, "后唐纪", 1),
    (80058, 80053, "后晋纪", 1),
    (80052, 80049, "后汉纪", 1),
    (80048, 80044, "后周纪", 1),
]

def get_section_name(page_id):
    """根据页码返回(纪名, 卷号)"""
    for start, end, name, vol_start in SECTIONS:
        if end <= page_id <= start:
            vol = vol_start + (start - page_id)
            return name, vol
    return "其他", 0

def html_to_markdown(content_div, title):
    """将articleContent转换为Markdown"""
    lines = ["# " + title, ""]

    for elem in content_div.children:
        if hasattr(elem, 'get_text'):
            tag = elem.name
            text = elem.get_text(strip=True)
            if not text:
                continue
            if tag in ('h1', 'h2', 'h3'):
                level = int(tag[1])
                lines.append("#" * level + " " + text)
            elif tag == 'p':
                lines.append(text)
                lines.append("")
            else:
                lines.append(text)
                lines.append("")
        else:
            text = str(elem).strip()
            if text:
                lines.append(text)

    return "\n".join(lines)

def download_page(page_id, session):
    url = BASE_URL.format(page_id)
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 404:
            return None
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')

        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else f"第{page_id}页"

        content = soup.find(id='articleContent')
        if not content:
            return None

        md = html_to_markdown(content, title)
        return title, md
    except Exception as e:
        print(f"  错误 {page_id}: {e}")
        return None

def main():
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'

    # 收集所有页码
    all_pages = []
    for start, end, name, vol_start in SECTIONS:
        for page_id in range(start, end - 1, -1):
            vol = vol_start + (start - page_id)
            all_pages.append((page_id, name, vol))

    print(f"共 {len(all_pages)} 个页面待下载")

    success = 0
    failed = []

    for i, (page_id, name, vol) in enumerate(all_pages):
        filename = f"{name}{vol:02d}_{page_id}.md"
        filepath = os.path.join(OUT_DIR, filename)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
            print(f"[{i+1}/{len(all_pages)}] 已存在: {filename}")
            success += 1
            continue

        print(f"[{i+1}/{len(all_pages)}] 下载: {name}第{vol}卷 ({page_id})", end=" ... ", flush=True)
        result = download_page(page_id, session)

        if result:
            title, md = result
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md)
            print(f"OK ({len(md)}字符)")
            success += 1
        else:
            print("SKIP (404或无内容)")
            failed.append(page_id)

        time.sleep(0.3)  # 礼貌延迟

    print(f"\n完成: {success} 成功, {len(failed)} 失败")
    if failed:
        print(f"失败页码: {failed}")

if __name__ == "__main__":
    main()
