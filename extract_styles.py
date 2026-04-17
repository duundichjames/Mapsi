#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import csv
from pathlib import Path
from collections import defaultdict

BASE_PATH = Path('/Users/JaesungJamesPark/Dropbox/works/2025/works/빅데이터핀테크/works/w-md2hwp/mapsi')
OUTPUT_DIR = BASE_PATH / 'spec' / 'extracted'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLES = [
    ('base', 'samples/base'),
    ('01_headings', 'samples/incremental/01_headings'),
    ('02_bullet_list', 'samples/incremental/02_bullet_list'),
    ('03_ordered_list', 'samples/incremental/03_ordered_list'),
    ('04_blockquote_code', 'samples/incremental/04_blockquote_code'),
    ('05_table', 'samples/incremental/05_table'),
    ('06_figure', 'samples/incremental/06_figure'),
    ('07_footnote', 'samples/incremental/07_footnote'),
    ('08_references', 'samples/incremental/08_references'),
    ('09_equations', 'samples/incremental/09_equations'),
]

NAMESPACES = {
    'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
    'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
}

def extract_styles(xml_file):
    """Extract style definitions from header.xml"""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    styles = []
    for style in root.findall('.//hh:style', NAMESPACES):
        style_id = style.get('id')
        style_name = style.get('name', '')
        style_eng_name = style.get('engName', '')
        style_type = style.get('type', '')
        para_pr_ref = style.get('paraPrIDRef', '')
        char_pr_ref = style.get('charPrIDRef', '')

        styles.append({
            'id': style_id,
            'name': style_name,
            'engName': style_eng_name,
            'type': style_type,
            'paraPrIDRef': para_pr_ref,
            'charPrIDRef': char_pr_ref,
        })

    return styles

def extract_para_pr(xml_file):
    """Extract paragraph properties"""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    para_prs = []
    for para_pr in root.findall('.//hh:paraPr', NAMESPACES):
        para_id = para_pr.get('id')
        tab_pr_ref = para_pr.get('tabPrIDRef', '')
        condense = para_pr.get('condense', '')
        snap_to_grid = para_pr.get('snapToGrid', '')

        # Get alignment
        align_elem = para_pr.find('.//hh:align', NAMESPACES)
        h_align = align_elem.get('horizontal', '') if align_elem is not None else ''

        # Get margin
        margin_elem = para_pr.find('.//hh:margin', NAMESPACES)
        left_margin = ''
        if margin_elem is not None:
            left_child = margin_elem.find('hc:left', NAMESPACES)
            if left_child is not None:
                left_margin = left_child.get('value', '')

        para_prs.append({
            'id': para_id,
            'tabPrIDRef': tab_pr_ref,
            'condense': condense,
            'snapToGrid': snap_to_grid,
            'horizontal_align': h_align,
            'left_margin': left_margin,
        })

    return para_prs

def extract_char_pr(xml_file):
    """Extract character properties"""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    char_prs = []
    for char_pr in root.findall('.//hh:charPr', NAMESPACES):
        char_id = char_pr.get('id')
        height = char_pr.get('height', '')
        text_color = char_pr.get('textColor', '')
        shade_color = char_pr.get('shadeColor', '')
        border_fill_ref = char_pr.get('borderFillIDRef', '')

        # Get font reference
        font_ref = char_pr.find('.//hh:fontRef', NAMESPACES)
        hangul_font = font_ref.get('hangul', '') if font_ref is not None else ''

        char_prs.append({
            'id': char_id,
            'height': height,
            'textColor': text_color,
            'shadeColor': shade_color,
            'borderFillIDRef': border_fill_ref,
            'hangul_font': hangul_font,
        })

    return char_prs

def extract_numbering(xml_file):
    """Extract numbering definitions"""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    numberings = []
    for numbering in root.findall('.//hh:numbering', NAMESPACES):
        num_id = numbering.get('id')
        start = numbering.get('start', '')

        # Count para heads
        para_heads = numbering.findall('.//hh:paraHead', NAMESPACES)
        para_head_count = len(para_heads)

        # Get first paraHead info
        if para_heads:
            first_head = para_heads[0]
            num_format = first_head.get('numFormat', '')
            text_offset = first_head.get('textOffset', '')
        else:
            num_format = ''
            text_offset = ''

        numberings.append({
            'id': num_id,
            'start': start,
            'paraHeadCount': para_head_count,
            'numFormat': num_format,
            'textOffset': text_offset,
        })

    return numberings

