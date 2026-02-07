import streamlit as st
import pandas as pd
import os
import re
import json
import datetime

# ==========================================
# 1. 页面基础配置
# ==========================================
st.set_page_config(
    page_title="AI课堂周报生成器", 
    page_icon="📊",
    layout="wide"
)

# ==========================================
# 2. 🔐 登录保护逻辑 (放在最前面)
# ==========================================
def check_password():
    """密码验证函数"""
    # 在侧边栏显示输入框
    password = st.sidebar.text_input("🔒 请输入访问密码", type="password")
    
    # --- 请在这里修改您的密码 ---
    # 目前设置为 a123456
    if password == "a123456":
        return True
    return False

# 如果密码不对，停止运行后续代码
if not check_password():
    st.warning("⚠️ 请在左侧输入密码以访问系统。")
    st.info("如果您不知道密码，请联系管理员。")
    st.stop()  # ⛔️ 停止执行

# ==========================================
# 3. 主界面内容
# ==========================================
st.title("📊 AI课堂教学数据分析工具")
st.markdown("""
**使用说明：**
1. 点击下方按钮上传Excel或CSV表格（需包含“周”、“课时数”、“出勤率”等列）。
2. 系统会自动分析并生成包含 **详细表格** 和 **趋势图** 的完整 HTML 报表。
3. 点击下载按钮保存到本地。
""")

# ==========================================
# 4. 辅助函数定义
# ==========================================
def natural_sort_key(s):
    """自然排序算法 (处理中文数字和混合排序)"""
    if not isinstance(s, str): s = str(s)
    trans_map = {
        '七': '07', '八': '08', '九': '09', 
        '高一': '10', '高二': '11', '高三': '12',
        '初一': '07', '初二': '08', '初三': '09'
    }
    s_temp = s
    for k, v in trans_map.items():
        # 仅替换作为年级的中文数字
        if k in s_temp and ('级' in s_temp or '年' in s_temp):
            s_temp = s_temp.replace(k, v)
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s_temp)]

def clean_percentage(x):
    """清洗百分比数据"""
    if pd.isna(x) or x == '': return 0.0
    x_str = str(x).strip()
    if '%' in x_str:
        try: return float(x_str.rstrip('%')) / 100
        except: return 0.0
    else:
        try: return float(x_str)
        except: return 0.0

def get_grade(class_name):
    """从班级名提取年级"""
    class_str = str(class_name)
    match = re.search(r'(.*?级)', class_str)
    if match: return match.group(1)
    if '七' in class_str: return '七年级'
    if '八' in class_str: return '八年级'
    if '九' in class_str: return '九年级'
    if '高' in class_str: return '高中部'
    return "其他"

def weighted_avg(x, col, w_col='课时数'):
    """计算加权平均值"""
    try:
        w_sum = x[w_col].sum()
        if w_sum == 0: return 0
        return (x[col] * x[w_col]).sum() / w_sum
    except ZeroDivisionError: return 0

def get_trend_html(current, previous, is_percent=False):
    """生成趋势红绿箭头HTML"""
    if previous is None or previous == 0: return ""
    diff = current - previous
    if abs(diff) < 0.0001: return '<span style="color:#999;font-size:14px;">(持平)</span>'
    
    symbol = "↑" if diff > 0 else "↓"
    color = "#2ecc71" if diff > 0 else "#e74c3c" # 绿涨红跌
    
    if is_percent:
        diff_str = f"{abs(diff)*100:.1f}%"
    else:
        diff_str = f"{int(abs(diff))}"
        
    return f'<span style="color:{color};font-weight:bold;">{symbol} {diff_str}</span>'

# ==========================================
# 5. 核心逻辑：文件处理与生成
# ==========================================
uploaded_file = st.file_uploader("请上传表格文件", type=['xlsx', 'xls', 'csv'])

