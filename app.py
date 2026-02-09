import streamlit as st
import pandas as pd
import os
import json
import datetime
import streamlit.components.v1 as components
import qianfan

# ==========================================
# BLOCK 1: 基础配置 (事项 2)
# ==========================================
CONFIG_FILE = "config_v2.json"
LOG_FILE = "access_log.csv"
FEEDBACK_FILE = "feedback_log.csv"

def load_config():
    defaults = {
        "admin_password": "199266", 
        "user_password": "a123456",
        "baidu_api_key": "",
        "baidu_secret_key": "",
        "app_title": "AI课堂教学数据分析工具",
        "upload_hint": "⬆️ 请上传班级教学数据 Excel 原文件"
    }
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f: json.dump(defaults, f)
        return defaults
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

conf = load_config()

# ==========================================
# BLOCK 2: 行为监控 (事项 2)
# ==========================================
def log_action(action, detail=""):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = pd.DataFrame([[now, st.session_state.get('role', '访客'), action, detail]], 
                            columns=["时间", "角色", "操作", "详情"])
    if not os.path.exists(LOG_FILE):
        log_entry.to_csv(LOG_FILE, index=False)
    else:
        log_entry.to_csv(LOG_FILE, mode='a', header=False, index=False)

# ==========================================
# BLOCK 3: 数据处理大脑 (事项 1 - 深度升级版)
# [说明]：此部分计算 HTML 模板所需的所有 15+ 个变量
# ==========================================
def process_data_logic(df):
    try:
        # 1. 基础清洗
        df['周'] = pd.to_datetime(df['周'], errors='coerce')
        df = df.dropna(subset=['周']).fillna(0)
        
        # 2. 确定统计周期
        all_weeks = sorted(df['周'].unique())
        target_week = all_weeks[-1]
        prev_week = all_weeks[-2] if len(all_weeks) > 1 else None
        
        # 3. 计算本周指标 (m_curr)
        curr_df = df[df['周'] == target_week]
        m_curr = {
            'hours': int(curr_df['课时数'].sum()),
            'att': curr_df['课时平均出勤率'].mean(),
            'corr': curr_df['题目正确率（自学+快背）'].mean()
        }
        
        # 4. 计算同比变化 (t_h, t_a, t_c)
        t_h, t_a, t_c = "", "", ""
        if prev_week:
            prev_df = df[df['周'] == prev_week]
            h_diff = m_curr['hours'] - prev_df['课时数'].sum()
            t_h = f" ({'+' if h_diff>=0 else ''}{h_diff})"
            a_diff = (m_curr['att'] - prev_df['课时平均出勤率'].mean()) * 100
            t_a = f" ({'+' if a_diff>=0 else ''}{a_diff:.1f}%)"
            c_diff = (m_curr['corr'] - prev_df['题目正确率（自学+快背）'].mean()) * 100
            t_c = f" ({'+' if c_diff>=0 else ''}{c_diff:.1f}%)"

        # 5. 班级效能分析数据 (c_cats, c_hours...)
        class_stats = curr_df.groupby('班级名称').agg({
            '课时数':'sum', '课时平均出勤率':'mean', '题目正确率（自学+快背）':'mean'
        }).reset_index().sort_values('课时平均出勤率', ascending=False)
        
        # 6. 标杆与关注 (best_html, focus_html)
        best_c = class_stats.iloc[0]
        best_html = f'<div class="highlight-box success-box">🏆 <b>标杆班级:</b> {best_c["班级名称"]} (出勤 {best_c["课时平均出勤率"]*100:.1f}%)</div>'
        focus_html = "" # 可根据逻辑增加需关注班级
        
        # 7. 历史趋势数据 (t_dates, t_hours...)
        trend = df.groupby('周').agg({
            '课时数':'sum', '课时平均出勤率':'mean', '题目正确率（自学+快背）':'mean'
        }).reset_index()
        
        # 8. 生成表格 HTML (tables_html)
        tables_html = curr_df[['班级名称','课时数','课时平均出勤率','题目正确率（自学+快背）']].to_html(index=False, classes='table')

        return {
            "target_week": target_week.strftime('%Y-%m-%d'),
            "prev_week": prev_week.strftime('%Y-%m-%d') if prev_week else None,
            "m_curr": m_curr, "t_h": t_h, "t_a": t_a, "t_c": t_c,
            "best_html": best_html, "focus_html": focus_html,
            "c_cats": class_stats['班级名称'].tolist(),
            "c_hours": class_stats['课时数'].tolist(),
            "c_att": (class_stats['课时平均出勤率']*100).round(1).tolist(),
            "c_corr": (class_stats['题目正确率（自学+快背）']*100).round(1).tolist(),
            "t_dates": trend['周'].dt.strftime('%m-%d').tolist(),
            "t_hours": trend['课时数'].tolist(),
            "t_att": (trend['课时平均出勤率']*100).round(1).tolist(),
            "t_corr": (trend['题目正确率（自学+快背）']*100).round(1).tolist(),
            "tables_html": tables_html
        }
    except Exception as e:
        st.error(f"数据脑处理失败: {e}")
        return None

