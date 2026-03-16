import sqlite3
import hashlib
from datetime import date, datetime
import streamlit as st

# 1. 基本設定
st.set_page_config(page_title="創作進捗管理アプリ", layout="centered")

# 2. データベース初期化
DB_NAME = "progress.db"

def initialize_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    
    # テーブル作成
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)")
    c.execute("""
    CREATE TABLE IF NOT EXISTS works (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        title TEXT, total_pages INTEGER, event_name TEXT, event_date TEXT, deadline TEXT,
        work_type TEXT DEFAULT '漫画',
        plot_percent INTEGER DEFAULT 0, name_pages INTEGER DEFAULT 0,
        draft_pages INTEGER DEFAULT 0, line_pages INTEGER DEFAULT 0, tone_pages INTEGER DEFAULT 0,
        has_cover INTEGER DEFAULT 0, cover_percent INTEGER DEFAULT 0,
        novel_unit TEXT DEFAULT 'P',
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS progress_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, work_id INTEGER,
        update_date TEXT, 
        plot_diff INTEGER DEFAULT 0, name_diff INTEGER DEFAULT 0, 
        line_diff INTEGER DEFAULT 0, tone_diff INTEGER DEFAULT 0,
        cov_diff INTEGER DEFAULT 0, ill_diff INTEGER DEFAULT 0,
        FOREIGN KEY(work_id) REFERENCES works(id)
    )
    """)
    c.execute("CREATE TABLE IF NOT EXISTS friends (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, friend_id INTEGER, UNIQUE(user_id, friend_id))")
    conn.commit()
    return conn

conn = initialize_db()
c = conn.cursor()

# セッション管理
if "user_id" not in st.session_state: st.session_state.user_id = None
if "username" not in st.session_state: st.session_state.username = None
if "page" not in st.session_state: st.session_state.page = "list"
if "edit_id" not in st.session_state: st.session_state.edit_id = None
if "view_id" not in st.session_state: st.session_state.view_id = None
if "log_edit_id" not in st.session_state: st.session_state.log_edit_id = None

# 3. カスタムCSS (画像のデザインを反映)
st.markdown("""
<style>
    .stApp { background-color: white; color: #B282E6; }
    header { visibility: hidden; }
    .header-bar { background-color: #C199E5; height: 60px; display: flex; align-items: center; justify-content: center; margin: -60px -500px 30px -500px; }
    .header-title { color: white; font-size: 1.1rem; font-weight: bold; }
    .big-datetime { text-align: center; font-size: clamp(1.8rem, 8vw, 2.8rem); font-weight: bold; color: #B282E6; margin-bottom: 15px; }
    
    /* ボタンデザイン */
    div.stButton > button { border-radius: 12px !important; font-weight: bold !important; width: 100%; border: 2px solid #C199E5 !important; }
    div.stButton > button[kind="primary"] { background-color: #C199E5 !important; color: white !important; }
    div.stButton > button[kind="secondary"] { color: #C199E5 !important; background-color: white !important; }
    
    /* 入力フォームデザイン */
    div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input, div[data-testid="stSelectbox"] div[data-baseweb="select"] { 
        background-color: #F3E5F5 !important; border-radius: 12px !important; border: none !important; color: #B282E6 !important; 
    }
    
    /* ログカード */
    .log-card { border-left: 4px solid #C199E5; padding: 10px; margin-bottom: 5px; background: #fafafa; border-radius: 0 8px 8px 0; width: 100%; }
</style>
""", unsafe_allow_html=True)

def make_hashes(p): return hashlib.sha256(str.encode(p)).hexdigest()
def check_hashes(p, h): return make_hashes(p) == h

# 合計値再計算ロジック
def update_work_totals(work_id):
    c.execute("SELECT SUM(plot_diff), SUM(name_diff), SUM(line_diff), SUM(tone_diff), SUM(cov_diff), SUM(ill_diff) FROM progress_logs WHERE work_id=?", (work_id,))
    p, n, l, t, cov, ill = [x if x else 0 for x in c.fetchone()]
    c.execute("UPDATE works SET plot_percent=?, name_pages=?, line_pages=?, tone_pages=?, cover_percent=?, draft_pages=? WHERE id=?", (p, n, l, t, cov, ill, work_id))
    conn.commit()

