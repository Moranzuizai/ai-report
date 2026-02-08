import streamlit as st
import pandas as pd
import os
import re
import json
import datetime
import streamlit.components.v1 as components

# ==========================================
# 0. 全局配置与文件路径
# ==========================================
st.set_page_config(
    page_title="AI课堂周报生成器", 
    page_icon="📊",
    layout="wide"
)

LOG_FILE = "access_log.csv"
FEEDBACK_FILE = "feedback_log.csv"
CONFIG_FILE = "config.json"

# ==========================================
# 1. 核心工具函数 (密码管理、日志记录)
# ==========================================

def load_config():
    """读取配置文件"""
    if not os.path.exists(CONFIG_FILE):
        # 如果文件不存在，创建默认配置
        default_config = {"admin_password": "199266", "user_password": "a123456"}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f)
        return default_config
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def log_access(event_type="用户登录"):
    """记录访问日志"""
    now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not os.path.exists(LOG_FILE):
        df_log = pd.DataFrame(columns=["访问时间", "事件"])
        df_log.to_csv(LOG_FILE, index=False)
    
    new_entry = pd.DataFrame([{"访问时间": now_time, "事件": event_type}])
    new_entry.to_csv(LOG_FILE, mode='a', header=False, index=False)

def save_feedback(rating, comment):
    """保存用户评价和建议"""
    now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not os.path.exists(FEEDBACK_FILE):
        df = pd.DataFrame(columns=["时间", "评价", "建议"])
        df.to_csv(FEEDBACK_FILE, index=False)
    
    new_entry = pd.DataFrame([{"时间": now_time, "评价": rating, "建议": comment}])
    new_entry.to_csv(FEEDBACK_FILE, mode='a', header=False, index=False)

# ==========================================
# 2. 权限控制逻辑 (隐形管理员入口)
# ==========================================

# 加载配置
config = load_config()
ADMIN_PWD = config.get("admin_password", "199266")
USER_PWD = config.get("user_password", "123456")

def check_auth():
    """
    返回状态码：
    0: 未登录
    1: 普通用户
    2: 管理员
    """
    # 侧边栏统一入口
    password = st.sidebar.text_input("🔒 请输入访问密码", type="password")
    
    if password == ADMIN_PWD:
        return 2  # 管理员
    elif password == USER_PWD:
        if 'logged_in' not in st.session_state:
            log_access("普通用户登录")
            st.session_state['logged_in'] = True
        return 1  # 普通用户
    else:
        return 0  # 密码错误或未输入

auth_status = check_auth()

if auth_status == 0:
    st.warning("⚠️ 请在左侧输入密码以访问系统。")
    st.info("提示：输入密码进入功能")
    st.stop()

# ==========================================
# 3. 管理员后台 (当输入 199266 时显示)
# ==========================================
if auth_status == 2:
    st.sidebar.success("🔑 管理员已登录")
    st.title("🔧 管理员控制台")
    
    tab1, tab2, tab3 = st.tabs(["📝 访问日志", "💬 用户反馈", "⚙️ 系统设置"])
    
    with tab1:
        st.subheader("访问日志记录")
        if os.path.exists(LOG_FILE):
            df_log = pd.read_csv(LOG_FILE).sort_values(by="访问时间", ascending=False)
            st.dataframe(df_log, use_container_width=True)
            st.download_button("📥 下载日志", df_log.to_csv(index=False).encode('utf-8-sig'), "access_log.csv")
        else:
            st.info("暂无日志")
            
    with tab2:
        st.subheader("用户评价与建议")
        if os.path.exists(FEEDBACK_FILE):
            df_feed = pd.read_csv(FEEDBACK_FILE).sort_values(by="时间", ascending=False)
            st.dataframe(df_feed, use_container_width=True)
            st.download_button("📥 下载反馈", df_feed.to_csv(index=False).encode('utf-8-sig'), "feedback.csv")
        else:
            st.info("暂无反馈")
            
    with tab3:
        st.subheader("修改密码")
        col1, col2 = st.columns(2)
        with col1:
            new_user_pwd = st.text_input("设置新的【普通用户】密码", value=USER_PWD)
        with col2:
            new_admin_pwd = st.text_input("设置新的【管理员】密码", value=ADMIN_PWD)
            
        if st.button("💾 保存新密码"):
            config["user_password"] = new_user_pwd
            config["admin_password"] = new_admin_pwd
            save_config(config)
            st.success("密码已更新！请使用新密码重新登录。")
            
    st.stop() # 管理员界面结束，不显示下面的普通用户功能

# ==========================================
# 4. 普通用户界面 (当输入 123456 时显示)
# ==========================================
st.title("📊 AI课堂教学数据分析工具")
st.markdown("""
**使用说明：**
1. 上传表格 -> 2. 在线预览报表 -> 3. 下载或评价
""")

# --- 辅助函数定义 (保持不变) ---
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

# --- 文件上传与处理 ---
uploaded_file = st.file_uploader("请上传表格文件", type=['xlsx', 'xls', 'csv'])

