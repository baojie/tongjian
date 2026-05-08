#!/usr/bin/env python3
"""
从资治通鉴原文中发现未建页的实体（人名/地名/官职）。

策略变更 v2:
  人名: 放弃「XX曰」模式（噪音太大），改为从 D1 broken wikilink 中提取
        person 类型候选，然后用 corpus_search 验证正文命中。
  地名: 提取「X州」「X郡」「X城」「X县」模式 + 过滤泛称 + corpus 验证。
  官职: 全词匹配 + corpus 验证。

用法:
  python3 wiki/scripts/butler/corpus_discover.py [--top N] [--output FILE]
"""

import re
import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path('/home/baojie/work/knowledge/tongjian')
CORPUS = BASE / 'corpus/raw/资治通鉴.txt'
PAGES_JSON = BASE / 'wiki/public/pages.json'

def load_all_known():
    """加载所有已有页面 ID + label + aliases。"""
    data = json.load(open(PAGES_JSON))
    pages = data['pages']
    existing = set(pages.keys())
    label_to_page = {}
    for slug, meta in pages.items():
        label = meta.get('label', slug)
        if label != slug:
            label_to_page[label] = slug
        for a in meta.get('aliases', []):
            label_to_page[a] = slug
    all_known = existing | set(label_to_page.keys())
    return pages, existing, all_known


def load_person_names():
    """加载已有 person 类型页面的名字部件，用于人名匹配。"""
    data = json.load(open(PAGES_JSON))
    pages = data['pages']
    names = set()
    for slug, meta in pages.items():
        if meta.get('type') == '人物':
            names.add(slug)
            for a in meta.get('aliases', []):
                names.add(a)
    return names


# ── 过滤集 ──────────────────────────────────────────

# 地名泛称（不是特定地名）
PLACE_GENERIC = {
    '京城', '都城', '城中', '郡城', '县城', '州城', '诸州', '诸郡', '诸城',
    '城中', '城外', '郡中', '县中', '关中', '关内', '关外', '关前', '关后',
    '塞外', '塞内', '塞上', '塞下',
    '弃城', '闭城', '登城', '据城', '举城', '以城', '至城', '去城', '还平城',
    '深沟高垒', '主还平城',
    '今城', '今关', '以塞', '斩关',
    '赐爵关', '京师及郡', '都督扬州', '都督荆州', '以扬州', '为南徐州',
    '为南兗州', '为南豫州',
}

# 州名已知（已有页面或已作为组成部分）
KNOWN_ZHOU_PREFIX = {
    '冀二', '兗二', '秦二', '益二', '凉二', '并二', '豫二', '荆二', '扬二',
    '徐二', '青二', '幽二', '雍二', '梁二', '交二', '广二',
}


def is_place_known(full):
    """判断是否为已知地名。"""
    if full in PLACE_GENERIC:
        return True
    # 跳过「X二州」模式（如「冀二州」= 冀州+XX州，非单纯地名）
    for k in KNOWN_ZHOU_PREFIX:
        if full.startswith(k):
            return True
    return False


# 常见官职名（完整词）
COMMON_TITLES = [
    '丞相', '太尉', '司徒', '司空', '司马', '司寇', '司士', '司会',
    '太守', '刺史', '尚书', '仆射', '常侍', '侍郎', '郎中', '都尉',
    '校尉', '长史', '从事', '主簿', '县令', '县尉', '县丞',
    '郡守', '郡尉', '监军', '御史', '大夫', '将军',
    '节度使', '观察使', '防御使', '团练使', '经略使', '总管', '都督',
    '中书令', '侍中', '尚书令', '枢密使', '参知政事', '判官', '推官',
    '博士', '祭酒', '司业',
    '谏议大夫', '拾遗', '补阙', '正言', '司谏',
    '大将军', '骠骑将军', '车骑将军', '卫将军',
    '安东将军', '安南将军', '安西将军', '安北将军',
    '平东将军', '平南将军', '平西将军', '平北将军',
    '征东将军', '征南将军', '征西将军', '征北将军',
    '镇东将军', '镇南将军', '镇西将军', '镇北将军',
    '龙骧将军', '辅国将军', '冠军将军', '游击将军',
    '领军将军', '护军将军', '中领军', '中护军',
    '都督诸军事', '大都督',
    '太子太傅', '太子少傅', '太子太师', '太子少师',
    '大司农', '大鸿胪', '大司空', '大司徒', '大宗伯',
    '大理卿', '太常卿', '光禄卿', '卫尉卿', '太仆卿',
    '廷尉', '鸿胪卿', '司农卿', '太府卿',
    '内史', '治粟内史', '典属国', '少府', '将作大匠',
    '詹事', '中庶子', '洗马', '舍人', '家令',
    '率更令', '家丞', '庶子', '谕德', '赞善',
    '节度', '观察', '防御', '团练', '经略',
    '总督', '巡抚', '提督', '总兵', '副将', '参将',
    '录事', '功曹', '仓曹', '兵曹', '骑曹',
    '长秋', '大长秋', '东园', '尚方', '御府', '掖庭',
    '大行', '典客', '行人',
]


