from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

try:
    for _secret_name in ("CLICKBAIT_DB_CONNECTION", "CLICKBAIT_JWT_SECRET", "CLICKBAIT_MODEL_PATH"):
        if _secret_name in st.secrets:
            os.environ.setdefault(_secret_name, str(st.secrets[_secret_name]))
except StreamlitSecretNotFoundError:
    pass

from api import ExplainableSignalsResponse, PredictResponse
from auth_api import database, password_hash, password_matches
from clickbait_model import ClickbaitDetector


st.set_page_config(page_title="Baitbuster AI", page_icon="🧠", layout="wide", initial_sidebar_state="collapsed")


@st.cache_resource
def load_detector(model_path: str) -> ClickbaitDetector:
    return ClickbaitDetector.load(model_path)


def write_uploaded_thumbnail(uploaded_file) -> Path:
    suffix = Path(uploaded_file.name).suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
        temporary_file.write(uploaded_file.getbuffer())
        return Path(temporary_file.name)


def clear_inputs() -> None:
    st.session_state["headline"] = ""
    st.session_state["thumbnail"] = None
    st.session_state["result"] = None
    st.session_state["result_has_thumbnail"] = False


def probability_label(value: float) -> str:
    if value >= 0.75:
        return "High signal"
    if value >= 0.45:
        return "Watch closely"
    return "Low signal"


def public_user(row) -> dict:
    return {
        "id": row.UserId,
        "username": row.Username,
        "role": row.Role,
        "created_at": row.CreatedAt.isoformat(),
    }


def register_user(username: str, password: str) -> dict:
    if len(username.strip()) < 3 or len(password) < 4:
        raise ValueError("Username must be 3+ characters and password 4+ characters.")
    with database.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO dbo.Users (Username, PasswordHash, Role) OUTPUT INSERTED.UserId, INSERTED.Username, INSERTED.Role, INSERTED.CreatedAt VALUES (?, ?, 'user')",
            username.strip(),
            password_hash(password),
        )
        row = cursor.fetchone()
    return public_user(row)


def login_user(username: str, password: str) -> dict:
    row = database.user(username.strip())
    if not row or not password_matches(password, row.PasswordHash):
        raise ValueError("Invalid username or password.")
    return public_user(row)


def save_prediction(user: dict | None, headline: str, result) -> None:
    guest_session_id = st.session_state.get("guest_session_id") if user is None else None
    response = PredictResponse(
        label=result.label,
        clickbait_probability=result.clickbait_probability,
        not_clickbait_probability=result.not_clickbait_probability,
        confidence=result.confidence,
        headline_probability=result.headline_probability,
        thumbnail_probability=result.thumbnail_probability,
        signals=ExplainableSignalsResponse(**vars(result.signals)),
    )
    database.save_prediction(int(user["id"]) if user else None, headline, response, guest_session_id)


