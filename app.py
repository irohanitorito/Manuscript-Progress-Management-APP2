import sqlite3
import hashlib
from datetime import date, datetime
import streamlit as st
import os

# 1. 基本設定
st.set_page_config(page_title="創作進捗管理アプリ", layout="centered")

# 2. データベース初期化
DB_NAME = "progress.db"

def initialize_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    
    # ユーザーテーブル (show_friends_progress カラムを追加)
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        username TEXT UNIQUE, 
        password TEXT,
        show_friends_progress INTEGER DEFAULT 1
    )
    """)
    
    # 既存DBへのカラム追加（ユーザー設定用）
    try:
        c.execute("SELECT show_friends_progress FROM users LIMIT 1")
    except:
        c.execute("ALTER TABLE users ADD COLUMN show_friends_progress INTEGER DEFAULT 1")

    # 作品テーブル
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
    
    # ログテーブル
    c.execute("""
    CREATE TABLE IF NOT EXISTS progress_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, work_id INTEGER,
        update_date TEXT, note TEXT,
        p_diff INTEGER DEFAULT 0, n_diff INTEGER DEFAULT 0, 
        l_diff INTEGER DEFAULT 0, t_diff INTEGER DEFAULT 0,
        cov_diff INTEGER DEFAULT 0, ill_diff INTEGER DEFAULT 0,
        FOREIGN KEY(work_id) REFERENCES works(id)
    )
    """)
    
    # 既存DBへのカラム追加（エラー回避用）
    try:
        c.execute("SELECT cov_diff FROM progress_logs LIMIT 1")
    except:
        c.execute("ALTER TABLE progress_logs ADD COLUMN cov_diff INTEGER DEFAULT 0")
        c.execute("ALTER TABLE progress_logs ADD COLUMN ill_diff INTEGER DEFAULT 0")

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

# 3. カスタムCSS
st.markdown("""
<style>
    .stApp { background-color: white; color: #B282E6; }
    header { visibility: hidden; }
    .header-bar { background-color: #C199E5; height: 60px; display: flex; align-items: center; justify-content: center; margin: -60px -500px 30px -500px; }
    .header-title { color: white; font-size: 1.1rem; font-weight: bold; }
    .big-datetime { text-align: center; font-size: clamp(1.8rem, 8vw, 2.8rem); font-weight: bold; color: #B282E6; margin-bottom: 15px; }
    div.stButton > button { border-radius: 12px !important; font-weight: bold !important; width: 100%; }
    div.stButton > button[kind="primary"] { background-color: #C199E5 !important; color: white !important; border: none !important; height: 2.2rem !important; display: flex !important; align-items: center !important; justify-content: center !important; }
    div.stButton > button[kind="secondary"] { border: 2px solid #C199E5 !important; color: #C199E5 !important; background-color: white !important; height: 2.2rem !important; display: flex !important; align-items: center !important; justify-content: center !important; }
    [data-testid="column"] div.stButton > button { font-size: 0.8rem !important; padding: 0 !important; }
    .progress-container { width: 100%; background-color: #F0F0F0; border-radius: 10px; margin: 5px 0; height: 12px; overflow: hidden; }
    .progress-bar-fill { height: 100%; background-color: #C199E5; transition: width 0.3s ease; }
    div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input { background-color: #F3E5F5 !important; border-radius: 12px !important; border: none !important; color: #B282E6 !important; }
    .log-card { border-left: 4px solid #C199E5; padding: 10px; margin-bottom: 5px; background: #fafafa; border-radius: 0 8px 8px 0; width: 100%; }
    .type-badge { background-color: #E1BEE7; color: #7B1FA2; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-right: 5px; }
    .owner-tag { color: #888; font-size: 0.8rem; margin-bottom: 4px; font-weight: bold; }
    .complete-badge { background-color: #4CAF50; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def make_hashes(p): return hashlib.sha256(str.encode(p)).hexdigest()
def check_hashes(p, h): return make_hashes(p) == h

def update_work_totals(work_id):
    c.execute("SELECT SUM(p_diff), SUM(n_diff), SUM(l_diff), SUM(t_diff), SUM(cov_diff), SUM(ill_diff) FROM progress_logs WHERE work_id=?", (work_id,))
    res = c.fetchone()
    p, n, l, t, cov, ill = [x if x else 0 for x in res]
    c.execute("UPDATE works SET plot_percent=?, name_pages=?, line_pages=?, tone_pages=?, cover_percent=?, draft_pages=? WHERE id=?", (p, n, l, t, cov, ill, work_id))
    conn.commit()

def get_work_dict(row):
    if not row: return None
    d = list(row) + [0]*22
    return {
        "id": d[0], "user_id": d[1], "title": d[2], "total_pages": d[3],
        "event_name": d[4], "event_date": d[5], "deadline": d[6], "work_type": d[7],
        "plot_percent": d[8], "name_pages": d[9], "draft_pages": d[10],
        "line_pages": d[11], "tone_pages": d[12], 
        "has_illustrations": d[16], "total_illustrations": d[17],
        "has_cover": d[18], "cover_percent": d[19], "novel_unit": d[20],
        "owner_name": d[21] if len(d) > 21 else ""
    }

def calculate_total_percent(w):
    wd = get_work_dict(w)
    if not wd: return 0.0
    total = wd["total_pages"] if wd["total_pages"] > 0 else 1
    w_type = wd["work_type"]
    if w_type == "小説":
        scores = [wd["plot_percent"], (wd["name_pages"]/total*100), (wd["line_pages"]/total*100)]
        if wd["has_cover"]: scores.append(wd["cover_percent"])
        if wd["has_illustrations"] and wd["total_illustrations"] > 0:
            scores.append((wd["draft_pages"] / wd["total_illustrations"]) * 100)
    else:
        scores = [wd["plot_percent"], (wd["name_pages"]/total*100), (wd["line_pages"]/total*100), (wd["tone_pages"]/total*100)]
        if wd["has_cover"]: scores.append(wd["cover_percent"])
    avg = sum(scores) / len(scores)
    return round(max(0.0, min(float(avg), 100.0)), 1)

def get_labels_from_type(w_type, novel_unit="P"):
    if w_type == "イラスト": return "枚", ["構成", "ラフ/下書き", "線画", "塗り/仕上げ"]
    elif w_type == "小説": return novel_unit, ["プロット","執筆", "推敲/校正"]
    else: return "P", ["プロット", "ネーム", "線画", "トーン/仕上げ"]

def format_log_note(p, n, l, t, w_type, unit, labels, cover=0, ill=0):
    parts = []
    if p: parts.append(f"{labels[0]} +{p}%")
    if n: parts.append(f"{labels[1]} +{n}{unit}")
    if l: parts.append(f"{labels[2]} +{l}{unit}")
    if t and w_type != "小説": parts.append(f"{labels[3]} +{t}{unit}")
    if cover: parts.append(f"表紙 +{cover}%")
    if ill: parts.append(f"挿絵 +{ill}枚")
    return " / ".join(parts) if parts else "更新なし"

# --- 認証機能 ---
if st.session_state.user_id is None:
    st.markdown('<div class="header-bar"><div class="header-title">進捗管理ログイン</div></div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["ログイン", "新規登録"])
    with tab1:
        u = st.text_input("ユーザー名", key="login_user")
        p = st.text_input("パスワード", type='password', key="login_pass")
        if st.button("ログイン", type="primary", use_container_width=True):
            c.execute('SELECT id, password FROM users WHERE username = ?', (u,))
            data = c.fetchone()
            if data and check_hashes(p, data[1]):
                st.session_state.user_id, st.session_state.username = data[0], u
                st.rerun()
            else: st.error("ユーザー名またはパスワードが違います")
    with tab2:
        nu = st.text_input("新しいユーザー名", key="reg_user")
        np = st.text_input("新しいパスワード", type='password', key="reg_pass")
        if st.button("アカウントを作成する", type="primary", use_container_width=True):
            if nu and np:
                try:
                    c.execute("INSERT INTO users (username, password) VALUES (?,?)", (nu, make_hashes(np)))
                    conn.commit()
                    st.success("登録完了！ログインしてください")
                except: st.error("そのユーザー名は既に使用されています")
            else: st.error("ユーザー名とパスワードを入力してください")
    st.stop()

# --- ユーザー設定 (サイドバー) ---
c.execute("SELECT show_friends_progress FROM users WHERE id=?", (st.session_state.user_id,))
show_friends_config = c.fetchone()[0]

with st.sidebar:
    st.title("設定")
    new_show_friends = st.checkbox("友達の進捗を表示する", value=bool(show_friends_config))
    if new_show_friends != bool(show_friends_config):
        c.execute("UPDATE users SET show_friends_progress=? WHERE id=?", (int(new_show_friends), st.session_state.user_id))
        conn.commit()
        st.rerun()
    
    if st.button("ログアウト"):
        st.session_state.user_id = None
        st.session_state.username = None
        st.rerun()

st.markdown(f'<div class="header-bar"><div class="header-title">{st.session_state.username}さんの進捗</div></div>', unsafe_allow_html=True)

# --- メイン画面 ---
if st.session_state.page == "list":
    st.markdown(f'<div class="big-datetime">{datetime.now().strftime("%Y/%m/%d %H:%M")}</div>', unsafe_allow_html=True)
    st.button("今日の進捗", use_container_width=True, type="primary", on_click=lambda: setattr(st.session_state, 'page', 'daily'))
    col_sub1, col_sub2 = st.columns(2)
    with col_sub1: st.button("全履歴(LOG)", use_container_width=True, type="secondary", on_click=lambda: setattr(st.session_state, 'page', 'log_all'))
    with col_sub2: st.button("友達を追加", use_container_width=True, type="secondary", on_click=lambda: setattr(st.session_state, 'page', 'add_friend'))
    st.divider()

    # 自分の原稿
    c.execute("SELECT * FROM works WHERE user_id = ?", (st.session_state.user_id,))
    my_works = c.fetchall()
    
    col_t, col_add = st.columns([7, 1.5])
    col_t.subheader(f"自分の原稿")
    with col_add:
        if st.button("＋", type="primary", key="add_new_work_btn"): 
            st.session_state.edit_id = None
            st.session_state.page = "form"
            st.rerun()

    for work in my_works:
        wd = get_work_dict(work); percent = calculate_total_percent(work)
        st.markdown(f'<div><span class="type-badge">{wd["work_type"]}</span><small style="color:#B282E6;">{wd["event_date"]} {wd["event_name"]}</small></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:18px; font-weight:bold; color:#B282E6; margin-bottom:5px;">{wd["deadline"]}〆 {wd["title"]}</div>', unsafe_allow_html=True)
        col_bar, col_ed, col_rd = st.columns([5.5, 1.5, 1.5])
        with col_bar:
            if percent >= 100:
                st.markdown('<div style="margin: 10px 0;"><span class="complete-badge">✅ 完了済み</span></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="progress-container"><div class="progress-bar-fill" style="width:{percent}%;"></div></div><div style="text-align:right; font-size:10px; color:#B282E6;">{percent}%</div>', unsafe_allow_html=True)
        with col_ed:
            if st.button("編集", key=f"e_btn_{wd['id']}", use_container_width=True, type="secondary"): 
                st.session_state.edit_id, st.session_state.page = wd['id'], "form"
                st.rerun()
        with col_rd:
            if st.button("閲覧", key=f"v_btn_{wd['id']}", use_container_width=True, type="primary"): 
                st.session_state.view_id, st.session_state.page = wd['id'], "view"
                st.rerun()

    st.divider()
    
    # 友達の原稿 (ON/OFF機能)
    if show_friends_config:
        st.subheader(f"友達の原稿")
        c.execute("""
            SELECT w.*, u.username FROM works w 
            JOIN users u ON w.user_id = u.id 
            WHERE w.user_id IN (SELECT friend_id FROM friends WHERE user_id = ?)
        """, (st.session_state.user_id,))
        friend_works = c.fetchall()
        
        if friend_works:
            for f_work in friend_works:
                wd = get_work_dict(f_work); percent = calculate_total_percent(f_work)
                st.markdown(f'<div class="owner-tag">👤 {wd["owner_name"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div><span class="type-badge">{wd["work_type"]}</span><small style="color:#B282E6;">{wd["event_date"]} {wd["event_name"]}</small></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:18px; font-weight:bold; color:#B282E6; margin-bottom:5px;">{wd["deadline"]}〆 {wd["title"]}</div>', unsafe_allow_html=True)
                col_bar, col_rd = st.columns([7, 1.5])
                with col_bar:
                    if percent >= 100:
                        st.markdown('<div style="margin: 10px 0;"><span class="complete-badge">✅ 完了済み</span></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="progress-container"><div class="progress-bar-fill" style="width:{percent}%;"></div></div><div style="text-align:right; font-size:10px; color:#B282E6;">{percent}%</div>', unsafe_allow_html=True)
                with col_rd:
                    if st.button("閲覧", key=f"v_f_btn_{wd['id']}", use_container_width=True, type="primary"): 
                        st.session_state.view_id, st.session_state.page = wd['id'], "view"
                        st.rerun()
        else:
            st.info("表示できる友達の原稿はありません。")

elif st.session_state.page == "daily":
    if st.button("◀", key="back_from_daily"): st.session_state.page = "list"; st.rerun()
    c.execute("SELECT * FROM works WHERE user_id = ?", (st.session_state.user_id,))
    works = c.fetchall()
    if works:
        titles = [w[2] for w in works]; sel_title = st.selectbox("作品名", titles)
        w = next(x for x in works if x[2] == sel_title)
        wd = get_work_dict(w); unit, labels = get_labels_from_type(wd['work_type'], wd['novel_unit'])
        p = st.number_input(f"{labels[0]} (%)", min_value=0, key="daily_p")
        n = st.number_input(f"{labels[1]} ({unit})", min_value=0, key="daily_n")
        l = st.number_input(f"{labels[2]} ({unit})", min_value=0, key="daily_l")
        t = st.number_input(f"{labels[3]} ({unit})", min_value=0, key="daily_t") if wd['work_type'] != "小説" else 0
        cov = st.number_input(f"表紙 (%)", min_value=0, key="daily_cov") if wd['has_cover'] else 0
        ill = st.number_input(f"挿絵 (枚)", min_value=0, key="daily_ill") if (wd['work_type'] == "小説" and wd['has_illustrations']) else 0
        if st.button("保存", type="primary", key="daily_save"):
            note = format_log_note(p, n, l, t, wd['work_type'], unit, labels, cov, ill)
            c.execute("INSERT INTO progress_logs (work_id, update_date, note, p_diff, n_diff, l_diff, t_diff, cov_diff, ill_diff) VALUES (?,?,?,?,?,?,?,?,?)", (wd['id'], datetime.now().strftime("%Y/%m/%d %H:%M"), note, p, n, l, t, cov, ill))
            conn.commit(); update_work_totals(wd['id']); st.session_state.page = "list"; st.rerun()

elif st.session_state.page == "form":
    is_e = st.session_state.edit_id is not None
    if is_e:
        row = c.execute("SELECT * FROM works WHERE id=?", (st.session_state.edit_id,)).fetchone()
        wd = get_work_dict(row)
    else:
        wd = {"title":"","total_pages":1,"event_name":"","event_date":str(date.today()),"deadline":str(date.today()),"work_type":"漫画","novel_unit":"文字","has_illustrations":0,"total_illustrations":0,"has_cover":0}

    if st.button("◀", key="back_from_form"): st.session_state.page = "list"; st.rerun()
    st.subheader("原稿スケジュールの" + ("編集" if is_e else "追加"))
    
    w_type = st.radio("ジャンル", ["漫画", "イラスト", "小説"], index=["漫画", "イラスト", "小説"].index(wd.get('work_type','漫画')), horizontal=True, key="form_type")
    n_unit, h_ill, t_ill, h_cov = wd.get('novel_unit','文字'), wd.get('has_illustrations',0), wd.get('total_illustrations',0), wd.get('has_cover',0)
    
    if w_type == "小説":
        n_unit = st.radio("管理単位", ["文字", "ページ"], index=0 if n_unit=="文字" else 1, horizontal=True, key="form_unit")
        h_ill = 1 if st.checkbox("挿絵あり", value=bool(h_ill), key="form_h_ill") else 0
        if h_ill: t_ill = st.number_input("目標の挿絵枚数", min_value=1, value=max(1, t_ill), key="form_t_ill")
        h_cov = 1 if st.checkbox("表紙あり", value=bool(h_cov), key="form_h_cov_novel") else 0
    elif w_type == "漫画": 
        h_cov = 1 if st.checkbox("表紙あり", value=bool(h_cov), key="form_h_cov_manga") else 0
    
    t = st.text_input("作品名", value=wd.get('title',''), key="form_title")
    pg = st.number_input(f"目標の数 ({'P' if w_type!='小説' else n_unit})", min_value=1, value=wd.get('total_pages',1), key="form_target")
    ev = st.text_input("イベント名", value=wd.get('event_name',''), key="form_event")
    ed = st.date_input("イベント日", value=date.fromisoformat(wd.get('event_date', str(date.today()))), key="form_edate")
    dd = st.date_input("締切日", value=date.fromisoformat(wd.get('deadline', str(date.today()))), key="form_deadline")
    
    if st.button("保存", type="primary", use_container_width=True, key="form_save_btn"):
        if is_e:
            c.execute("UPDATE works SET title=?, total_pages=?, event_name=?, event_date=?, deadline=?, work_type=?, has_illustrations=?, total_illustrations=?, has_cover=?, novel_unit=? WHERE id=?", (t, pg, ev, str(ed), str(dd), w_type, h_ill, t_ill, h_cov, n_unit, wd['id']))
        else:
            c.execute("INSERT INTO works (user_id, title, total_pages, event_name, event_date, deadline, work_type, has_illustrations, total_illustrations, has_cover, novel_unit) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (st.session_state.user_id, t, pg, ev, str(ed), str(dd), w_type, h_ill, t_ill, h_cov, n_unit))
        conn.commit(); st.session_state.page = "list"; st.rerun()
    
    if is_e:
        st.markdown("---")
        with st.expander("危険な操作"):
            if st.button("この作品を削除する", type="secondary", key="del_work_btn"):
                c.execute("DELETE FROM progress_logs WHERE work_id=?", (wd['id'],))
                c.execute("DELETE FROM works WHERE id=?", (wd['id'],))
                conn.commit(); st.session_state.page = "list"; st.rerun()

elif st.session_state.page == "log_all":
    if st.button("◀", key="back_from_logall"): st.session_state.page = "list"; st.session_state.log_edit_id = None; st.rerun()
    
    # ON/OFF設定に基づいたクエリ
    if show_friends_config:
        query = """
            SELECT pl.id, pl.update_date, pl.note, w.title, u.username, u.id, 
                   pl.p_diff, pl.n_diff, pl.l_diff, pl.t_diff, pl.cov_diff, pl.ill_diff, 
                   w.id, w.work_type, w.novel_unit, w.has_cover, w.has_illustrations
            FROM progress_logs pl JOIN works w ON pl.work_id = w.id JOIN users u ON w.user_id = u.id 
            WHERE w.user_id = ? OR w.user_id IN (SELECT friend_id FROM friends WHERE user_id = ?) ORDER BY pl.id DESC
        """
        params = (st.session_state.user_id, st.session_state.user_id)
    else:
        query = """
            SELECT pl.id, pl.update_date, pl.note, w.title, u.username, u.id, 
                   pl.p_diff, pl.n_diff, pl.l_diff, pl.t_diff, pl.cov_diff, pl.ill_diff, 
                   w.id, w.work_type, w.novel_unit, w.has_cover, w.has_illustrations
            FROM progress_logs pl JOIN works w ON pl.work_id = w.id JOIN users u ON w.user_id = u.id 
            WHERE w.user_id = ? ORDER BY pl.id DESC
        """
        params = (st.session_state.user_id,)

    c.execute(query, params)
    
    for log in c.fetchall():
        lid, ldate, lnote, wtitle, uname, uid, lp, ln, ll, lt, lcov, lill, wid, wtype, lunit, h_cov, h_ill = log
        is_mine = (uid == st.session_state.user_id)
        
        if st.session_state.log_edit_id == lid:
            with st.container():
                st.markdown(f'<div style="color:#B282E6; font-size:1.2rem; font-weight:bold;">ログ編集: {wtitle} ({ldate})</div>', unsafe_allow_html=True)
                unit, labels = get_labels_from_type(wtype, lunit)
                ep = st.number_input(f"{labels[0]} (%)", value=lp, key=f"edit_p_{lid}")
                en = st.number_input(f"{labels[1]} ({unit})", value=ln, key=f"edit_n_{lid}")
                el = st.number_input(f"{labels[2]} ({unit})", value=ll, key=f"edit_l_{lid}")
                et = st.number_input(f"{labels[3]} ({unit})", value=lt, key=f"edit_t_{lid}") if wtype != "小説" else 0
                ec = st.number_input("表紙 (%)", value=lcov, key=f"edit_cov_{lid}") if h_cov else 0
                ei = st.number_input("挿絵 (枚)", value=lill, key=f"edit_ill_{lid}") if (wtype == "小説" and h_ill) else 0
                
                c_s1, c_s2 = st.columns(2)
                with c_s1:
                    if st.button("更新保存", key=f"log_save_{lid}", type="primary"):
                        nn = format_log_note(ep, en, el, et, wtype, unit, labels, ec, ei)
                        c.execute("UPDATE progress_logs SET note=?, p_diff=?, n_diff=?, l_diff=?, t_diff=?, cov_diff=?, ill_diff=? WHERE id=?", (nn, ep, en, el, et, ec, ei, lid))
                        conn.commit(); update_work_totals(wid); st.session_state.log_edit_id = None; st.rerun()
                with c_s2:
                    if st.button("取消", key=f"log_cancel_{lid}"): st.session_state.log_edit_id = None; st.rerun()
        else:
            col_txt, col_btn = st.columns([7.5, 2.5])
            with col_txt: st.markdown(f'<div class="log-card"><small>{ldate} - {uname}<br>{wtitle}</small><br><b>{lnote}</b></div>', unsafe_allow_html=True)
            with col_btn:
                if is_mine:
                    c1, c2 = st.columns(2)
                    if c1.button("編集", key=f"log_ebtn_{lid}"): st.session_state.log_edit_id = lid; st.rerun()
                    if c2.button("削除", key=f"log_dbtn_{lid}"):
                        c.execute("DELETE FROM progress_logs WHERE id=?", (lid,)); conn.commit(); update_work_totals(wid); st.rerun()

elif st.session_state.page == "view":
    c.execute("SELECT works.*, users.username FROM works JOIN users ON works.user_id = users.id WHERE works.id=?", (st.session_state.view_id,))
    row = c.fetchone(); wd = get_work_dict(row); uname = row[21] if row else "不明"
    if st.button("◀", key="back_from_view"): st.session_state.page = "list"; st.rerun()
    st.subheader(f"{uname}さんの：{wd['title']}")
    
    p = calculate_total_percent(row)
    if p >= 100:
        st.markdown('<div style="text-align:center; padding: 20px; background:#f0fff0; border-radius:15px; border:2px solid #4CAF50; color:#4CAF50; font-weight:bold; font-size:1.5rem; margin-bottom:20px;">🎉 完了済み (100.0%)</div>', unsafe_allow_html=True)
    else:
        st.progress(p/100)
        st.write(f"全体の進捗: **{p}%**")

    unit, labels = get_labels_from_type(wd['work_type'], wd['novel_unit'])
    st.write(f"**{labels[0]}**: {wd['plot_percent']} / 100 %")
    st.write(f"**{labels[1]}**: {wd['name_pages']} / {wd['total_pages']} {unit}")
    st.write(f"**{labels[2]}**: {wd['line_pages']} / {wd['total_pages']} {unit}")
    if wd['work_type'] != "小説": st.write(f"**{labels[3]}**: {wd['tone_pages']} / {wd['total_pages']} {unit}")
    if wd['has_cover']: st.write(f"**表紙**: {wd['cover_percent']} / 100 %")
    if wd['has_illustrations']: st.write(f"**挿絵**: {wd['draft_pages']} / {wd['total_illustrations']} 枚")

elif st.session_state.page == "add_friend":
    if st.button("◀", key="back_from_friend"): st.session_state.page = "list"; st.rerun()
    fn, fp = st.text_input("友達のユーザー名", key="f_user"), st.text_input("友達のパスワード", type="password", key="f_pass")
    if st.button("追加", type="primary", key="f_add_btn"):
        c.execute("SELECT id, password FROM users WHERE username=?", (fn,))
        res = c.fetchone()
        if res and check_hashes(fp, res[1]):
            try: 
                c.execute("INSERT INTO friends (user_id, friend_id) VALUES (?,?)", (st.session_state.user_id, res[0]))
                conn.commit(); st.success("追加しました！")
            except: st.error("既に追加されています")
        else: st.error("ユーザー名またはパスワードが違います")