def discover_places(text, all_known, min_freq=3, top=60):
    """从原文发现未建页地名（X州/X郡/X城/X县）。"""
    # 匹配 1-3字前缀 + 州/郡/城/县
    pat = re.compile(r'([一-鿿]{1,3})(州|郡|城|县)')
    hits = pat.findall(text)

    counter = Counter()
    for prefix, suffix in hits:
        full = prefix + suffix
        if full in all_known:
            continue
        if is_place_known(full):
            continue
        if len(prefix) < 1:
            continue
        # 上下文检验：如果后面紧跟着「之」「等」「皆」，可能不是地名
        counter[full] += 1

    # 按频次排序并过滤
    result = {k: v for k, v in counter.most_common(200)
              if k not in all_known and v >= min_freq}
    return dict(sorted(result.items(), key=lambda x: -x[1])[:top])


def discover_titles(text, all_known, min_freq=3, top=60):
    """从原文发现未建页官职。"""
    counter = Counter()
    for title in COMMON_TITLES:
        if title in all_known:
            continue
        count = text.count(title)
        if count >= min_freq:
            counter[title] = count
    return dict(sorted(counter.items(), key=lambda x: -x[1])[:top])


def discover_d1_persons(text, all_known, top=60):
    """
    从 D1 broken wikilink 扫描中提取 person 类型候选，
    然后用 corpus 验证是否有正文命中（确保可建页时有 PN 引注）。
    """
    # 运行 D1 扫描
    import subprocess
    result = subprocess.run(
        ['python3', str(BASE / 'wiki/scripts/butler/discover_wanted.py'), '--top', '120', '--json'],
        capture_output=True, text=True, cwd=str(BASE)
    )

    candidates = []
    for line in result.stdout.split('\n'):
        line = line.strip()
        if not line or line.startswith('---') or line.startswith('===') or line.startswith('共'):
            continue
        # 格式：序号. 名称 (链接数)
        m = re.match(r'\s*\d+\.\s+(.+?)\s*\(×?\d+\)', line)
        if not m:
            continue
        name = m.group(1).strip()
        # 过滤概念类词（财政、制度、行政等）
        if name in all_known:
            continue
        # 检查是否在正文中出现（确保有 PN 来源）
        count = text.count(name)
        if count < 3:
            continue
        # 分类：是像人名、地名还是官职？
        candidates.append((name, count))

    return candidates


