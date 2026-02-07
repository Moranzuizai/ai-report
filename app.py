import streamlit as st
import pandas as pd
import os
import re
import json

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
2. 系统会自动分析并生成 HTML 报表。
3. 点击下载按钮保存到本地。
""")

# --- 辅助函数 (保持不变) ---
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
                'att': weighted_avg(d, cols_map['att'], cols_map['hours']),
                'corr': weighted_avg(d, cols_map['corr'], cols_map['hours'])
            }
        m_curr = calc_metrics(df_curr)
        m_prev = calc_metrics(df_prev)
        
        # HTML生成准备
        t_h = ""; t_a = ""; t_c = ""
        if m_prev:
            t_h = get_trend_html(m_curr['hours'], m_prev['hours'], False)
            t_a = get_trend_html(m_curr['att'], m_prev['att'], True)
            t_c = get_trend_html(m_curr['corr'], m_prev['corr'], True)
            
        # 班级详情
        class_stats = df_curr.groupby(['年级', cols_map['class']]).apply(
            lambda x: pd.Series({
                '课时数': int(x[cols_map['hours']].sum()),
                '出勤率': weighted_avg(x, cols_map['att'], cols_map['hours']),
                '题目正确率': weighted_avg(x, cols_map['corr'], cols_map['hours']),
                '主要学科': ','.join(x[cols_map['subject']].astype(str).unique()) if 'subject' in cols_map else '-'
            })
        ).reset_index()
        class_stats['key'] = class_stats.apply(lambda r: (natural_sort_key(r['年级']), natural_sort_key(r[cols_map['class']])), axis=1)
        chart_df = class_stats.sort_values(by='key')
        
        # 图表JSON
        c_cats = json.dumps([str(x) for x in chart_df[cols_map['class']].tolist()], ensure_ascii=False)
        c_hours = json.dumps(chart_df['课时数'].tolist())
        c_att = json.dumps([round(x*100, 1) for x in chart_df['出勤率'].tolist()])
        c_corr = json.dumps([round(x*100, 1) for x in chart_df['题目正确率'].tolist()])
        
        # 历史趋势
        hist_stats = df.groupby(time_col).apply(
            lambda x: pd.Series({
                '课时数': int(x[cols_map['hours']].sum()),
                '出勤率': weighted_avg(x, cols_map['att'], cols_map['hours']),
                '题目正确率': weighted_avg(x, cols_map['corr'], cols_map['hours'])
            })
        ).reset_index()
        hist_stats['sk'] = hist_stats[time_col].apply(lambda x: natural_sort_key(str(x)))
        hist_stats = hist_stats.sort_values(by='sk')
        
        t_dates = json.dumps([str(x) for x in hist_stats[time_col].tolist()], ensure_ascii=False)
        t_hours = json.dumps(hist_stats['课时数'].tolist())
        t_att = json.dumps([round(x*100, 1) for x in hist_stats['出勤率'].tolist()])
        t_corr = json.dumps([round(x*100, 1) for x in hist_stats['题目正确率'].tolist()])

        # HTML 模板
        # 注意：这里使用 CDN 引用 ECharts，无需本地文件
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
        <style>
            body {{ font-family: "Microsoft YaHei", sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f4f6f9; }}
            .card {{ background: #fff; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
            .kpi {{ display: flex; justify-content: space-around; text-align: center; }}
            .kpi div strong {{ font-size: 30px; color: #2980b9; display: block; }}
            .highlight-box {{ padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .success-box {{ background: #d4edda; color: #155724; border-left: 5px solid #28a745; }}
            .warning-box {{ background: #fff3cd; color: #856404; border-left: 5px solid #ffc107; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ background: #eee; padding: 10px; }} td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: center; }}
            .alert {{ color: #e74c3c; font-weight: bold; }} .good {{ color: #27ae60; }}
            .chart {{ height: 400px; width: 100%; }}
        </style>
        </head>
        <body>
            <h2 style="text-align:center">AI课堂教学数据分析</h2>
            <div style="text-align:center;color:#666;margin-bottom:20px">统计周期: {target_week} {f'(对比: {prev_week})' if prev_week else ''}</div>
            <div class="card">
                <h3>📊 本周核心指标</h3>
                <div class="kpi">
                    <div><strong>{m_curr['hours']}{t_h}</strong>总课时</div>
                    <div><strong>{m_curr['att']*100:.1f}%{t_a}</strong>出勤率</div>
                    <div><strong>{m_curr['corr']*100:.1f}%{t_c}</strong>正确率</div>
                </div>
            </div>
            <div class="card"><h3>🏫 班级效能分析</h3><div id="c1" class="chart"></div></div>
            <div class="card"><h3>📈 历史趋势</h3><div id="c2" class="chart"></div></div>
            <script>
                var c1 = echarts.init(document.getElementById('c1'));
                c1.setOption({{
                    tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                    xAxis: {{type:'category', data:{c_cats}, axisLabel:{{rotate:30}}}},
                    yAxis: [{{type:'value',name:'课时'}}, {{type:'value',name:'%',max:100}}],
                    series: [
                        {{type:'bar',name:'课时数',data:{c_hours},itemStyle:{{color:'#3498db'}}}},
                        {{type:'line',yAxisIndex:1,name:'出勤率',data:{c_att},itemStyle:{{color:'#2ecc71'}}}},
                        {{type:'line',yAxisIndex:1,name:'正确率',data:{c_corr},itemStyle:{{color:'#e74c3c'}}}}
                    ]
                }});
                var c2 = echarts.init(document.getElementById('c2'));
                c2.setOption({{
                    tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                    xAxis: {{type:'category', data:{t_dates}}},
                    yAxis: [{{type:'value',name:'课时'}}, {{type:'value',name:'%',max:100}}],
                    series: [
                        {{type:'bar',name:'课时数',data:{t_hours},itemStyle:{{color:'#9b59b6'}}}},
                        {{type:'line',yAxisIndex:1,name:'出勤率',data:{t_att},itemStyle:{{color:'#2ecc71'}}}},
                        {{type:'line',yAxisIndex:1,name:'正确率',data:{t_corr},itemStyle:{{color:'#e74c3c'}}}}
                    ]
                }});
                window.onresize = function(){{c1.resize();c2.resize();}};
            </script>
        </body></html>
        """
        
        # --- 下载按钮 ---
        base_name = os.path.splitext(uploaded_file.name)[0]
        st.download_button(
            label="📥 点击下载分析报表 (HTML)",
            data=html_content,
            file_name=f"{base_name}_分析报表.html",
            mime="text/html"
        )
        
    except Exception as e:
        st.error(f"发生错误：{str(e)}")