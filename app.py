import sqlite3
import hashlib
from datetime import date, datetime
import streamlit as st

# 1. 基本設定
st.set_page_config(page_title="創作進捗管理アプリ", layout="centered")

# 2. データベース初期化
conn = sqlite3.connect("progress.db", check_same_thread=False)
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)")
c.execute("""
CREATE TABLE IF NOT EXISTS works (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
    title TEXT, total_pages INTEGER, event_name TEXT, event_date TEXT, deadline TEXT,
    work_type TEXT DEFAULT '漫画',
    plot_percent INTEGER DEFAULT 0, name_pages INTEGER DEFAULT 0,
    draft_pages INTEGER DEFAULT 0, line_pages INTEGER DEFAULT 0, tone_pages INTEGER DEFAULT 0,
    current_chapter INTEGER DEFAULT 1,
    novel_type TEXT DEFAULT '短編',
    total_chapters INTEGER DEFAULT 1,
    has_illustrations INTEGER DEFAULT 0,
    total_illustrations INTEGER DEFAULT 0,
    has_cover INTEGER DEFAULT 0,
    cover_percent INTEGER DEFAULT 0,
    novel_unit TEXT DEFAULT '文字',
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")

# カラム追加対応
try:
    c.execute("ALTER TABLE works ADD COLUMN novel_unit TEXT DEFAULT '文字'")
except: pass

c.execute("""
CREATE TABLE IF NOT EXISTS progress_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, work_id INTEGER,
    update_date TEXT, note TEXT,
    p_diff INTEGER DEFAULT 0, n_diff INTEGER DEFAULT 0, 
    l_diff INTEGER DEFAULT 0, t_diff INTEGER DEFAULT 0,
    FOREIGN KEY(work_id) REFERENCES works(id)
)
""")
c.execute("CREATE TABLE IF NOT EXISTS friends (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, friend_id INTEGER, UNIQUE(user_id, friend_id))")
conn.commit()

# セッション管理
if "user_id" not in st.session_state: st.session_state.user_id = None
if "username" not in st.session_state: st.session_state.username = None
if "page" not in st.session_state: st.session_state.page = "list"
if "edit_id" not in st.session_state: st.session_state.edit_id = None
if "view_id" not in st.session_state: st.session_state.view_id = None

# 3. カスタムCSS
st.markdown("""
<style>
    .stApp { background-color: white; color: #B282E6; }
    header { visibility: hidden; }
    .header-bar { background-color: #C199E5; height: 60px; display: flex; align-items: center; justify-content: center; margin: -60px -500px 30px -500px; }
    .header-title { color: white; font-size: 1.1rem; font-weight: bold; }
    .big-datetime { text-align: center; font-size: clamp(1.8rem, 8vw, 2.8rem); font-weight: bold; color: #B282E6; margin-bottom: 15px; }
    
    div.stButton > button { border-radius: 12px !important; font-weight: bold !important; width: 100%; }
    
    /* 編集・閲覧ボタンのサイズを完全に統一する設定 */
    div.stButton > button[kind="primary"] { 
        background-color: #C199E5 !important; 
        color: white !important; 
        border: none !important; 
        height: 2.2rem !important; /* リスト内の高さを統一 */
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    div.stButton > button[kind="secondary"] { 
        border: 2px solid #C199E5 !important; 
        color: #C199E5 !important; 
        background-color: white !important; 
        height: 2.2rem !important; /* プライマリボタンと同じ高さに固定 */
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    /* カラム内のボタンフォントサイズと余白を固定 */
    [data-testid="column"] div.stButton > button { 
        font-size: 0.8rem !important; 
        padding: 0 !important;
    }

    .progress-container { width: 100%; background-color: #F0F0F0; border-radius: 10px; margin: 5px 0; height: 12px; overflow: hidden; }
    .progress-bar-fill { height: 100%; background-color: #C199E5; transition: width 0.3s ease; }
    div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input { background-color: #F3E5F5 !important; border-radius: 12px !important; border: none !important; color: #B282E6 !important; }
    .log-card { border-left: 4px solid #C199E5; padding: 10px; margin-bottom: 10px; background: #fafafa; border-radius: 0 8px 8px 0; }
    .type-badge { background-color: #E1BEE7; color: #7B1FA2; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-right: 5px; }
</style>
""", unsafe_allow_html=True)

def make_hashes(p): return hashlib.sha256(str.encode(p)).hexdigest()
def check_hashes(p, h): return make_hashes(p) == h

def calculate_total_percent(w):
    total = w[3] if w[3] and w[3] > 0 else 1
    scores = [w[8], (w[9]/total*100), (w[11]/total*100), (w[12]/total*100)]
    if w[7] != "イラスト" and w[18]: scores.append(w[19])
    avg = sum(scores) / len(scores)
    return round(max(0.0, min(float(avg), 100.0)), 1)

def get_labels(w):
    w_type = w[7]
    if w_type == "イラスト":
        return "枚", ["構成", "ラフ/下書き", "線画", "塗り/仕上げ"]
    elif w_type == "小説":
        unit = w[20] if len(w) > 20 else "文字"
        return unit, ["プロット","執筆", "推敲/校正", "調整"]
    else: # 漫画
        return "P", ["プロット", "ネーム", "線画", "トーン/仕上げ"]

def format_log_note(p, n, l, t, w_type, unit, cover=0):
    parts = []
    if p: parts.append(f"工程1 +{p}%")
    if n: parts.append(f"工程2 +{n}{unit}")
    if l: parts.append(f"工程3 +{l}{unit}")
    if t: parts.append(f"工程4 +{t}{unit}")
    if cover: parts.append(f"表紙 +{cover}%")
    return " / ".join(parts) if parts else "更新なし"

# --- 認証機能 ---
if st.session_state.user_id is None:
    st.markdown('<div class="header-bar"><div class="header-title">進捗管理ログイン</div></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["ログイン", "新規登録"])
    with tab1:
        u = st.text_input("ユーザー名")
        p = st.text_input("パスワード", type='password')
        if st.button("ログイン", type="primary", use_container_width=True):
            c.execute('SELECT id, password FROM users WHERE username = ?', (u,))
            data = c.fetchone()
            if data and check_hashes(p, data[1]):
                st.session_state.user_id, st.session_state.username = data[0], u
                st.rerun()
    with tab2:
        nu = st.text_input("希望のユーザー名")
        np = st.text_input("希望のパスワード", type='password')
        if st.button("登録", use_container_width=True):
            try:
                c.execute('INSERT INTO users(username, password) VALUES (?,?)', (nu, make_hashes(np)))
                conn.commit(); st.success("登録完了！")
            except: st.error("エラーが発生しました")
    st.stop()

st.markdown(f'<div class="header-bar"><div class="header-title">{st.session_state.username}さんの進捗</div></div>', unsafe_allow_html=True)

# --- 画面遷移 ---
if st.session_state.page == "list":
    st.markdown(f'<div class="big-datetime">{datetime.now().strftime("%Y/%m/%d %H:%M")}</div>', unsafe_allow_html=True)
    st.button("今日の進捗", use_container_width=True, type="primary", on_click=lambda: setattr(st.session_state, 'page', 'daily'))
    col_sub1, col_sub2 = st.columns(2)
    with col_sub1: st.button("全履歴(LOG)", use_container_width=True, type="secondary", on_click=lambda: setattr(st.session_state, 'page', 'log_all'))
    with col_sub2: st.button("友達を追加", use_container_width=True, type="secondary", on_click=lambda: setattr(st.session_state, 'page', 'add_friend'))
    st.divider()
    
    c.execute("SELECT * FROM works WHERE user_id = ?", (st.session_state.user_id,))
    my_works = c.fetchall()
    col_t, col_add = st.columns([7, 1.5])
    col_t.subheader("自分の原稿")
    with col_add:
        if st.button("＋", type="primary"): st.session_state.edit_id, st.session_state.page = None, "form"; st.rerun()
            
    for work in my_works:
        st.markdown(f'<div><span class="type-badge">{work[7]}</span><small style="color:#B282E6;">{work[5]} {work[4]}</small></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:18px; font-weight:bold; color:#B282E6; margin-bottom:5px;">{work[6]}〆 {work[2]}</div>', unsafe_allow_html=True)
        percent = calculate_total_percent(work)
        
        # ご希望のレイアウト（進捗バー：編集：閲覧 ＝ 4：1.5：1.5）
        col_bar, col_ed, col_rd = st.columns([4, 1.5, 1.5])
        with col_bar:
            st.markdown(f'<div class="progress-container"><div class="progress-bar-fill" style="width:{percent}%;"></div></div><div style="text-align:right; font-size:10px; color:#B282E6;">{percent}%</div>', unsafe_allow_html=True)
        with col_ed:
            if st.button("編集", key=f"e_{work[0]}", use_container_width=True, type="secondary"): st.session_state.edit_id, st.session_state.page = work[0], "form"; st.rerun()
        with col_rd:
            if st.button("閲覧", key=f"v_{work[0]}", use_container_width=True, type="primary"): st.session_state.view_id, st.session_state.page = work[0], "view"; st.rerun()

elif st.session_state.page == "daily":
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    c.execute("SELECT * FROM works WHERE user_id = ?", (st.session_state.user_id,))
    works = c.fetchall()
    if works:
        sel_title = st.selectbox("作品名", [w[2] for w in works])
        w = next(x for x in works if x[2] == sel_title)
        unit, labels = get_labels(w)
        
        p = st.number_input(f"{labels[0]} (現在: {w[8]}%)", min_value=0, max_value=100-w[8])
        n = st.number_input(f"{labels[1]} (現在: {w[9]}/{w[3]}{unit})", min_value=0, max_value=w[3]-w[9])
        l = st.number_input(f"{labels[2]} (現在: {w[11]}/{w[3]}{unit})", min_value=0, max_value=w[3]-w[11])
        t = st.number_input(f"{labels[3]} (現在: {w[12]}/{w[3]}{unit})", min_value=0, max_value=w[3]-w[12])
        cov = st.number_input(f"表紙進捗 (現在: {w[19]}%)", min_value=0, max_value=100-w[19]) if (w[7] != "イラスト" and w[18]) else 0
        
        if st.button("保存", type="primary", use_container_width=True):
            c.execute("UPDATE works SET plot_percent=plot_percent+?, name_pages=name_pages+?, line_pages=line_pages+?, tone_pages=tone_pages+?, cover_percent=cover_percent+? WHERE id=?", (p, n, l, t, cov, w[0]))
            note = format_log_note(p, n, l, t, w[7], unit, cov)
            c.execute("INSERT INTO progress_logs (work_id, update_date, note, p_diff, n_diff, l_diff, t_diff) VALUES (?,?,?,?,?,?,?)", (w[0], datetime.now().strftime("%Y/%m/%d %H:%M"), note, p, n, l, t))
            conn.commit(); st.session_state.page = "list"; st.rerun()

elif st.session_state.page == "form":
    is_e = st.session_state.edit_id is not None
    wd = c.execute("SELECT * FROM works WHERE id=?", (st.session_state.edit_id,)).fetchone() if is_e else (None, None, "", 1, "", str(date.today()), str(date.today()), "漫画", 0, 0, 0, 0, 0, 1, "短編", 1, 0, 0, 0, 0, "文字")
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    
    w_type = st.radio("ジャンル", ["漫画", "イラスト", "小説"], index=["漫画", "イラスト", "小説"].index(wd[7]), horizontal=True)
    
    n_unit, h_ill, h_cov = wd[20], 0, 0
    if w_type == "小説":
        n_unit = st.radio("管理単位", ["文字", "ページ"], index=0 if wd[20]=="文字" else 1, horizontal=True)
        h_ill = 1 if st.checkbox("挿絵あり", value=bool(wd[16])) else 0
        h_cov = 1 if st.checkbox("表紙あり", value=bool(wd[18])) else 0
    elif w_type == "漫画":
        h_cov = 1 if st.checkbox("表紙あり", value=bool(wd[18])) else 0

    t = st.text_input("作品名", value=wd[2])
    pg = st.number_input(f"目標の{n_unit if w_type == '小説' else '総ページ'}数", min_value=1, value=wd[3])
    ev, ed, dd = st.text_input("イベント名", value=wd[4]), st.date_input("イベント日", value=date.fromisoformat(wd[5])), st.date_input("締切日", value=date.fromisoformat(wd[6]))
    
    if st.button("保存", type="primary", use_container_width=True):
        if is_e:
            c.execute("UPDATE works SET title=?, total_pages=?, event_name=?, event_date=?, deadline=?, work_type=?, has_illustrations=?, has_cover=?, novel_unit=? WHERE id=?", (t, pg, ev, str(ed), str(dd), w_type, h_ill, h_cov, n_unit, wd[0]))
        else:
            c.execute("INSERT INTO works (user_id, title, total_pages, event_name, event_date, deadline, work_type, has_illustrations, has_cover, novel_unit) VALUES (?,?,?,?,?,?,?,?,?,?)", (st.session_state.user_id, t, pg, ev, str(ed), str(dd), w_type, h_ill, h_cov, n_unit))
        conn.commit(); st.session_state.page = "list"; st.rerun()

elif st.session_state.page == "view":
    c.execute("SELECT works.*, users.username FROM works JOIN users ON works.user_id = users.id WHERE works.id=?", (st.session_state.view_id,))
    w = c.fetchone()
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    st.subheader(f"{w[20]}さんの：{w[2]}")
    p = calculate_total_percent(w); st.markdown(f'<div class="progress-container"><div class="progress-bar-fill" style="width:{p}%;"></div></div><div style="text-align:right;">{p}%</div>', unsafe_allow_html=True)
    unit, labels = get_labels(w)
    for i, val in enumerate([w[8], w[9], w[11], w[12]]):
        st.write(f"**{labels[i]}**: {val} / {100 if i==0 else w[3]} {'%' if i==0 else unit}")
    if w[7] != "イラスト" and w[18]: st.write(f"**表紙**: {w[19]} / 100 %")

elif st.session_state.page == "log_all":
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    c.execute("SELECT pl.update_date, pl.note, w.title, u.username FROM progress_logs pl JOIN works w ON pl.work_id = w.id JOIN users u ON w.user_id = u.id WHERE w.user_id = ? OR w.user_id IN (SELECT friend_id FROM friends WHERE user_id = ?) ORDER BY pl.id DESC", (st.session_state.user_id, st.session_state.user_id))
    for log in c.fetchall(): st.markdown(f'<div class="log-card"><small>{log[0]} - {log[3]}<br>{log[2]}</small><br><b>{log[1]}</b></div>', unsafe_allow_html=True)

elif st.session_state.page == "add_friend":
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    f_name, f_pass = st.text_input("友達のユーザー名"), st.text_input("友達のパスワード", type="password")
    if st.button("追加", type="primary"):
        c.execute("SELECT id, password FROM users WHERE username=?", (f_name,))
        res = c.fetchone()
        if res and check_hashes(f_pass, res[1]):
            try:
                c.execute("INSERT INTO friends (user_id, friend_id) VALUES (?,?)", (st.session_state.user_id, res[0])); conn.commit(); st.success("追加しました！")
            except: st.error("既に追加されています")
        else: st.error("ユーザー名またはパスワードが違います")
