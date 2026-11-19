"""
Global CSS for the sustainability theme:
forest green and sage accents on white and light grey.
"""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --forest: #2D5A3D;
    --forest-dark: #1F4029;
    --sage: #8DAA91;
    --sage-light: #E8EFE9;
    --bg: #F5F7F5;
    --card: #FFFFFF;
    --border: #E2E8E3;
    --text: #1E2A22;
    --muted: #6B7A70;
    --alert: #A9443A;
    --alert-bg: #FBEDEA;
    --warn: #A87523;
    --warn-bg: #FBF3E3;
    --ok: #2D6E46;
    --ok-bg: #E6F2E9;
    --neutral: #5E6B63;
    --neutral-bg: #EEF1EF;
}

html, body, .stApp, [class*="css"], button, input, textarea, select {
    font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;
}
.stApp { background: var(--bg); color: var(--text); }

#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }
.wq-brand { padding: 0.25rem 0.25rem 1.25rem 0.25rem; border-bottom: 1px solid var(--border); margin-bottom: 1rem; }
.wq-brand-mark { width: 34px; height: 34px; border-radius: 9px; background: var(--forest);
    display: inline-flex; align-items: center; justify-content: center; color: #fff;
    font-weight: 700; font-size: 0.95rem; margin-bottom: 0.6rem; }
.wq-brand-title { font-size: 1.05rem; font-weight: 700; color: var(--text); line-height: 1.3; }
.wq-brand-sub { font-size: 0.8rem; color: var(--muted); }

[data-testid="stSidebar"] [role="radiogroup"] { gap: 0.25rem; }
[data-testid="stSidebar"] [role="radiogroup"] label {
    padding: 0.6rem 0.8rem; border-radius: 8px; width: 100%;
    transition: background 0.15s ease; cursor: pointer;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: var(--sage-light); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background: var(--sage-light); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { color: var(--forest); font-weight: 600; }
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child { display: none; }
[data-testid="stSidebar"] [role="radiogroup"] label p { font-size: 0.92rem; color: var(--text); }

.wq-sidebar-foot { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border);
    font-size: 0.75rem; color: var(--muted); line-height: 1.6; }

/* ---------- Page header ---------- */
.wq-header { margin-bottom: 1.6rem; }
.wq-header h1 { font-size: 1.65rem; font-weight: 700; color: var(--text); margin: 0; padding: 0; letter-spacing: -0.01em; }
.wq-header p { color: var(--muted); margin: 0.3rem 0 0 0; font-size: 0.95rem; }

.wq-section { font-size: 1rem; font-weight: 600; color: var(--text); margin: 1.8rem 0 0.75rem 0; }
.wq-section span { font-weight: 400; color: var(--muted); font-size: 0.85rem; margin-left: 0.4rem; }

