#!/usr/bin/env python3
"""H21 — 扫描 type=official 页面任职者表格，检测人名提取错误。

已知错误模式（来自自动提取的误匹配）:
  1. 官职前缀粘入：[[太仆卿王昱]] → [[王昱]]
  2. 上下文虚词粘入：[[会闾出]] → [[高闾]]（"会"=恰逢）
  3. 短指代+动词：[[欢袭击]] = "高欢"+"袭击"，[[斯从]] = "李斯"+"从"
  4. 动词短语：[[逮捕勃]]、[[验治何人]]、[[议是]]
  5. 完全抓错：[[之言]]、[[说左]]、[[所卖]]

用法:
    python3 wiki/scripts/butler/h21_audit_person_tables.py           # 只扫描
    python3 wiki/scripts/butler/h21_audit_person_tables.py --fix     # 交互式修正
"""

import re
import sys
import subprocess
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[3]
PAGES = ROOT / "wiki/public/pages"

sys.path.insert(0, str(ROOT / "wiki/scripts"))
from page_bucket import resolve_page_file  # noqa: E402

# ─── 动词短语——出现在人名位置几乎可以肯定提取错误 ───
VERB_PATTERNS = [
    '逮捕','验治','就考','覆案','论罪','科罪','禁推','行刑',
    '断狱','诛勋','法议','问邪','诏狱','考实','望山','出坦',
    '待罪','治罪','请罪','受罪','宜便操','又出卢',
    '议是','说左','之言','执法',
]

# ─── 官职前缀——wikilink 以其开头说明未正确剥离 ───
TITLE_PREFIXES = [
    '太尉','司徒','司空','丞相','太仆','廷尉','御史','大夫',
    '刺史','太守','中书','门下','尚书','郎中','都尉','校尉',
    '光禄','大司','少府','中郎','卫尉','太常','宗正','鸿胪',
    '司隶','京兆','大鸿','奉常','典客','治粟','中尉','将作',
    '詹事','水衡','执金','右北','太师','太傅','太保',
    '都督','总管','节度','观察','防御','团练','经略',
    '长史','司马','参军','录事','功曹','仓曹','户曹','兵曹',
    '法曹','士曹','别驾','治中','典签',
    '大将军','车骑','骠骑','卫将军','龙骧','冠军',
    '征西','征东','征南','征北','镇西','镇东','镇南',
    '镇北','平西','平东','平南','平北',
    '安东','安西','安南','安北',
    '昭义','宣武','宣歙','武宁','彰义','平卢','天平',
    '河东','河阳','陕虢','山南','荆南','剑南','西川',
    '东川','朔方','振武','天德','泾原','邠宁','凤翔',
    '陇右','河西','北庭','安西','范阳','卢龙','成德',
    '魏博','淄青','义武','义昌','大同','奉诚',
    '左冯','右扶','京兆',
    '安阳','颍川','南阳','东郡','陇西','上党','河内',
    '河南','河东','河北','淮南','江南','剑南','岭南',
    '山南','陇右','关内','真定','信都','安定','平原',
    '常山','中山','彭城','琅邪','东海','会稽',
    '太仆卿','安阳令','大司农','中大夫','丞南阳',
    '上柱国','仪同','开府',
    '河南尹',  # missing in original
    '大将军','大司马','大司农','大鸿胪','光禄勋',  # full titles
    '下大夫','右大夫','左将军','右将军','前将军','后将军',
]

# ─── 上下文短指代——自动提取时从前文抓取的单个指代字 ───
# 这些字出现在人名开头几乎总是提取错误（前文人名的残留）
CONTEXT_REFS = {
    '泰':'宇文泰','欢':'高欢','斯':'李斯',
    '亮':'诸葛亮','懿':'司马懿',
    '雄':'刘雄/郝雄','睿':'萧睿/曹睿',
    '演':'元演/高演','崧':'某崧','弘':'某弘',
    '虎':'某虎','睿':'某睿',
}