def discover_persons_via_corpus(text, all_known, existing_person_names, top=60, min_freq=5):
    """
    从原文直接发现未建页人物。

    方法：寻找「以XX为XX」「封XX」「拜XX」「立XX为」等任命/封赏格式中的实体。
    这些模式比「XX曰」更可靠，因为被任命/被封赏的通常是特定人物。
    """
    # 模式1：以[XX]为 — 任命
    pat1 = re.compile(r'以([一-鿿]{2,4})为')
    hits1 = pat1.findall(text)

    # 模式2：封[XX] — 封爵
    pat2 = re.compile(r'(?:封|拜|立|加)([一-鿿]{2,3})(?:为|以|。)')
    hits2 = pat2.findall(text)

    # 模式3：使[XX] — 派遣某人做某事
    pat3 = re.compile(r'使([一-鿿]{2,3})(?:为|将|率|攻|伐|守|使|镇|都|领|护)')
    hits3 = pat3.findall(text)

    # 组合所有模式
    all_hits = list(hits1) + list(hits2) + list(hits3)
    counter = Counter(all_hits)

    # 过滤
    person_names = set()
    for slug in existing_person_names:
        person_names.add(slug)
        # 也加入单名
        if len(slug) == 2:
            person_names.add(slug)
        elif len(slug) == 3:
            person_names.add(slug[1:])  # 后两字（名）
            person_names.add(slug[0])   # 姓

    # 加载姓氏表（从已有 person 页面提取）
    surnames = set()
    for slug in existing_person_names:
        if len(slug) >= 2:
            surnames.add(slug[0])  # 第一个字可能是姓

    # 常见姓氏补充
    common_surnames = '赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳丰鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅齐康伍余元卜顾孟黄穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞纪项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟邱徐高蔡田胡凌霍虞万支柯昝管卢经裘缪干解应宗宣丁贲邓郁单杭洪包诸左石吉崔龚程嵇邢滑裴陆荣翁荀羊於惠甄麴家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇暴甘戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逮盍益桓公'

    all_surnames = surnames | set(common_surnames)

    # 过滤
    filtered = {}
    for name, freq in counter.most_common(200):
        if name in all_known:
            continue
        if freq < min_freq:
            continue
        # 跳过明显不是人名的词
        if len(name) < 2:
            continue
        # 必须包含至少一个姓氏字符
        has_surname = any(c in all_surnames for c in name)
        if not has_surname:
            continue
        # 跳过已知官职名（以防「以刺史为XX」之类）
        if name in COMMON_TITLES:
            continue
        # 检查是否在正文中有「XX曰」出现（确认是人名）
        has_speech = text.count(f'{name}曰') > 0

        filtered[name] = {
            'freq': freq,
            'has_speech': has_speech,
        }

    return filtered


def main():
    top = 60
    output_file = '/tmp/corpus_discover_result.json'
    for arg in sys.argv[1:]:
        if arg.startswith('--top='):
            top = int(arg.split('=')[1])
        elif arg.startswith('--output='):
            output_file = arg.split('=')[1]
        elif arg == '--json':
            pass  # default behavior

    text = open(CORPUS).read()
    pages, existing, all_known = load_all_known()
    existing_person_names = load_person_names()

    print(f'=== 原文发现结果 ===')
    print(f'已有页面总数: {len(existing)}')
    print(f'已有person页面: {len(existing_person_names)}')
    print()

    # ── 1. 人物发现 ──
    persons = discover_persons_via_corpus(text, all_known, existing_person_names,
                                          top=top, min_freq=5)
    print(f'--- 未建页人物候选 (任命/封赏模式, freq≥5) ---')
    print(f'共 {len(persons)} 条')
    sorted_persons = sorted(persons.items(), key=lambda x: -x[1]['freq'])
    for i, (name, info) in enumerate(sorted_persons[:top]):
        speech_tag = '✅有曰' if info['has_speech'] else '  '
        print(f'  {i+1:3d}. {name} (×{info["freq"]}) {speech_tag}')

    # ── 2. 地名发现 ──
    places = discover_places(text, all_known, min_freq=5, top=top)
    print()
    print(f'--- 未建页地名候选 (州/郡/城/县后缀, freq≥5) ---')
    print(f'共 {len(places)} 条')
    for i, (name, freq) in enumerate(places.items()):
        print(f'  {i+1:3d}. {name} (×{freq})')

    # ── 3. 官职发现 ──
    titles = discover_titles(text, all_known, min_freq=5, top=top)
    print()
    print(f'--- 未建页官职候选 (全词匹配, freq≥5) ---')
    print(f'共 {len(titles)} 条')
    for i, (name, freq) in enumerate(titles.items()):
        print(f'  {i+1:3d}. {name} (×{freq})')

    # ── 保存结果 ──
    output = {
        'persons': [(k, v['freq'], v['has_speech']) for k, v in sorted_persons[:top]],
        'places': list(places.items()),
        'titles': list(titles.items()),
    }
    with open(output_file, 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'\n结果已保存到 {output_file}')


if __name__ == '__main__':
    main()