/* ---------- Cards ---------- */
.wq-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.15rem 1.3rem; }
.wq-metric-label { font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
.wq-metric-value { font-size: 2rem; font-weight: 700; color: var(--forest); margin-top: 0.35rem; line-height: 1.1; }
.wq-metric-value.alert { color: var(--alert); }
.wq-metric-note { font-size: 0.8rem; color: var(--muted); margin-top: 0.35rem; }

[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
    background: var(--card); border-radius: 12px; border-color: var(--border);
}

.wq-loc-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.wq-loc-name { font-size: 1.05rem; font-weight: 600; color: var(--text); }
.wq-loc-area { font-size: 0.82rem; color: var(--muted); margin-left: 0.5rem; }
.wq-meta { font-size: 0.82rem; color: var(--muted); margin: 0.6rem 0 0.2rem 0; }
.wq-meta b { color: var(--text); font-weight: 500; }

/* ---------- Status badges ---------- */
.wq-badge { display: inline-block; padding: 0.22rem 0.7rem; border-radius: 999px;
    font-size: 0.74rem; font-weight: 600; letter-spacing: 0.01em; white-space: nowrap; }
.wq-badge::before { content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 50%;
    margin-right: 0.4rem; vertical-align: middle; background: currentColor; position: relative; top: -1px; }
.wq-badge.alert { background: var(--alert-bg); color: var(--alert); }
.wq-badge.ok { background: var(--ok-bg); color: var(--ok); }
.wq-badge.warn { background: var(--warn-bg); color: var(--warn); }
.wq-badge.neutral { background: var(--neutral-bg); color: var(--neutral); }

/* ---------- Banners ---------- */
.wq-banner { border-radius: 10px; padding: 0.95rem 1.15rem; border: 1px solid; border-left-width: 4px; margin: 0.75rem 0; }
.wq-banner-title { font-weight: 600; font-size: 0.98rem; }
.wq-banner-text { font-size: 0.86rem; margin-top: 0.2rem; }
.wq-banner.ok { background: var(--ok-bg); border-color: #CFE3D5; border-left-color: var(--ok); color: var(--ok); }
.wq-banner.alert { background: var(--alert-bg); border-color: #F1D3CE; border-left-color: var(--alert); color: var(--alert); }
.wq-banner.neutral { background: var(--card); border-color: var(--border); border-left-color: var(--sage); color: var(--neutral); }

/* ---------- Tables ---------- */
.wq-table-wrap { overflow-x: auto; }
.wq-table { width: 100%; border-collapse: separate; border-spacing: 0; background: var(--card);
    border: 1px solid var(--border); border-radius: 12px; overflow: hidden; font-size: 0.86rem; }
.wq-table th { background: #F8FAF8; color: var(--muted); text-transform: uppercase; font-size: 0.7rem;
    letter-spacing: 0.05em; font-weight: 600; text-align: left; padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); }
.wq-table td { padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); color: var(--text); vertical-align: middle; }
.wq-table tr:last-child td { border-bottom: none; }
.wq-table tr:hover td { background: #FAFCFA; }
.wq-muted { color: var(--muted); }

.wq-empty { background: var(--card); border: 1px dashed var(--border); border-radius: 12px;
    padding: 1.6rem; text-align: center; color: var(--muted); font-size: 0.9rem; }

.wq-live-note { font-size: 0.82rem; color: var(--muted); margin-top: 0.4rem; }

/* ---------- Drone telemetry ---------- */
.wq-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; margin: 0.9rem 0 0.4rem 0; }
.wq-stat { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 0.7rem 0.9rem; }
.wq-stat-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
.wq-stat-value { font-size: 1.05rem; font-weight: 600; color: var(--text); margin-top: 0.25rem; }
.wq-stat-value.alert { color: var(--alert); }
.st-key-drone_emergency button { background: var(--alert) !important; border-color: var(--alert) !important; }
.st-key-drone_emergency button:hover { background: #8E372E !important; border-color: #8E372E !important; }
.st-key-drone_disconnect button { background: #FFFFFF !important; color: var(--forest) !important; border-color: var(--sage) !important; }

/* ---------- Widgets ---------- */
.stButton > button, .stFormSubmitButton > button {
    background: var(--forest); color: #FFFFFF; border: 1px solid var(--forest);
    border-radius: 8px; padding: 0.45rem 1.1rem; font-weight: 500; width: 100%;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
    background: var(--forest-dark); border-color: var(--forest-dark); color: #FFFFFF;
}
.stButton > button:disabled { background: #D5DDD7; border-color: #D5DDD7; color: #FFFFFF; }
.stButton > button:focus:not(:active) { color: #FFFFFF; }

[data-testid="stFileUploaderDropzone"] { background: var(--card); border: 1px dashed var(--sage); border-radius: 12px; }
[data-testid="stExpander"] details { background: var(--card); border-radius: 12px; border-color: var(--border); }
[data-testid="stImage"] img, [data-testid="stImageContainer"] img { border-radius: 10px; }
</style>
"""


def apply_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