def extract_border_fill(xml_file):
    """Extract border and fill definitions"""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    border_fills = []
    for border_fill in root.findall('.//hh:borderFill', NAMESPACES):
        bf_id = border_fill.get('id')
        three_d = border_fill.get('threeD', '')
        shadow = border_fill.get('shadow', '')
        center_line = border_fill.get('centerLine', '')

        # Get border info
        left_border = border_fill.find('.//hh:leftBorder', NAMESPACES)
        left_type = left_border.get('type', '') if left_border is not None else ''
        left_width = left_border.get('width', '') if left_border is not None else ''

        border_fills.append({
            'id': bf_id,
            'threeD': three_d,
            'shadow': shadow,
            'centerLine': center_line,
            'leftBorderType': left_type,
            'leftBorderWidth': left_width,
        })

    return border_fills

def write_csv(data, fieldnames, output_file):
    """Write data to CSV file"""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

# Extract and aggregate data
all_styles = defaultdict(list)
all_para_prs = defaultdict(list)
all_char_prs = defaultdict(list)
all_numberings = defaultdict(list)
all_border_fills = defaultdict(list)

for sample_name, sample_path in SAMPLES:
    xml_file = BASE_PATH / sample_path / 'unpacked' / 'Contents' / 'header.xml'

    if not xml_file.exists():
        print(f"⚠️ Missing: {xml_file}")
        continue

    print(f"📄 Processing {sample_name}...")

    # Extract styles
    for style in extract_styles(xml_file):
        style['sample'] = sample_name
        all_styles[sample_name].append(style)

    # Extract paragraph properties
    for para_pr in extract_para_pr(xml_file):
        para_pr['sample'] = sample_name
        all_para_prs[sample_name].append(para_pr)

    # Extract character properties
    for char_pr in extract_char_pr(xml_file):
        char_pr['sample'] = sample_name
        all_char_prs[sample_name].append(char_pr)

    # Extract numbering
    for numbering in extract_numbering(xml_file):
        numbering['sample'] = sample_name
        all_numberings[sample_name].append(numbering)

    # Extract border fill
    for border_fill in extract_border_fill(xml_file):
        border_fill['sample'] = sample_name
        all_border_fills[sample_name].append(border_fill)

# Write CSV files
print("\n📋 Writing CSV files...")

# Styles CSV
styles_data = []
for sample_name in [s[0] for s in SAMPLES]:
    styles_data.extend(all_styles.get(sample_name, []))

write_csv(
    styles_data,
    ['sample', 'id', 'name', 'engName', 'type', 'paraPrIDRef', 'charPrIDRef'],
    OUTPUT_DIR / 'styles.csv'
)
print("✓ styles.csv")

# Paragraph Properties CSV
para_pr_data = []
for sample_name in [s[0] for s in SAMPLES]:
    para_pr_data.extend(all_para_prs.get(sample_name, []))

write_csv(
    para_pr_data,
    ['sample', 'id', 'tabPrIDRef', 'condense', 'snapToGrid', 'horizontal_align', 'left_margin'],
    OUTPUT_DIR / 'paraPr.csv'
)
print("✓ paraPr.csv")

# Character Properties CSV
char_pr_data = []
for sample_name in [s[0] for s in SAMPLES]:
    char_pr_data.extend(all_char_prs.get(sample_name, []))

write_csv(
    char_pr_data,
    ['sample', 'id', 'height', 'textColor', 'shadeColor', 'borderFillIDRef', 'hangul_font'],
    OUTPUT_DIR / 'charPr.csv'
)
print("✓ charPr.csv")

# Numbering CSV
numbering_data = []
for sample_name in [s[0] for s in SAMPLES]:
    numbering_data.extend(all_numberings.get(sample_name, []))

write_csv(
    numbering_data,
    ['sample', 'id', 'start', 'paraHeadCount', 'numFormat', 'textOffset'],
    OUTPUT_DIR / 'numbering.csv'
)
print("✓ numbering.csv")

# Border Fill CSV
border_fill_data = []
for sample_name in [s[0] for s in SAMPLES]:
    border_fill_data.extend(all_border_fills.get(sample_name, []))

write_csv(
    border_fill_data,
    ['sample', 'id', 'threeD', 'shadow', 'centerLine', 'leftBorderType', 'leftBorderWidth'],
    OUTPUT_DIR / 'borderFill.csv'
)
print("✓ borderFill.csv")

print(f"\n✅ 완료! CSV 파일이 {OUTPUT_DIR}에 저장되었습니다.")
