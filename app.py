import streamlit as st
import pandas as pd
import os
import re
import json
import datetime
import time

# ==========================================
# 1. 页面基础配置
# ==========================================
st.set_page_config(
    page_title="AI课堂周报生成器", 
    page_icon="📊",
    layout="wide"
)

# ==========================================
# 2. 🔐 登录保护 & 📝 访问记录逻辑
# ==========================================
LOG_FILE = "access_log.csv"

def log_access():
    """记录访问时间"""
    now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 如果文件不存在，创建表头
    if not os.path.exists(LOG_FILE):
        df_log = pd.DataFrame(columns=["访问时间", "事件"])
        df_log.to_csv(LOG_FILE, index=False)
    
    # 追加记录
    new_entry = pd.DataFrame([{"访问时间": now_time, "事件": "用户登录成功"}])
    new_entry.to_csv(LOG_FILE, mode='a', header=False, index=False)

def check_password():
    """普通用户密码验证"""
    password = st.sidebar.text_input("🔒 请输入访问密码", type="password", key="user_pw")
    
    # --- 普通用户密码 ---
    if password == "123456": 
        # 只有当session_state里没有标记为已登录时，才记录日志，防止刷新页面重复记录
        if 'logged_in' not in st.session_state:
            log_access()
            st.session_state['logged_in'] = True
        return True
    return False

def show_admin_logs():
    """管理员查看日志"""
    st.sidebar.markdown("---")
    show_admin = st.sidebar.checkbox("我是管理员 (查看日志)")
    
    if show_admin:
        admin_pwd = st.sidebar.text_input("🔑 管理员密码", type="password", key="admin_pw")
        # --- 管理员密码 (设为 888888) ---
        if admin_pwd == "888888":
            st.sidebar.success("管理员已认证")
            st.subheader("📝 系统访问日志")
            
            if os.path.exists(LOG_FILE):
                df_log = pd.read_csv(LOG_FILE)
                # 按时间倒序排列（最新的在最上面）
                df_log = df_log.sort_values(by="访问时间", ascending=False)
                st.dataframe(df_log, use_container_width=True)
                
                # 下载日志按钮
                csv = df_log.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 下载日志文件",
                    csv,
                    "access_log.csv",
                    "text/csv",
                    key='download-csv'
                )
            else:
                st.info("暂无访问记录")
            st.markdown("---") # 分割线
        elif admin_pwd:
            st.sidebar.error("管理员密码错误")

# 先运行管理员逻辑（如果有的话）
show_admin_logs()

# 再运行普通用户验证
if not check_password():
    st.warning("⚠️ 请在左侧输入密码以访问系统。")
    st.stop() # ⛔️ 停止标志

# ==========================================
# 3. 主界面标题
# ==========================================
st.title("📊 AI课堂教学数据分析工具")
st.markdown("""
**使用说明：**
1. 点击下方按钮上传表格。
2. 系统会自动分析并生成包含 **详细表格** 和 **趋势图** 的完整 HTML 报表。
""")

# ==========================================
# 4. 辅助工具箱 (保持不变)
# ==========================================

# 工具1：自然排序
def natural_sort_key(s):
    if not isinstance(s, str): s = str(s)
    trans_map = {'七': '07', '八': '08', '九': '09', '高一': '10', '高二': '11', '高三': '12'}
    s_temp = s
    for k, v in trans_map.items():
        if k in s_temp and ('级' in s_temp or '年' in s_temp):
            s_temp = s_temp.replace(k, v)
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s_temp)]

# 工具2：百分比清洗
def clean_percentage(x):
    if pd.isna(x) or x == '': return 0.0
    x_str = str(x).strip()
    if '%' in x_str:
        try: return float(x_str.rstrip('%')) / 100
        except: return 0.0
    else:
        try: return float(x_str)
        except: return 0.0

# 工具3：提取年级
def get_grade(class_name):
    class_str = str(class_name)
    match = re.search(r'(.*?级)', class_str)
    if match: return match.group(1)
    if '七' in class_str: return '七年级'
    if '八' in class_str: return '八年级'
    if '九' in class_str: return '九年级'
    return "其他"

# 工具4：加权平均计算器
def weighted_avg(x, col, w_col='课时数'):
    try:
        w_sum = x[w_col].sum()
        if w_sum == 0: return 0
        return (x[col] * x[w_col]).sum() / w_sum
    except ZeroDivisionError: return 0