# ─── 纯虚词开头——表示完全抓错 ───
FUNCTION_STARTS = set('所岂不哉乎矣邪焉兮之其')

# ─── 动词语素——跟在短指代后表示这是动词短语而非人名 ───
VERB_MARKERS = set(
    '免复从入还至击袭举攻请在向出见闻知谓言曰答对'
    '归去来降破败守退进追杀伤斩诛灭收捕系狱案推'
    '用起居行立奏表称号令召告示许听纳拜授迁补领兼'
    '督护监率将引提拥挟持执秉据屯壁筑修缮治理通开'
    '决穿凿望伺候待捕追逐按验结平定安集抚柔附属委'
    '弃释放发动兴作起徵调课敛赋税贡献输转漕运积聚'
    '贮藏卷隐军旅师营阵列伍行戍烽燧候望严警戒备防'
    '御拒敌寇虏禽获俘馘献捷凯旋振旅班劳飨赏赐封裂'
    '剖析爵命秩禄赉予告请谒干求丐假贷'
    '隐于在及之其以与所'
)

# ─── 标点符号——人名中绝对不该出现 ───
PUNCTUATION = set('！？""『』（）〈〉［］，。、；：、～—…·•●○■□◆◇▲△▼▽☆★◎⊙※')


def name_has_verb_prefix(name):
    """检查是否以动词短语开头"""
    for vp in VERB_PATTERNS:
        if name.startswith(vp):
            return True
    return False


def name_has_title_prefix(name):
    """检查是否以官职前缀开头"""
    # 先检查长度是否超过最长前缀
    for prefix in TITLE_PREFIXES:
        if name.startswith(prefix) and len(name) > len(prefix):
            # 排除合法的复姓
            compound_surnames = {'令狐','司徒','司空','司马','上官','欧阳','夏侯',
                                '诸葛','鲜于','申屠','慕容','宇文','长孙','万俟'}
            if prefix in compound_surnames and len(name) - len(prefix) <= 2:
                return False
            return True
    return False


def name_has_context_ref(name):
    """检查是否以单字指代开头（前文人名残留）"""
    if len(name) < 2:
        return False
    if name[0] in CONTEXT_REFS:
        # 如果只有2个字且第二字也在CONTEXT_REFS中，可能是短指代重叠
        # 例：[[泰欢]] → 宇文泰+高欢 的边界错误
        if len(name) == 2:
            return True  # 单字短指代不可能形成合法人名
        # 3字以上：检查剩余部分是否含动词特征
        rest = name[1:]
        verb_count = sum(1 for c in rest if c in VERB_MARKERS)
        # 如果剩余部分超过一半是动词标记 → 几乎可肯定不是人名
        # 即使少于一半，只要剩余部分与已知人名不匹配
        # 放宽标准：剩余部分≥2字且含至少一个动词标记
        if len(rest) >= 2 and verb_count >= 1:
            return True
        if verb_count >= len(rest):  # 全部是动词
            return True
    return False


def name_is_garbled(name):
    """检查是否属于乱码式错误（完全不是人名）"""
    # 5字以上基本不可能是人名（除非带官职前缀）
    if len(name) >= 5:
        return True
    # 纯文言虚词
    FUNCTION_CHARS = set('会代当其何所以为于与且乃此令使将被受宜可未毋勿非议问论考就')
    if all(ch in FUNCTION_CHARS for ch in name):
        return True
    return False


def name_has_noise(name):
    """检查是否含标点符号"""
    return any(c in name for c in PUNCTUATION)


def name_starts_with_function_word(name):
    """检查是否以虚词开头（纯抓错）"""
    return len(name) >= 2 and name[0] in FUNCTION_STARTS