if uploaded_file is not None:
    try:
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
            elif '微课' in c and '率' in c: cols_map['micro'] = c
            elif '课时' in c and '数' in c: cols_map['hours'] = c
            elif '班级' in c: cols_map['class'] = c
            elif '学科' in c: cols_map['subject'] = c
        
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
        
        if not all_periods:
            st.error("数据错误：未找到有效的时间/周次数据。")
            st.stop()

        target_week = all_periods[-1]
        prev_week = all_periods[-2] if len(all_periods) > 1 else None
        
        df_curr = df[df[time_col].astype(str) == target_week].copy()
        df_prev = df[df[time_col].astype(str) == prev_week].copy() if prev_week else None
        df_curr['年级'] = df_curr[cols_map['class']].apply(get_grade)
        
        def calc_metrics(d):
            if d is None or d.empty: return None
            return {
                'hours': int(d[cols_map['hours']].sum()),
                'att': weighted_avg(d, cols_map['att'], cols_map['hours']),
                'corr': weighted_avg(d, cols_map['corr'], cols_map['hours'])
            }
        m_curr = calc_metrics(df_curr)
        m_prev = calc_metrics(df_prev)
        
        t_h = ""; t_a = ""; t_c = ""
        if m_prev:
            t_h = get_trend_html(m_curr['hours'], m_prev['hours'], False)
            t_a = get_trend_html(m_curr['att'], m_prev['att'], True)
            t_c = get_trend_html(m_curr['corr'], m_prev['corr'], True)
            
        class_stats = df_curr.groupby(['年级', cols_map['class']]).apply(
            lambda x: pd.Series({
                '课时数': int(x[cols_map['hours']].sum()),
                '出勤率': weighted_avg(x, cols_map['att'], cols_map['hours']),
                '微课完成率': weighted_avg(x, cols_map['micro'], cols_map['hours']) if 'micro' in cols_map else 0,
                '题目正确率': weighted_avg(x, cols_map['corr'], cols_map['hours']),
                '主要学科': ','.join(x[cols_map['subject']].astype(str).unique()) if 'subject' in cols_map else '-'
            })
        ).reset_index()
        class_stats['key'] = class_stats.apply(lambda r: (natural_sort_key(r['年级']), natural_sort_key(r[cols_map['class']])), axis=1)
        chart_df = class_stats.sort_values(by='key')
        
        c_cats = json.dumps([str(x) for x in chart_df[cols_map['class']].tolist()], ensure_ascii=False)
        c_hours = json.dumps(chart_df['课时数'].tolist())
        c_att = json.dumps([round(x*100, 1) for x in chart_df['出勤率'].tolist()])
        c_corr = json.dumps([round(x*100, 1) for x in chart_df['题目正确率'].tolist()])
        
        best_class = class_stats.sort_values(by=['课时数', '题目正确率'], ascending=False).iloc[0]
        focus_classes = class_stats[(class_stats['出勤率'] > m_curr['att']) & (class_stats['题目正确率'] < m_curr['corr'])]
        focus_row = focus_classes.iloc[0] if not focus_classes.empty else None

        best_html = f'<div class="highlight-box success-box">🏆 <strong>综合标杆：{best_class[cols_map["class"]]}</strong> (课时:{int(best_class["课时数"])} / 正确率:{best_class["题目正确率"]*100:.1f}%)</div>'
        focus_html = ""
        if focus_row is not None:
            focus_html = f'<div class="highlight-box warning-box">⚠️ <strong>重点关注：{focus_row[cols_map["class"]]}</strong> (出勤:{focus_row["出勤率"]*100:.1f}% 正常，但正确率 {focus_row["题目正确率"]*100:.1f}% 偏低)</div>'
        
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

        # --- HTML 模板 ---
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
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
            th {{ background: #eee; padding: 10px; border-bottom: 2px solid #ddd; }} 
            td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: center; }}
            .alert {{ color: #e74c3c; font-weight: bold; }} .good {{ color: #27ae60; }}
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
                {best_html}{focus_html}
            </div>
            
            <div class="card"><h3>🏫 班级效能分析</h3><div id="c1" class="chart"></div></div>
            <div class="card"><h3>📋 详细数据明细</h3>
                <p style="text-align:right;color:#999;font-size:12px">* 红色数字表示低于全校均值</p>{tables_html}
            </div>
            <div class="card"><h3>📈 全周期历史趋势</h3><div id="c2" class="chart"></div></div>
            <div class="footer">Generated by AI Agent (Web Edition)</div>

            <script>
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
        
        # --- 1. 下载按钮 (放在最上面) ---
        base_name = os.path.splitext(uploaded_file.name)[0]
        st.download_button(
            label="📥 下载报表 (HTML)",
            data=html_content,
            file_name=f"{base_name}_分析报表.html",
            mime="text/html",
            key='download_html_btn'
        )
        
        # --- 2. 在线预览 (使用 iframe 渲染 HTML) ---
        st.subheader("👁️ 在线预览")
        components.html(html_content, height=800, scrolling=True)
        
        # --- 3. 评价与建议系统 ---
        st.markdown("---")
        st.subheader("💬 您的反馈")
        
        col_fb1, col_fb2 = st.columns([1, 2])
        
        with col_fb1:
            feedback_score = st.radio("您对本次分析满意吗？", ["👍 棒", "😐 一般", "👎 差"], horizontal=True)
        
        with col_fb2:
            feedback_text = st.text_input("有什么改进建议？(可选)")
            
        if st.button("提交评价"):
            save_feedback(feedback_score, feedback_text)
            st.success("感谢您的反馈！我们将持续改进。")
            st.balloons()
        
    except Exception as e:
        st.error(f"发生错误：{str(e)}")