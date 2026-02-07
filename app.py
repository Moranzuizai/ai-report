import streamlit as st
import pandas as pd
import os
import re
import json
import datetime

# --- 页面配置 ---
st.set_page_config(
    page_title="AI课堂周报生成器", 
    page_icon="📊",
    layout="wide"
)

# --- 标题 ---
st.title("📊 AI课堂教学数据分析工具")
st.markdown("""
**使用说明：**
1. 点击下方按钮上传Excel或CSV表格（需包含“周”、“课时数”、“出勤率”等列）。
2. 系统会自动分析并生成包含 **详细表格** 和 **趋势图** 的完整 HTML 报表。
3. 点击下载按钮保存到本地。
""")

# --- 辅助函数 ---
def natural_sort_key(s):
    if not isinstance(s, str): s = str(s)
    trans_map = {'七': '07', '八': '08', '九': '09', '高一': '10', '高二': '11', '高三': '12'}
    s_temp = s
    for k, v in trans_map.items():
        if k in s_temp and ('级' in s_temp or '年' in s_temp):
            s_temp = s_temp.replace(k, v)
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s_temp)]

def clean_percentage(x):
    if pd.isna(x) or x == '': return 0.0
    x_str = str(x).strip()
    if '%' in x_str:
        try: return float(x_str.rstrip('%')) / 100
        except: return 0.0
    else:
        try: return float(x_str)
        except: return 0.0

def get_grade(class_name):
    class_str = str(class_name)
    match = re.search(r'(.*?级)', class_str)
    if match: return match.group(1)
    if '七' in class_str: return '七年级'
    if '八' in class_str: return '八年级'
    if '九' in class_str: return '九年级'
    return "其他"

def weighted_avg(x, col, w_col='课时数'):
    try:
        w_sum = x[w_col].sum()
        if w_sum == 0: return 0
        return (x[col] * x[w_col]).sum() / w_sum
    except ZeroDivisionError: return 0

def get_trend_html(current, previous, is_percent=False):
    if previous is None or previous == 0: return ""
    diff = current - previous
    if abs(diff) < 0.0001: return '<span style="color:#999;font-size:14px;">(持平)</span>'
    symbol = "↑" if diff > 0 else "↓"
    color = "#2ecc71" if diff > 0 else "#e74c3c"
    diff_str = f"{abs(diff)*100:.1f}%" if is_percent else f"{int(abs(diff))}"
    return f'<span style="color:{color};font-weight:bold;">{symbol} {diff_str}</span>'

# --- 核心逻辑 ---
uploaded_file = st.file_uploader("请上传表格文件", type=['xlsx', 'xls', 'csv'])

if uploaded_file is not None:
    try:
        # 读取文件
        if uploaded_file.name.endswith('.csv'):
            try: df = pd.read_csv(uploaded_file, encoding='utf-8')
            except: df = pd.read_csv(uploaded_file, encoding='gbk')
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success(f"✅ 成功读取文件：{uploaded_file.name}")
        
        # --- 数据处理 ---
        df = df.fillna(0)
        cols_map = {}
        if '周' in df.columns: cols_map['time'] = '周'
        else: cols_map['time'] = df.columns[0]

        for c in df.columns:
            if '出勤' in c: cols_map['att'] = c
            elif '正确' in c: cols_map['corr'] = c
            elif '微课' in c: cols_map['micro'] = c
            elif '课时' in c and '数' in c: cols_map['hours'] = c
            elif '班级' in c: cols_map['class'] = c
            elif '学科' in c: cols_map['subject'] = c
        
        # 简单兜底
        if 'class' not in cols_map: cols_map['class'] = '班级名称'
        if 'hours' not in cols_map: cols_map['hours'] = '课时数'
        if 'att' not in cols_map: cols_map['att'] = '课时平均出勤率'
        if 'corr' not in cols_map: cols_map['corr'] = '题目正确率'

        for k in ['att', 'corr', 'micro']:
            if k in cols_map and cols_map[k] in df.columns:
                df[cols_map[k]] = df[cols_map[k]].apply(clean_percentage)
        
        time_col = cols_map['time']
        df = df[df[time_col].astype(str) != '合计']
        all_periods = [str(x) for x in df[time_col].unique()]
        try: all_periods.sort(key=lambda x: natural_sort_key(x))
        except: all_periods.sort()
        
        target_week = all_periods[-1]
        prev_week = all_periods[-2] if len(all_periods) > 1 else None
        
        df_curr = df[df[time_col].astype(str) == target_week].copy()
        df_prev = df[df[time_col].astype(str) == prev_week].copy() if prev_week else None
        df_curr['年级'] = df_curr[cols_map['class']].apply(get_grade)
        
        # 计算指标
        def calc_metrics(d):
            if d is None or d.empty: return None
            return {
                'hours': int(d[cols_map['hours']].sum()),
                'att': weighted_avg(