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
    c.execute("ALTER TABLE works ADD COLUMN has_illustrations INTEGER DEFAULT 0")
    c.execute("ALTER TABLE works ADD COLUMN total_illustrations INTEGER DEFAULT 0")
    c.execute("ALTER TABLE works ADD COLUMN has_cover INTEGER DEFAULT 0")
    c.execute("ALTER TABLE works ADD COLUMN cover_percent INTEGER DEFAULT 0")
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
    
    div.stButton > button[kind="primary"] { 
        background-color: #C199E5 !important; color: white !important; border: none !important; height: 2.2rem !important;
        display: flex !important; align-items: center !important; justify-content: center !important;
    }
    div.stButton > button[kind="secondary"] { 
        border: 2px solid #C199E5 !important; color: #C199E5 !important; background-color: white !important; height: 2.2rem !important;
        display: flex !important; align-items: center !important; justify-content: center !important;
    }

    [data-testid="column"] div.stButton > button { font-size: 0.8rem !important; padding: 0 !important; }

    .progress-container { width: 100%; background-color: #F0F0F0; border-radius: 10px; margin: 5px 0; height: 12px; overflow: hidden; }
    .progress-bar-fill { height: 100%; background-color: #C199E5; transition: width 0.3s ease; }
    div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input { background-color: #F3E5F5 !important; border-radius: 12px !important; border: none !important; color: #B282E6 !important; }
    .log-card { border-left: 4px solid #C199E5; padding: 10px; margin-bottom: 10px; background: #fafafa; border-radius: 0 8px 8px 0; }
    .type-badge { background-color: #E1BEE7; color: #7B1FA2; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-right: 5px; }
</style>
""", unsafe_allow_html=True)

def make_hashes(p): return hashlib.sha256(str.encode(p)).hexdigest()
def check_hashes(p, h): return make_hashes(p) == h

def get_work_dict(row):
    if not row: return None
    return {
        "id": row[0], "user_id": row[1], "title": row[2], "total_pages": row[3],
        "event_name": row[4], "event_date": row[5], "deadline": row[6], "work_type": row[7],
        "plot_percent": row[8], "name_pages": row[9], "draft_pages": row[10],
        "line_pages": row[11], "tone_pages": row[12], 
        "has_illustrations": row[16], "total_illustrations": row[17],
        "has_cover": row[18], "cover_percent": row[19], "novel_unit": row[20]
    }

def calculate_total_percent(w):
    wd = get_work_dict(w)
    total = wd["total_pages"] if wd["total_pages"] > 0 else 1
    scores = [wd["plot_percent"], (wd["name_pages"]/total*100), (wd["line_pages"]/total*100), (wd["tone_pages"]/total*100)]
    if wd["work_type"] != "イラスト" and wd["has_cover"]: scores.append(wd["cover_percent"])
    avg = sum(scores) / len(scores)
    return round(max(0.0, min(float(avg), 100.0)), 1)

def get_labels(w):
    wd = get_work_dict(w)
    w_type = wd["work_type"]
    if w_type == "イラスト": return "枚", ["構成", "ラフ/下書き", "線画", "塗り/仕上げ"]
    elif w_type == "小説": return wd["novel_unit"], ["プロット","執筆", "推敲/校正", "調整"]
    else: return "P", ["プロット", "ネーム", "線画", "トーン/仕上げ"]

def format_log_note(p, n, l, t, w_type, unit, cover=0, ill=0):
    parts = []
    if p: parts.append(f"工程1 +{p}%")
    if n: parts.append(f"工程2 +{n}{unit}")
    if l: parts.append(f"工程3 +{l}{unit}")
    if t: parts.append(f"工程4 +{t}{unit}")
    if cover: parts.append(f"表紙 +{cover}%")
    if ill: parts.append(f"挿絵 +{ill}枚")
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
    
    # 作品数と完了数の集計
    total_count = len(my_works)
    completed_count = 0
    work_status_list = []
    for w in my_works:
        p = calculate_total_percent(w)
        if p >= 100.0: completed_count += 1
        work_status_list.append((w, p))

    col_t, col_add = st.columns([7, 1.5])
    # 完了数 / 全作品数 を表示
    col_t.subheader(f"自分の原稿 ({completed_count} / {total_count})")
    with col_add:
        if st.button("＋", type="primary"): st.session_state.edit_id, st.session_state.page = None, "form"; st.rerun()
            
    for work, percent in work_status_list:
        wd = get_work_dict(work)
        st.markdown(f'<div><span class="type-badge">{wd["work_type"]}</span><small style="color:#B282E6;">{wd["event_date"]} {wd["event_name"]}</small></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:18px; font-weight:bold; color:#B282E6; margin-bottom:5px;">{wd["deadline"]}〆 {wd["title"]}</div>', unsafe_allow_html=True)
        
        col_bar, col_ed, col_rd = st.columns([4, 1.5, 1.5])
        with col_bar:
            # 100%未満の場合のみプログレスバーを表示
            if percent < 100.0:
                st.markdown(f'<div class="progress-container"><div class="progress-bar-fill" style="width:{percent}%;"></div></div><div style="text-align:right; font-size:10px; color:#B282E6;">{percent}%</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="color:#C199E5; font-weight:bold; font-size:14px; padding-top:5px;">★ 完了済み (100%)</div>', unsafe_allow_html=True)
                
        with col_ed:
            if st.button("編集", key=f"e_{wd['id']}", use_container_width=True, type="secondary"): st.session_state.edit_id, st.session_state.page = wd['id'], "form"; st.rerun()
        with col_rd:
            if st.button("閲覧", key=f"v_{wd['id']}", use_container_width=True, type="primary"): st.session_state.view_id, st.session_state.page = wd['id'], "view"; st.rerun()

elif st.session_state.page == "daily":
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    c.execute("SELECT * FROM works WHERE user_id = ?", (st.session_state.user_id,))
    works = c.fetchall()
    if works:
        titles = [w[2] for w in works]
        sel_title = st.selectbox("作品名", titles)
        w = next(x for x in works if x[2] == sel_title)
        wd = get_work_dict(w)
        unit, labels = get_labels(w)
        
        p = st.number_input(f"{labels[0]} (現在: {wd['plot_percent']}%)", min_value=0, max_value=100-wd['plot_percent'])
        n = st.number_input(f"{labels[1]} (現在: {wd['name_pages']}/{wd['total_pages']}{unit})", min_value=0, max_value=wd['total_pages']-wd['name_pages'])
        l = st.number_input(f"{labels[2]} (現在: {wd['line_pages']}/{wd['total_pages']}{unit})", min_value=0, max_value=wd['total_pages']-wd['line_pages'])
        t = st.number_input(f"{labels[3]} (現在: {wd['tone_pages']}/{wd['total_pages']}{unit})", min_value=0, max_value=wd['total_pages']-wd['tone_pages'])
        cov = st.number_input(f"表紙進捗 (現在: {wd['cover_percent']}%)", min_value=0, max_value=100-wd['cover_percent']) if (wd['work_type'] != "イラスト" and wd['has_cover']) else 0
        ill = st.number_input(f"挿絵完了枚数 (現在: {wd['draft_pages']}/{wd['total_illustrations']}枚)", min_value=0, max_value=wd['total_illustrations']-wd['draft_pages']) if (wd['work_type'] == "小説" and wd['has_illustrations']) else 0
        
        if st.button("保存", type="primary", use_container_width=True):
            c.execute("UPDATE works SET plot_percent=plot_percent+?, name_pages=name_pages+?, line_pages=line_pages+?, tone_pages=tone_pages+?, cover_percent=cover_percent+?, draft_pages=draft_pages+? WHERE id=?", (p, n, l, t, cov, ill, wd['id']))
            note = format_log_note(p, n, l, t, wd['work_type'], unit, cov, ill)
            c.execute("INSERT INTO progress_logs (work_id, update_date, note, p_diff, n_diff, l_diff, t_diff) VALUES (?,?,?,?,?,?,?)", (wd['id'], datetime.now().strftime("%Y/%m/%d %H:%M"), note, p, n, l, t))
            conn.commit(); st.session_state.page = "list"; st.rerun()
    else: st.info("作品を登録してください")

elif st.session_state.page == "form":
    is_e = st.session_state.edit_id is not None
    row = c.execute("SELECT * FROM works WHERE id=?", (st.session_state.edit_id,)).fetchone() if is_e else (None, None, "", 1, "", str(date.today()), str(date.today()), "漫画", 0, 0, 0, 0, 0, 1, "短編", 1, 0, 0, 0, 0, "文字")
    wd = get_work_dict(row)
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    w_type = st.radio("ジャンル", ["漫画", "イラスト", "小説"], index=["漫画", "イラスト", "小説"].index(wd['work_type']), horizontal=True)
    n_unit, h_ill, t_ill, h_cov = wd['novel_unit'], wd['has_illustrations'], wd['total_illustrations'], wd['has_cover']
    if w_type == "小説":
        n_unit = st.radio("管理単位", ["文字", "ページ"], index=0 if wd['novel_unit']=="文字" else 1, horizontal=True)
        h_ill = 1 if st.checkbox("挿絵あり", value=bool(wd['has_illustrations'])) else 0
        if h_ill: t_ill = st.number_input("目標の挿絵枚数", min_value=1, value=max(1, wd['total_illustrations']))
        h_cov = 1 if st.checkbox("表紙あり", value=bool(wd['has_cover'])) else 0
    elif w_type == "漫画": h_cov = 1 if st.checkbox("表紙あり", value=bool(wd['has_cover'])) else 0
    t = st.text_input("作品名", value=wd['title'])
    pg = st.number_input(f"目標の{n_unit if w_type == '小説' else '総ページ'}数", min_value=1, value=wd['total_pages'])
    ev, ed, dd = st.text_input("イベント名", value=wd['event_name']), st.date_input("イベント日", value=date.fromisoformat(wd['event_date'])), st.date_input("締切日", value=date.fromisoformat(wd['deadline']))
    if st.button("保存", type="primary", use_container_width=True):
        if is_e: c.execute("UPDATE works SET title=?, total_pages=?, event_name=?, event_date=?, deadline=?, work_type=?, has_illustrations=?, total_illustrations=?, has_cover=?, novel_unit=? WHERE id=?", (t, pg, ev, str(ed), str(dd), w_type, h_ill, t_ill, h_cov, n_unit, wd['id']))
        else: c.execute("INSERT INTO works (user_id, title, total_pages, event_name, event_date, deadline, work_type, has_illustrations, total_illustrations, has_cover, novel_unit) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (st.session_state.user_id, t, pg, ev, str(ed), str(dd), w_type, h_ill, t_ill, h_cov, n_unit))
        conn.commit(); st.session_state.page = "list"; st.rerun()

elif st.session_state.page == "view":
    c.execute("SELECT works.*, users.username FROM works JOIN users ON works.user_id = users.id WHERE works.id=?", (st.session_state.view_id,))
    row = c.fetchone()
    wd = get_work_dict(row)
    uname = row[21] if len(row) > 21 else "不明"
    if st.button("◀"): st.session_state.page = "list"; st.rerun()
    st.subheader(f"{uname}さんの：{wd['title']}")
    p = calculate_total_percent(row); st.markdown(f'<div class="progress-container"><div class="progress-bar-fill" style="width:{p}%;"></div></div><div style="text-align:right;">{p}%</div>', unsafe_allow_html=True)
    unit, labels = get_labels(row)
    steps = [wd['plot_percent'], wd['name_pages'], wd['line_pages'], wd['tone_pages']]
    for i, val in enumerate(steps): st.write(f"**{labels[i]}**: {val} / {100 if i==0 else wd['total_pages']} {'%' if i==0 else unit}")
    if wd['work_type'] != "イラスト" and wd['has_cover']: st.write(f"**表紙**: {wd['cover_percent']} / 100 %")
    if wd['work_type'] == "小説" and wd['has_illustrations']: st.write(f"**挿絵**: {wd['draft_pages']} / {wd['total_illustrations']} 枚")

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
            try: c.execute("INSERT INTO friends (user_id, friend_id) VALUES (?,?)", (st.session_state.user_id, res[0])); conn.commit(); st.success("追加しました！")
            except: st.error("既に追加されています")
        else: st.error("ユーザー名またはパスワードが違います")