# ==========================================
# BLOCK 4: HTML 模板 (事项 3 - 采用您满意的维度)
# ==========================================
def get_report_html(d, ai_text):
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
        .ai-card {{ border-left: 5px solid #2ecc71; background: #f0fff4; padding: 15px; margin-bottom: 20px; border-radius: 8px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        th {{ background: #eee; padding: 10px; border-bottom: 2px solid #ddd; }} 
        td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: center; }}
        .chart {{ height: 400px; width: 100%; }}
    </style>
    </head>
    <body>
        <h2 style="text-align:center">AI课堂教学数据分析周报</h2>
        <div style="text-align:center;color:#666;margin-bottom:20px">
            统计周期: <b>{d['target_week']}</b> 
            {f'<span style="font-size:12px">(对比: {d["prev_week"]})</span>' if d['prev_week'] else ''}
        </div>
        
        <div class="card">
            <h3>📊 本周核心指标</h3>
            <div class="kpi">
                <div><strong>{d['m_curr']['hours']}{d['t_h']}</strong>总课时</div>
                <div><strong>{d['m_curr']['att']*100:.1f}%{d['t_a']}</strong>出勤率</div>
                <div><strong>{d['m_curr']['corr']*100:.1f}%{d['t_c']}</strong>正确率</div>
            </div>
            {d['best_html']}{d['focus_html']}
        </div>

        <div class="ai-card">
            <h3>🤖 AI 协作分析建议</h3>
            <div style="white-space: pre-wrap;">{ai_text}</div>
        </div>
        
        <div class="card"><h3>🏫 班级效能分析</h3><div id="c1" class="chart"></div></div>
        <div class="card"><h3>📋 详细数据明细</h3>{d['tables_html']}</div>
        <div class="card"><h3>📈 全周期历史趋势</h3><div id="c2" class="chart"></div></div>

        <script>
            var c1 = echarts.init(document.getElementById('c1'));
            c1.setOption({{
                tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                xAxis: {{type:'category', data:{json.dumps(d['c_cats'])}, axisLabel:{{rotate:30, interval:0}}}},
                yAxis: [{{type:'value',name:'课时'}}, {{type:'value',name:'%',max:100}}],
                series: [
                    {{type:'bar',name:'课时数',data:{json.dumps(d['c_hours'])},itemStyle:{{color:'#3498db'}}}},
                    {{type:'line',yAxisIndex:1,name:'出勤率',data:{json.dumps(d['c_att'])},itemStyle:{{color:'#2ecc71'}}}},
                    {{type:'line',yAxisIndex:1,name:'正确率',data:{json.dumps(d['c_corr'])},itemStyle:{{color:'#e74c3c'}}}}
                ]
            }});
            var c2 = echarts.init(document.getElementById('c2'));
            c2.setOption({{
                tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                xAxis: {{type:'category', data:{json.dumps(d['t_dates'])}}},
                yAxis: [{{type:'value',name:'课时'}}, {{type:'value',name:'%',max:100}}],
                series: [
                    {{type:'bar',name:'课时数',data:{json.dumps(d['t_hours'])},itemStyle:{{color:'#9b59b6'}}}},
                    {{type:'line',yAxisIndex:1,name:'出勤率',data:{json.dumps(d['t_att'])},itemStyle:{{color:'#2ecc71'}}}},
                    {{type:'line',yAxisIndex:1,name:'正确率',data:{json.dumps(d['t_corr'])},itemStyle:{{color:'#e74c3c'}}}}
                ]
            }});
        </script>
    </body></html>
    """
    return html_content

# ==========================================
# BLOCK 5 & 6: 交互与 AI (事项 1 & 3)
# ==========================================
st.set_page_config(page_title=conf["app_title"], layout="wide")

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'ai_history' not in st.session_state: st.session_state.ai_history = []
if 'analysis_res' not in st.session_state: st.session_state.analysis_res = None

if not st.session_state.logged_in:
    st.title(f"🔐 {conf['app_title']}")
    pwd = st.text_input("登录密码", type="password")
    if st.button("进入"):
        if pwd == conf["admin_password"] or pwd == conf["user_password"]:
            st.session_state.logged_in = True
            st.session_state.role = "admin" if pwd == conf["admin_password"] else "user"
            log_action("登录成功")
            st.rerun()
        else: st.error("密码错误")
else:
    mode = st.sidebar.radio("菜单", ["数据看板", "AI 协作区", "后台设置"])
    
    if mode == "数据看板":
        file = st.file_uploader(conf["upload_hint"], type=["xlsx"])
        if file:
            res = process_data_logic(pd.read_excel(file))
            if res:
                st.session_state.analysis_res = res
                st.success("数据分析已就绪。")
    
    elif mode == "AI 协作区":
        if not st.session_state.analysis_res: st.warning("请先上传数据。")
        else:
            for m in st.session_state.ai_history:
                with st.chat_message(m["role"]): st.write(m["content"])
            
            q = st.chat_input("输入指令调整 AI 建议...")
            if q:
                st.session_state.ai_history.append({"role":"user", "content":q})
                # 此处可接入百度的 call_ai 函数
                ans = "根据您的要求，AI 已重新生成分析建议..." 
                st.session_state.ai_history.append({"role":"assistant", "content":ans})
                st.rerun()
            
            if st.session_state.ai_history:
                html = get_report_html(st.session_state.analysis_res, st.session_state.ai_history[-1]["content"])
                st.download_button("📥 下载 HTML 报表", html, "教学周报.html", "text/html")
                components.html(html, height=800, scrolling=True)

    elif mode == "后台设置" and st.session_state.role == "admin":
        st.write("后台管理功能...")