# 工具5：生成红绿箭头的HTML代码
def get_trend_html(current, previous, is_percent=False):
    if previous is None or previous == 0: return ""
    diff = current - previous
    if abs(diff) < 0.0001: return '<span style="color:#999;font-size:14px;">(持平)</span>'
    symbol = "↑" if diff > 0 else "↓"
    color = "#2ecc71" if diff > 0 else "#e74c3c"
    diff_str = f"{abs(diff)*100:.1f}%" if is_percent else f"{int(abs(diff))}"
    return f'<span style="color:{color};font-weight:bold;">{symbol} {diff_str}</span>'

# ==========================================
# 5. 核心逻辑
# ==========================================

# 1. 上传文件
uploaded_file = st.file_uploader("请上传表格文件", type=['xlsx', 'xls', 'csv'])

if uploaded_file is not None:
    try:
        # 2. 读取文件内容
        if uploaded_file.name.endswith('.csv'):
            try: df = pd.read_csv(uploaded_file, encoding='utf-8')
            except: df = pd.read_csv(uploaded_file, encoding='gbk')
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success(f"✅ 成功读取文件：{uploaded_file.name}")
        
        # 3. 智能识别列名
        df = df.fillna(0)
        cols_map = {}
        if '周' in df.columns: cols_map['time'] = '周'
        else: cols_map['time'] = df.columns[0]

        for c in df.columns:
            if '出勤' in c: cols_map['att'] = c
            elif '正确' in c: cols_map['corr'] = c
            # 必须包含'微课'且包含'率'
            elif '微课' in c and '率' in c: cols_map['micro'] = c
            elif '课时' in c and '数' in c: cols_map['hours'] = c
            elif '班级' in c: cols_map['class'] = c
            elif '学科' in c: cols_map['subject'] = c
        
        # 兜底
        if 'class' not in cols_map: cols_map['class'] = '班级名称'
        if 'hours' not in cols_map: cols_map['hours'] = '课时数'
        if 'att' not in cols_map: cols_map['att'] = '课时平均出勤率'
        if 'corr' not in cols_map: cols_map['corr'] = '题目正确率'

        # 把百分比文本转成数字
        for k in ['att', 'corr', 'micro']:
            if k in cols_map and cols_map[k] in df.columns:
                df[cols_map[k]] = df[cols_map[k]].apply(clean_percentage)
        
        # 4. 时间切分
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
        
        # 5. 计算全校总指标
        def calc_metrics(d):
            if d is None or d.empty: return None
            return {
                'hours': int(d[cols_map['hours']].sum()),
                'att': weighted_avg(d, cols_map['att'], cols_map['hours']),
                'corr': weighted_avg(d, cols_map['corr'], cols_map['hours'])
            }
        m_curr = calc_metrics(df_curr)
        m_prev = calc_metrics(df_prev)
        
        # 准备红绿箭头
        t_h = ""; t_a = ""; t_c = ""
        if m_prev:
            t_h = get_trend_html(m_curr['hours'], m_prev['hours'], False)
            t_a = get_trend_html(m_curr['att'], m_prev['att'], True)
            t_c = get_trend_html(m_curr['corr'], m_prev['corr'], True)
            
        # 6. 计算每个班级的详细数据
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
        
        # 准备图表数据
        c_cats = json.dumps([str(x) for x in chart_df[cols_map['class']].tolist()], ensure_ascii=False)
        c_hours = json.dumps(chart_df['课时数'].tolist())
        c_att = json.dumps([round(x*100, 1) for x in chart_df['出勤率'].tolist()])
        c_corr = json.dumps([round(x*100, 1) for x in chart_df['题目正确率'].tolist()])
        
        # 7. 找出“标杆”和“问题”班级
        best_class = class_stats.sort_values(by=['课时数', '题目正确率'], ascending=False).iloc[0]
        focus_classes = class_stats[(class_stats['出勤率'] > m_curr['att']) & (class_stats['题目正确率'] < m_curr['corr'])]
        focus_row = focus_classes.iloc[0] if not focus_classes.empty else None

        best_html = f'<div class="highlight-box success-box">🏆 <strong>综合标杆：{best_class[cols_map["class"]]}</strong> (课时:{int(best_class["课时数"])} / 正确率:{best_class["题目正确率"]*100:.1f}%)</div>'
        focus_html = ""
        if focus_row is not None:
            focus_html = f'<div class="highlight-box warning-box">⚠️ <strong>重点关注：{focus_row[cols_map["class"]]}</strong> (出勤:{focus_row["出勤率"]*100:.1f}% 正常，但正确率 {focus_row["题目正确率"]*100:.1f}% 偏低)</div>'
        
        # 8. 生成详细表格的HTML代码
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

        # 9. 准备历史趋势图数据
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

        # ==========================================
        # 6. 最终摆盘 (生成 HTML)
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
            .success-box {{ background: #d4edda; color: #1557