if uploaded_file is not None:
    try:
        # --- 读取文件 ---
        if uploaded_file.name.endswith('.csv'):
            try: df = pd.read_csv(uploaded_file, encoding='utf-8')
            except: df = pd.read_csv(uploaded_file, encoding='gbk')
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success(f"✅ 成功读取文件：{uploaded_file.name}")
        
        # --- 数据清洗与映射 ---
        df = df.fillna(0)
        cols_map = {}
        # 自动寻找时间列
        if '周' in df.columns: cols_map['time'] = '周'
        else: cols_map['time'] = df.columns[0] # 默认第一列

        # 映射关键列
        for c in df.columns:
            if '出勤' in c: cols_map['att'] = c
            elif '正确' in c: cols_map['corr'] = c
            elif '微课' in c: cols_map['micro'] = c
            elif '课时' in c and '数' in c: cols_map['hours'] = c
            elif '班级' in c: cols_map['class'] = c
            elif '学科' in c: cols_map['subject'] = c
        
        # 兜底默认值
        if 'class' not in cols_map: cols_map['class'] = '班级名称'
        if 'hours' not in cols_map: cols_map['hours'] = '课时数'
        if 'att' not in cols_map: cols_map['att'] = '课时平均出勤率'
        if 'corr' not in cols_map: cols_map['corr'] = '题目正确率'

        # 转换百分比列
        for k in ['att', 'corr', 'micro']:
            if k in cols_map and cols_map[k] in df.columns:
                df[cols_map[k]] = df[cols_map[k]].apply(clean_percentage)
        
        # --- 时间段处理 ---
        time_col = cols_map['time']
        # 过滤合计行
        df = df[df[time_col].astype(str) != '合计']
        
        # 获取所有时间段并排序
        all_periods = [str(x) for x in df[time_col].unique()]
        try: all_periods.sort(key=lambda x: natural_sort_key(x))
        except: all_periods.sort()
        
        if not all_periods:
            st.error("未找到有效的时间/周次数据，请检查表格第一列。")
            st.stop()

        target_week = all_periods[-1] # 最新
        prev_week = all_periods[-2] if len(all_periods) > 1 else None # 上周
        
        # 切分数据
        df_curr = df[df[time_col].astype(str) == target_week].copy()
        df_prev = df[df[time_col].astype(str) == prev_week].copy() if prev_week else None
        df_curr['年级'] = df_curr[cols_map['class']].apply(get_grade)
        
        # --- 计算核心指标 ---
        def calc_metrics(d):
            if d is None or d.empty: return None
            return {
                'hours': int(d[cols_map['hours']].sum()),
                'att': weighted_avg(d, cols_map['att'], cols_map['hours']),
                'corr': weighted_avg(d, cols_map['corr'], cols_map['hours'])
            }
        m_curr = calc_metrics(df_curr)
        m_prev = calc_metrics(df_prev)
        
        # --- 生成趋势 HTML 片段 ---
        t_h = ""; t_a = ""; t_c = ""
        if m_prev:
            t_h = get_trend_html(m_curr['hours'], m_prev['hours'], False)
            t_a = get_trend_html(m_curr['att'], m_prev['att'], True)
            t_c = get_trend_html(m_curr['corr'], m_prev['corr'], True)
            
        # --- 班级详细数据聚合 ---
        class_stats = df_curr.groupby(['年级', cols_map['class']]).apply(
            lambda x: pd.Series({
                '课时数': int(x[cols_map['hours']].sum()),
                '出勤率': weighted_avg(x, cols_map['att'], cols_map['hours']),
                '微课完成率': weighted_avg(x, cols_map['micro'], cols_map['hours']) if 'micro' in cols_map else 0,
                '题目正确率': weighted_avg(x, cols_map['corr'], cols_map['hours']),
                '主要学科': ','.join(x[cols_map['subject']].astype(str).unique()) if 'subject' in cols_map else '-'
            })
        ).reset_index()
        
        # 排序
        class_stats['key'] = class_stats.apply(lambda r: (natural_sort_key(r['年级']), natural_sort_key(r[cols_map['class']])), axis=1)
        chart_df = class_stats.sort_values(by='key')
        
        # --- 图表1数据 (JSON) ---
        c_cats = json.dumps([str(x) for x in chart_df[cols_map['class']].tolist()], ensure_ascii=False)
        c_hours = json.dumps(chart_df['课时数'].tolist())
        c_att = json.dumps([round(x*100, 1) for x in chart_df['出勤率'].tolist()])
        c_corr = json.dumps([round(x*100, 1) for x in chart_df['题目正确率'].tolist()])
        
        # --- 智能标杆与预警 ---
        best_class = class_stats.sort_values(by=['课时数', '题目正确率'], ascending=False).iloc[0]
        focus_classes = class_stats[(class_stats['出勤率'] > m_curr['att']) & (class_stats['题目正确率'] < m_curr['corr'])]
        focus_row = focus_classes.iloc[0] if not focus_classes.empty else None

        best_html = f'<div class="highlight-box success-box">🏆 <strong>综合标杆：{best_class[cols_map["class"]]}</strong> (课时:{int(best_class["课时数"])} / 正确率:{best_class["题目正确率"]*100:.1f}%)</div>'
        
        focus_html = ""
        if focus_row is not None:
            focus_html = f'<div class="highlight-box warning-box">⚠️ <strong>重点关注：{focus_row[cols_map["class"]]}</strong> (出勤:{focus_row["出勤率"]*100:.1f}% 正常，但正确率 {focus_row["题目正确率"]*100:.1f}% 偏低)</div>'
        
        # --- 生成详细表格 HTML ---
        tables_html = ""
        sorted_grades = sorted(class_stats['年级'].unique(), key=lambda x: natural_sort_key(x))
        for grade in sorted_grades:
            g_df = class_stats[class_stats['年级'] == grade].sort_values(by=['课时数', '题目正确率'], ascending=False)
            tables_html += f"<h3>{grade}</h3><table><thead><tr><th>班级</th><th>主要学科</th><th>课时数</th><th>出勤率</th><th>微课完成率</th><th>题目正确率</th></tr></thead><tbody>"
            for _, row in g_df.iterrows():
                att_cls = 'alert' if row['出勤率'] < m_curr['att'] else 'good'
                corr_cls = 'alert' if row['题目正确率'] < m_curr['corr'] else 'good'
                tables_html += f"""
                <tr>
                    <td><b>{row[cols_map['class']]}</b></td>
                    <td style="color:#999;font-size:12px;">{row['主要学科']}</td>
                    <td>{int(row['课时数'])}</td>
                    <td class="{att_cls}">{row['出勤率']*100:.1f}%</td>
                    <td>{row['微课完成率']*100:.1f}%</td>
                    <td class="{corr_cls}">{row['题目正确率']*100:.1f}%</td>
                </tr>"""
            tables_html += "</tbody></table>"

        # --- 全历史趋势数据聚合 ---
        hist_stats = df.groupby(time_col).apply(
            lambda x: pd.Series({
                '课时数': int(x[cols_map['hours']].sum()),
                '出勤率': weighted_avg(x, cols_map['att'], cols_map['hours']),
                '题目正确率': weighted_avg(x, cols_map['corr'], cols_map['hours'])
            })
        ).reset_index()
        hist_stats['sk'] = hist_stats[time_col].apply(lambda x: natural_sort_key(str(x)))
        hist_stats = hist_stats.sort_values(by='sk')
        
        # --- 图表2数据 (JSON) ---
        t_dates = json.dumps([str(x) for x in hist_stats[time_col].tolist()], ensure_ascii=False)
        t_hours = json.dumps(hist_stats['课时数'].tolist())
        t_att = json.dumps([round(x*100, 1) for x in hist_stats['出勤率'].tolist()])
        t_corr = json.dumps([round(x*100, 1) for x in hist_stats['题目正确率'].tolist()])

        # ==========================================
        # 6. 生成最终 HTML 报告
        # ==========================================
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
            .highlight-box {{ padding: 15px; margin: 10px 0; border-radius: 5px; font-size: 14px; }}
            .success-box {{ background: #d4edda; color: #155724; border-left: 5px solid #28a745; }}
            .warning-box {{ background: #fff3cd; color: #856404; border-left: 5px solid #ffc107; }}
            
            /* 表格样式 */
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
            th {{ background: #eee; padding: 10px; border-bottom: 2px solid #ddd; }} 
            td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: center; }}
            .alert {{ color: #e74c3c; font-weight: bold; }} 
            .good {{ color: #27ae60; }}
            
            .chart {{ height: 400px; width: 100%; }}
            .footer {{ text-align:center; color:#999; font-size:12px; margin-top:20px; }}
        </style>
        </head>
        <body>
            <h2 style="text-align:center">AI课堂教学数据分析周报</h2>
            <div style="text-align:center;color:#666;margin-bottom:20px">
                统计周期: <b>{target_week}</b> 
                {f'<span style="font-size:12px">(对比: {prev_week})</span>' if prev_week else ''}
            </div>
            
            <div class="card">
                <h3>📊 本周核心指标</h3>
                <div class="kpi">
                    <div><strong>{m_curr['hours']}{t_h}</strong>总课时</div>
                    <div><strong>{m_curr['att']*100:.1f}%{t_a}</strong>出勤率</div>
                    <div><strong>{m_curr['corr']*100:.1f}%{t_c}</strong>正确率</div>
                </div>
                {best_html}
                {focus_html}
            </div>
            
            <div class="card">
                <h3>🏫 班级效能分析</h3>
                <div id="c1" class="chart"></div>
            </div>
            
            <div class="card">
                <h3>📋 详细数据明细</h3>
                <p style="text-align:right;color:#999;font-size:12px">* 红色数字表示低于全校均值</p>
                {tables_html}
            </div>
            
            <div class="card">
                <h3>📈 全周期历史趋势</h3>
                <div id="c2" class="chart"></div>
            </div>
            
            <div class="footer">Generated by AI Agent (Web Edition)</div>

            <script>
                // 图表1：班级画像
                var c1 = echarts.init(document.getElementById('c1'));
                c1.setOption({{
                    tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                    grid: {{left:'3%', right:'4%', bottom:'10%', containLabel:true}},
                    xAxis: {{type:'category', data:{c_cats}, axisLabel:{{rotate:30, interval:0}}}},
                    yAxis: [{{type:'value',name:'课时'}}, {{type:'value',name:'%',max:100}}],
                    series: [
                        {{type:'bar',name:'课时数',data:{c_hours},itemStyle:{{color:'#3498db'}}}},
                        {{type:'line',yAxisIndex:1,name:'出勤率',data:{c_att},itemStyle:{{color:'#2ecc71'}}}},
                        {{type:'line',yAxisIndex:1,name:'正确率',data:{c_corr},itemStyle:{{color:'#e74c3c'}}}}
                    ]
                }});

                // 图表2：历史趋势
                var c2 = echarts.init(document.getElementById('c2'));
                c2.setOption({{
                    tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                    grid: {{left:'3%', right:'4%', bottom:'10%', containLabel:true}},
                    xAxis: {{type:'category', data:{t_dates}}},
                    yAxis: [{{type:'value',name:'课时'}}, {{type:'value',name:'%',max:100}}],
                    series: [
                        {{type:'bar',name:'课时数',data:{t_hours},itemStyle:{{color:'#9b59b6'}}}},
                        {{type:'line',yAxisIndex:1,name:'出勤率',data:{t_att},itemStyle:{{color:'#2ecc71'}}}},
                        {{type:'line',yAxisIndex:1,name:'正确率',data:{t_corr},itemStyle:{{color:'#e74c3c'}}}}
                    ]
                }});
                
                window.onresize = function(){{ c1.resize(); c2.resize(); }};
            </script>
        </body></html>
        """
        
        # --- 下载按钮 ---
        # 获取源文件名(不含后缀)
        base_name = os.path.splitext(uploaded_file.name)[0]
        # 按钮
        st.download_button(
            label="📥 点击下载完整分析报表 (HTML)",
            data=html_content,
            file_name=f"{base_name}_分析报表.html",
            mime="text/html"
        )
        
    except Exception as e:
        st.error(f"发生错误：{str(e)}")