# --- 認証画面 ---
if st.session_state.user_id is None:
    st.markdown('<div class="header-bar"><div class="header-title">進捗管理ログイン</div></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["ログイン", "新規登録"])
    with tab1:
        u = st.text_input("ユーザー名")
        p = st.text_input("パスワード", type='password')
        if st.button("ログイン", type="primary"):
            c.execute('SELECT id, password FROM users WHERE username = ?', (u,))
            data = c.fetchone()
            if data and check_hashes(p, data[1]):
                st.session_state.user_id, st.session_state.username = data[0], u
                st.rerun()
    with tab2:
        nu, np = st.text_input("希望のユーザー名"), st.text_input("希望のパスワード", type='password')
        if st.button("登録"):
            try:
                c.execute('INSERT INTO users(username, password) VALUES (?,?)', (nu, make_hashes(np)))
                conn.commit(); st.success("登録完了")
            except: st.error("使用済みユーザー名")
    st.stop()

st.markdown(f'<div class="header-bar"><div class="header-title">{st.session_state.username}さんの進捗</div></div>', unsafe_allow_html=True)

# --- ページ遷移 ---
if st.session_state.page == "list":
    st.markdown(f'<div class="big-datetime">{datetime.now().strftime("%Y/%m/%d %H:%M")}</div>', unsafe_allow_html=True)
    if st.button("今日の進捗", type="primary"): st.session_state.page = "daily"; st.rerun()
    col1, col2 = st.columns(2)
    if col1.button("全履歴(LOG)", type="secondary"): st.session_state.page = "log_all"; st.rerun()
    if col2.button("友達を追加", type="secondary"): st.session_state.page = "add_friend"; st.rerun()
    
    st.divider()
    c.execute("SELECT id, title, event_date, event_name, deadline, work_type, total_pages FROM works WHERE user_id = ?", (st.session_state.user_id,))
    for row in c.fetchall():
        wid, title, edate, ename, dead, wtype, t_pages = row
        st.markdown(f'<small>{edate} {ename}</small><br><b>{dead}〆 {title}</b>', unsafe_allow_html=True)
        if st.button("閲覧", key=f"v_{wid}", type="primary"): st.session_state.view_id = wid; st.session_state.page = "view"; st.rerun()

elif st.session_state.page == "daily":
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    c.execute("SELECT id, title FROM works WHERE user_id = ?", (st.session_state.user_id,))
    works = c.fetchall()
    if works:
        st.write("作品名")
        titles = [w[1] for w in works]
        sel_title = st.selectbox("作品名", titles, label_visibility="collapsed")
        wid = works[titles.index(sel_title)][0]
        
        # 画面：image_efe898.png の再現
        p = st.number_input("プロット (%)", value=0)
        n = st.number_input("ネーム (P)", value=0)
        l = st.number_input("線画 (P)", value=0)
        t = st.number_input("トーン/仕上げ (P)", value=0)
        cov = st.number_input("表紙 (%)", value=0)
        
        if st.button("保存", type="primary"):
            c.execute("INSERT INTO progress_logs (work_id, update_date, plot_diff, name_diff, line_diff, tone_diff, cov_diff) VALUES (?,?,?,?,?,?,?)",
                      (wid, datetime.now().strftime("%Y/%m/%d %H:%M"), p, n, l, t, cov))
            conn.commit()
            update_work_totals(wid)
            st.session_state.page = "list"; st.rerun()

elif st.session_state.page == "view":
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    c.execute("SELECT * FROM works WHERE id=?", (st.session_state.view_id,))
    w = c.fetchone()
    # 画面：image_f0e7c3.png の再現
    st.markdown(f'### {st.session_state.username}さんの：{w[2]}')
    # 合計進捗（簡易計算）
    total_prog = (w[8]+(w[9]/w[3]*100)+(w[11]/w[3]*100)+(w[12]/w[3]*100))/4
    st.markdown(f'<div style="width:100%; background:#F0F0F0; height:12px; border-radius:10px;"><div style="width:{total_prog}%; background:#C199E5; height:100%; border-radius:10px;"></div></div>', unsafe_allow_html=True)
    st.write(f"プロット: {w[8]} / 100 %")
    st.write(f"ネーム: {w[9]} / {w[3]} P")
    st.write(f"線画: {w[11]} / {w[3]} P")
    st.write(f"トーン/仕上げ: {w[12]} / {w[3]} P")
    st.write(f"表紙: {w[14]} / 100 %")

elif st.session_state.page == "log_all":
    if st.button("◀"): st.session_state.page = "list"; st.session_state.log_edit_id = None; st.rerun()
    c.execute("""
        SELECT pl.id, pl.update_date, w.title, pl.plot_diff, pl.name_diff, pl.line_diff, pl.tone_diff, pl.cov_diff, w.id
        FROM progress_logs pl JOIN works w ON pl.work_id = w.id WHERE w.user_id = ? ORDER BY pl.id DESC
    """, (st.session_state.user_id,))
    
    for log in c.fetchall():
        lid, ldate, ltitle, lp, ln, ll, lt, lc, lwid = log
        if st.session_state.log_edit_id == lid:
            # LOG編集：今日の進捗(image_efe898.png)と同じ項目で編集
            st.write(f"### ログ編集 ({ldate})")
            up = st.number_input("プロット (%)", value=lp, key=f"up_{lid}")
            un = st.number_input("ネーム (P)", value=ln, key=f"un_{lid}")
            ul = st.number_input("線画 (P)", value=ll, key=f"ul_{lid}")
            ut = st.number_input("トーン/仕上げ (P)", value=lt, key=f"ut_{lid}")
            uc = st.number_input("表紙 (%)", value=lc, key=f"uc_{lid}")
            if st.button("更新を保存", key=f"us_{lid}", type="primary"):
                c.execute("UPDATE progress_logs SET plot_diff=?, name_diff=?, line_diff=?, tone_diff=?, cov_diff=? WHERE id=?", (up, un, ul, ut, uc, lid))
                conn.commit(); update_work_totals(lwid); st.session_state.log_edit_id = None; st.rerun()
            if st.button("キャンセル", key=f"ucan_{lid}"): st.session_state.log_edit_id = None; st.rerun()
        else:
            # 画面：image_effea3.png の再現
            st.markdown(f'''
            <div class="log-card">
                <small>{ldate} - {st.session_state.username}<br>{ltitle}</small><br>
                <b>プロット +{lp}% / ネーム +{ln}P / 線画 +{ll}P / トーン +{lt}P</b>
            </div>''', unsafe_allow_html=True)
            if st.button("編集", key=f"le_{lid}"): st.session_state.log_edit_id = lid; st.rerun()

elif st.session_state.page == "add_friend":
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    fn = st.text_input("友達のユーザー名")
    if st.button("追加", type="primary"):
        st.success(f"{fn}を追加しました（モック）")