st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;700;800&family=Space+Grotesk:wght@600;700&display=swap');
        :root { font-family: 'Manrope', sans-serif; }
        .stApp { background: radial-gradient(circle at 88% 0%, rgba(214,112,70,.24), transparent 28rem), radial-gradient(circle at 8% 55%, rgba(65,145,132,.12), transparent 25rem), #171b1e; color: #f5f0e8; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stToolbar"] { visibility: hidden; }
        [data-testid="stSidebar"] { background: #20282a; border-right: 1px solid #394348; }
        [data-testid="stSidebar"] * { font-family: 'Manrope', sans-serif; }
        .block-container { max-width: 1240px; padding: 1.5rem 2.5rem 2rem; }
        .brand { display: flex; align-items: center; border-bottom: 1px solid #384044; padding-bottom: 1.4rem; color: #f5f0e8; font-weight: 800; letter-spacing: .2px; }
        .brand-mark { display: inline-grid; place-items: center; width: 31px; height: 31px; color: #ff9b6b; border: 1px solid #ff9b6b; border-radius: 9px; margin-right: 10px; }
        .topbar { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #384044; padding-bottom: 1.4rem; }
        .topbar .brand { border: 0; padding: 0; }
        .model-status { display: flex; align-items: center; gap: 8px; color: #8c9997; font: 10px 'DM Mono', monospace; letter-spacing: .6px; text-transform: uppercase; }
        .status-dot { width: 7px; height: 7px; border-radius: 50%; background: #6ee0bc; box-shadow: 0 0 12px #6ee0bc; }
        .eyebrow, .kicker { color: #ff9b6b; font: 10px 'DM Mono', monospace; letter-spacing: 1.5px; text-transform: uppercase; }
        .intro { max-width: 840px; padding: 4.5rem 0 2.7rem; }
        .intro h1 { margin: 1rem 0 .8rem; color: #f5f0e8; font: 700 clamp(43px, 6vw, 79px)/.98 'Space Grotesk', sans-serif; letter-spacing: -3px; }
        .intro h1 em { color: #ff9b6b; font-style: normal; }
        .intro p { max-width: 600px; color: #b6bfbd; line-height: 1.65; font-size: 15px; }
        .panel { min-height: 560px; padding: 1.7rem; border: 1px solid #394348; border-radius: 17px; background: rgba(29,35,37,.86); box-shadow: 0 20px 70px rgba(0,0,0,.2); }
        .panel h2 { color: #f5f0e8; font-size: 20px; }
        .panel-heading { color: #ff9b6b; font-size: 21px; }
        .empty { padding: 9rem 2rem 2rem; color: #8191a3; text-align: center; }
        .empty h2 { color: #f5f0e8; }
        .verdict { margin-top: .5rem; color: #ff9b72; font-size: 27px; font-weight: 800; letter-spacing: -1px; }
        .score { color: #fca26d; font-size: 57px; font-weight: 800; letter-spacing: -3px; }
        .score-copy { margin: .5rem 0 0; color: #8fa0b2; font-size: 11px; line-height: 1.5; }
        .badge { display: inline-block; margin: 1rem .4rem 0 0; padding: 6px 9px; border: 1px solid rgba(105,208,159,.25); border-radius: 999px; color: #8ae3bf; background: rgba(105,208,159,.12); font: 10px 'DM Mono', monospace; text-transform: uppercase; }
        footer { display: flex; justify-content: space-between; padding-top: 1.5rem; color: #64758a; font: 9px 'DM Mono', monospace; letter-spacing: .5px; }
        label, .stTextArea label, .stFileUploader label { color: #c7cfcc !important; font-size: 12px !important; font-weight: 700 !important; }
        [data-testid="stFileUploaderDropzone"] { min-height: 145px; border: 1px dashed #526165; border-radius: 10px; background: rgba(35,45,46,.7); }
        [data-testid="stFileUploaderDropzoneInstructions"] { color: #9eafc1; }
        [data-testid="stFileUploaderDropzoneInstructions"] small { color: #64758b; }
        [data-testid="stTextArea"] textarea { min-height: 126px; color: #f2f4f1; background: #20282a; border: 1px solid #465258; border-radius: 10px; line-height: 1.55; }
        [data-testid="stTextArea"] textarea:focus { border-color: #ff9b6b; box-shadow: 0 0 0 3px rgba(255,155,107,.1); }
        .stButton > button { min-height: 40px; border: 1px solid #465258; border-radius: 8px; color: #dce5e2; background: transparent; font-size: 11px; }
        .stButton > button:hover { border-color: #ff9b6b; color: #ffb18c; }
        .stButton > button[kind="primary"] { border: 0; color: #171b1e; background: #ff9b6b; font-weight: 800; }
        .stButton > button[kind="primary"]:hover { color: #171b1e; background: #ffb28c; }
        [data-testid="stCaptionContainer"] { color: #73817f; font: 10px 'DM Mono', monospace; text-transform: uppercase; letter-spacing: .3px; }
        [data-testid="stProgressBar"] > div > div { background: #fca26d; }
        [data-testid="stMetricValue"] { color: #fca26d; }
        @media (max-width: 800px) { .block-container { padding: 1rem; } .intro { padding: 3rem 0 2rem; } .intro h1 { letter-spacing: -2px; } footer { gap: 10px; flex-direction: column; } }
    </style>
    """,
    unsafe_allow_html=True,
)

if "result" not in st.session_state:
    st.session_state["result"] = None
if "result_has_thumbnail" not in st.session_state:
    st.session_state["result_has_thumbnail"] = False
if "user" not in st.session_state:
    st.session_state["user"] = None
if "guest_session_id" not in st.session_state:
    st.session_state["guest_session_id"] = secrets.token_urlsafe(32)

with st.sidebar:
    st.markdown("### Baitbuster account")
    current_user = st.session_state["user"]
    if current_user:
        st.success(f"Signed in as {current_user['username']}")
        st.caption("Administrator" if current_user["role"] == "admin" else "Member")
        if st.button("Sign out", use_container_width=True):
            st.session_state["user"] = None
            st.rerun()

        with st.expander("Change password"):
            with st.form("change_password_form"):
                current_password = st.text_input("Current password", type="password")
                new_password = st.text_input("New password", type="password")
                change_password_clicked = st.form_submit_button("Update password", use_container_width=True)
            if change_password_clicked:
                if len(new_password) < 4:
                    st.error("New password must be at least 4 characters.")
                else:
                    try:
                        with database.connect() as connection:
                            row = database.user_by_id(int(current_user["id"]))
                            if not row or not password_matches(current_password, row.PasswordHash):
                                raise ValueError("Current password is incorrect.")
                            connection.cursor().execute(
                                "UPDATE dbo.Users SET PasswordHash = ? WHERE UserId = ?",
                                password_hash(new_password),
                                int(current_user["id"]),
                            )
                        st.success("Password changed successfully.")
                    except Exception as error:
                        st.error(str(error))

        with st.expander("Scan history"):
            try:
                history_items = database.history(None if current_user["role"] == "admin" else int(current_user["id"]))
                if not history_items:
                    st.caption("No saved scans yet.")
                for item in history_items[:20]:
                    st.markdown(f"**{item['headline'] or 'Image-only scan'}**")
                    st.caption(f"{item['label']} - {item['clickbait_probability']:.0%} confidence - {item['created_at']}")
            except Exception as error:
                st.error(f"Could not load history: {error}")
    else:
        login_tab, register_tab = st.tabs(["Sign in", "Register"])
        with login_tab:
            with st.form("login_form"):
                login_username = st.text_input("Username", key="login_username")
                login_password = st.text_input("Password", type="password", key="login_password")
                login_clicked = st.form_submit_button("Sign in", use_container_width=True)
            if login_clicked:
                try:
                    st.session_state["user"] = login_user(login_username, login_password)
                    st.rerun()
                except Exception as error:
                    st.error(str(error))
        with register_tab:
            with st.form("register_form"):
                register_username = st.text_input("Username", key="register_username")
                register_password = st.text_input("Password", type="password", key="register_password")
                register_clicked = st.form_submit_button("Create account", use_container_width=True)
            if register_clicked:
                try:
                    st.session_state["user"] = register_user(register_username, register_password)
                    st.rerun()
                except Exception as error:
                    st.error(str(error))
        st.caption("You can scan as a guest. Sign in to save history.")
        with st.expander("This session's scans"):
            try:
                guest_history = database.history(guest_session_id=st.session_state["guest_session_id"])
                if not guest_history:
                    st.caption("No saved scans in this session yet.")
                for item in guest_history[:20]:
                    st.markdown(f"**{item['headline'] or 'Image-only scan'}**")
                    st.caption(f"{item['label']} - {item['clickbait_probability']:.0%} - {item['created_at']}")
            except Exception as error:
                st.error(f"Could not load guest history: {error}")

st.markdown('<div class="topbar"><div class="brand"><span class="brand-mark">⌕</span> Baitbuster AI</div><div class="model-status"><span class="status-dot"></span> Model online</div></div>', unsafe_allow_html=True)
st.markdown(
    '<section class="intro"><div class="eyebrow">HEADLINE + VISUAL INTELLIGENCE</div><h1>Spot the <em>clickbait</em><br>before it spots you.</h1><p>Drop in a headline, a thumbnail, or both. Our AI will analyze the signals and give you a clear, explainable score.</p><div class="eyebrow" style="margin-top:1.5rem">⚡ FAST SIGNAL SCAN &nbsp;&nbsp;&nbsp; • &nbsp;&nbsp;&nbsp; EXPLAINABLE OUTPUT</div></section>',
    unsafe_allow_html=True,
)

artifacts_dir = Path(__file__).resolve().parent / "artifacts"
default_model = artifacts_dir / "clickbait_detector.joblib"
if not default_model.exists():
    default_model = artifacts_dir / "youtube_detector.joblib"
model_path = Path(os.getenv("CLICKBAIT_MODEL_PATH", str(default_model)))

input_column, result_column = st.columns([0.9, 1.1], gap="medium")
with input_column:
    st.markdown('<div class="panel"><div class="panel-heading">INPUT</div><h2>Bring something to inspect</h2>', unsafe_allow_html=True)
    st.text_area("Headline or video title", max_chars=500, height=126, placeholder="Paste the headline you are not quite sure about...", key="headline")
    st.caption("Try a quick scan")
    quick_scans = [
        "You will not believe what happened next",
        "The simple habit that changed my mornings",
        "Local team announces a new community project",
    ]
    quick_columns = st.columns(3)
    for index, scan in enumerate(quick_scans):
        if quick_columns[index].button(scan, key=f"quick_scan_{index}", use_container_width=True):
            st.session_state["headline"] = scan
            st.session_state["result"] = None
            st.rerun()
    st.file_uploader("Thumbnail image", type=["png", "jpg", "jpeg", "webp"], key="thumbnail")
    predict_column, clear_column = st.columns(2)
    predict_clicked = predict_column.button("Scan for signals", type="primary", use_container_width=True)
    clear_column.button("Clear", use_container_width=True, on_click=clear_inputs)
    st.markdown('</div>', unsafe_allow_html=True)

if predict_clicked:
    headline = st.session_state.get("headline", "")
    thumbnail = st.session_state.get("thumbnail")
    if not headline.strip() and thumbnail is None:
        st.warning("Add a headline or a thumbnail before analyzing.")
    elif not model_path.exists():
        st.error(f"Model not found: {model_path}")
    else:
        detector = load_detector(str(model_path))
        thumbnail_path = write_uploaded_thumbnail(thumbnail) if thumbnail is not None else None
        try:
            result = detector.predict([{"headline": headline, "thumbnail_path": thumbnail_path}])[0]
            st.session_state["result"] = result
            st.session_state["result_has_thumbnail"] = thumbnail is not None
            try:
                save_prediction(st.session_state["user"], headline, result)
            except Exception as error:
                st.warning(f"Prediction completed, but history was not saved: {error}")
        finally:
            if thumbnail_path is not None:
                thumbnail_path.unlink(missing_ok=True)

with result_column:
    result = st.session_state.get("result")
    if result is None:
        st.markdown('<div class="panel empty"><div class="kicker">RESULT</div><h2>Your readout will land here</h2><p>Submit a headline, thumbnail, or both to see the model confidence and language signals behind it.</p></div>', unsafe_allow_html=True)
    else:
        label = "Likely clickbait" if result.label == "clickbait" else "Likely not clickbait"
        signal_values = vars(result.signals)
        lead_signal = max(signal_values, key=signal_values.get)
        thumbnail_probability = result.thumbnail_probability if st.session_state["result_has_thumbnail"] else 0.0
        st.markdown(f'<div class="panel"><div class="kicker">02 / RESULT</div><div class="verdict">{label}</div><span class="badge">{probability_label(result.clickbait_probability)}</span><span class="badge">Lead signal: {lead_signal.replace("_", " ")}</span><div style="margin-top:2rem"><div class="score">{result.clickbait_probability:.1%}</div><div class="kicker">FUSED CLICKBAIT PROBABILITY</div></div>', unsafe_allow_html=True)
        st.progress(result.clickbait_probability)
        st.markdown(f"<p class='score-copy'>{'The combined evidence leans toward attention engineering.' if result.label == 'clickbait' else 'The combined evidence looks relatively grounded.'}</p>", unsafe_allow_html=True)
        confidence_column, headline_column, thumbnail_column = st.columns(3)
        confidence_column.metric("Confidence", f"{result.confidence:.1%}")
        headline_column.metric("Headline / DistilBERT", f"{result.headline_probability:.1%}")
        thumbnail_column.metric("Thumbnail / CLIP", f"{thumbnail_probability:.1%}")
        st.markdown('<div class="kicker" style="margin-top:1.5rem">EXPLAINABILITY</div><h3>What pushed the score</h3>', unsafe_allow_html=True)
        for name, value in signal_values.items():
            signal_column, value_column = st.columns([3, 1])
            signal_column.write(f"**{name.replace('_', ' ').title()}**")
            value_column.write(f"{value:.0%}")
            st.progress(value)
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<footer><span>CLICKBAIT AI / RESEARCH PREVIEW</span><span>Signals are probabilistic, not a verdict.</span></footer>', unsafe_allow_html=True)