def audit_page(filepath):
    """扫描单个页面，返回可疑条目列表"""
    text = filepath.read_text(encoding='utf-8')
    slug = filepath.stem

    if '任职者' not in text:
        return []

    findings = []
    lines = text.split('\n')
    in_table = False

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()

        # Detect table header
        if '|' in stripped and '任职者' in stripped:
            in_table = True
            continue

        # Track table boundaries
        if not in_table:
            continue
        if not stripped.startswith('|'):
            in_table = False
            continue
        if re.match(r'\|[-| ]+\|', stripped):
            continue

        # Extract [[wikilink]] from table row
        m = re.match(r'\|\s*\[\[([^\]]+)\]\]\s*\|', stripped)
        if not m:
            continue

        name = m.group(1)
        reasons = []

        # Check each detection pattern
        if name_is_garbled(name):
            reasons.append('乱码/过长')
        if name_has_verb_prefix(name):
            reasons.append('动词短语')
        if name_has_title_prefix(name):
            reasons.append('官职前缀')
        if name_has_context_ref(name):
            reasons.append(f'短指代({name[0]})')
        if name_has_noise(name):
            reasons.append('含标点')
        if name_starts_with_function_word(name):
            reasons.append(f'虚词开头({name[0]})')

        if reasons:
            findings.append((slug, lineno, name, '+'.join(reasons)))

    return findings


def fix_entry(slug, fix_content, summary_note):
    """用 edit_page.py 修正单条错误"""
    fix_file = Path(f'/tmp/h21_fix_{slug}.md')
    fix_file.write_text(fix_content, encoding='utf-8')
    cmd = [
        sys.executable, str(ROOT / 'wiki/scripts/edit_page.py'),
        slug, str(fix_file),
        '--allow-shrink',
        '--summary', f'H21: {summary_note}',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr


def main():
    fix_mode = '--fix' in sys.argv
    all_findings = []

    for fpath in sorted(PAGES.rglob('*.md')):
        findings = audit_page(fpath)
        all_findings.extend(findings)

    if not all_findings:
        print("✓ H21 扫描完成：未发现可疑人名提取错误")
        return

    by_page = defaultdict(list)
    for slug, lineno, name, reason in all_findings:
        by_page[slug].append((lineno, name, reason))

    print(f"H21 扫描完成：发现 {len(all_findings)} 条可疑条目，分布在 {len(by_page)} 个页面\n")
    for slug in sorted(by_page):
        entries = by_page[slug]
        pct = f"📄 {slug}.md"
        print(f"  {pct}")
        for lineno, name, reason in entries:
            print(f"    行 {lineno}: [[{name}]]  ← {reason}")

    print(f"\n总计 {len(all_findings)} 条可疑，{len(by_page)} 页待修正")

    if fix_mode:
        print("\n进入交互式修正模式...\n")
        for slug in sorted(by_page):
            entries = by_page[slug]
            print(f"\n{'='*60}")
            print(f"📄 {slug}.md ({len(entries)} 条)")
            print(f"{'='*60}")
            for lineno, name, reason in entries:
                print(f"  行 {lineno}: [[{name}]]  ← {reason}")
            resp = input("修正此页？(y/n/q): ").strip().lower()
            if resp == 'q':
                break
            if resp == 'y':
                filepath = resolve_page_file(PAGES, slug)
                text = filepath.read_text(encoding='utf-8')
                lines = text.split('\n')
                fix_count = 0
                for lineno, name, reason in entries:
                    line = lines[lineno - 1]
                    # Show current line and ask for replacement
                    print(f"\n    原文: {line.strip()}")
                    replacement = input(f"    [[{name}]] → [[")
                    if replacement.strip():
                        new = line.replace(f'[[{name}]]', f'[[{replacement.strip()}]]')
                        lines[lineno - 1] = new
                        fix_count += 1
                        print(f"    修正: [[{name}]] → [[{replacement.strip()}]]")
                    else:
                        print(f"    跳过: [[{name}]]")
                if fix_count > 0:
                    filepath.write_text('\n'.join(lines), encoding='utf-8')
                    print(f"  ✓ {slug}.md: 修正 {fix_count} 条")
                else:
                    print(f"  - {slug}.md: 未作修改")

    print("\n手动修复：python3 wiki/scripts/edit_page.py <slug> <fix_file> --allow-shrink --summary '...'")


if __name__ == '__main__':
    main()
