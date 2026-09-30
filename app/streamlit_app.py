import sys
import base64
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
SPORTIQ_LOGO_PATH = ASSETS_DIR / "sportiq_logo.png"
SPORTIQ_ICON_PATH = ASSETS_DIR / "sportiq_icon.png"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path = [
    p for p in sys.path
    if Path(p).resolve() != APP_DIR
]
import html
from datetime import datetime

import streamlit as st

from app.services.ai_service import AIService
from app.services.database_service import DatabaseService
from app.services.kickoff_service import KickoffService


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="SportIQ",
    page_icon="assets/sportiq_icon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)


def image_data_uri(path):
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return ""


SPORTIQ_LOGO_URI = image_data_uri(SPORTIQ_LOGO_PATH)
SPORTIQ_ICON_URI = image_data_uri(SPORTIQ_ICON_PATH)


# =========================================================
# CUSTOM CSS
# =========================================================

st.html(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stApp, button, input, textarea {
        font-family: "Inter", sans-serif !important;
    }

    .stApp, [data-testid="stAppViewContainer"] { background:#080b12; color:#f8fafc; }
    [data-testid="stHeader"] { background:transparent; }
    [data-testid="stSidebar"] { background:#0d111a; border-right:1px solid #1d2633; }
    [data-testid="stSidebar"] > div:first-child { padding-top:1.5rem; }

    .brand-logo {
        width:34px; height:34px; border-radius:10px;
        display:inline-block; object-fit:cover; object-position:center;
        margin-right:9px; vertical-align:middle;
        border:1px solid #315579;
        box-shadow:0 8px 24px rgba(37,99,235,.18);
    }
    .sportiq-brand { font-size:26px; font-weight:800; color:#fff; margin-bottom:2px; }
    .sportiq-subtitle { font-size:12px; color:#7f8da3; margin-bottom:25px; }
    .sidebar-footer { margin-top:35px; padding-top:15px; border-top:1px solid #202733; font-size:11px; color:#586579; line-height:1.6; }
    .sidebar-team { display:flex; align-items:center; gap:10px; background:#131a25; border:1px solid #202a38; border-radius:10px; padding:8px 10px; margin-bottom:7px; color:#dce4ef; font-size:13px; }
    .sidebar-team-logo { width:30px; height:30px; object-fit:contain; flex-shrink:0; }

    [data-testid="stSidebar"] .stButton, [data-testid="stSidebar"] .stButton > button { width:100% !important; }
    [data-testid="stSidebar"] .stButton > button { justify-content:flex-start !important; text-align:left !important; }
    [data-testid="stSidebar"] .stButton > button p { text-align:left !important; margin:0 !important; }

    .page-header { margin-bottom:26px; }
    .page-header-title { font-size:34px; line-height:1.15; font-weight:800; letter-spacing:-1px; color:#fff; margin-bottom:7px; }
    .page-header-subtitle { font-size:15px; color:#8491a5; }

    .hero-card, .next-match-card, .squad-team-card, .monitor-card, .standings-card, .social-card, .broadcast-card, .match-card {
        background:linear-gradient(135deg,#111827 0%,#0d1420 55%,#101827 100%);
        border:1px solid #253247; border-radius:18px; padding:28px; margin-bottom:20px;
        box-shadow:0 18px 50px rgba(0,0,0,.20);
    }
    .hero-card { padding:36px; position:relative; overflow:hidden; }
    .hero-card:after { content:""; position:absolute; width:260px; height:260px; right:-100px; top:-120px; border-radius:50%; background:radial-gradient(circle,rgba(59,130,246,.16),transparent 68%); pointer-events:none; }
    .hero-eyebrow, .next-match-eyebrow { font-size:11px; font-weight:800; letter-spacing:1.8px; color:#60a5fa; margin-bottom:10px; text-transform:uppercase; }
    .hero-title { font-size:30px; font-weight:800; color:#fff; margin-bottom:10px; }
    .hero-text { max-width:760px; font-size:14px; line-height:1.7; color:#9aa8bb; }

    .stat-card { background:linear-gradient(145deg,#101824,#0c121c); border:1px solid #202c3d; border-radius:16px; padding:18px 20px; min-height:100px; box-shadow:0 10px 30px rgba(0,0,0,.12); }
    .stat-label { font-size:10px; text-transform:uppercase; letter-spacing:1.2px; color:#64748b; margin-bottom:8px; }
    .stat-value { font-size:25px; font-weight:800; color:#fff; letter-spacing:-.5px; }
    .stat-note { font-size:11px; color:#718096; margin-top:5px; }
    .quick-card { background:#0f151f; border:1px solid #202a38; border-radius:14px; padding:18px; min-height:112px; }
    .quick-icon { font-size:22px; margin-bottom:10px; }
    .quick-title { color:#fff; font-size:14px; font-weight:800; margin-bottom:5px; }
    .quick-text { color:#718096; font-size:12px; line-height:1.55; }
    .dashboard-nav-button > button {
        width:100% !important; min-height:128px !important;
        padding:18px !important; border-radius:14px !important;
        border:1px solid #202a38 !important;
        background:#0f151f !important; color:#fff !important;
        text-align:left !important; white-space:pre-line !important;
        box-shadow:none !important;
        transition:all .18s ease !important;
    }
    .dashboard-nav-button > button:hover {
        transform:translateY(-2px); border-color:#315b94 !important;
        background:#111b2a !important; box-shadow:0 12px 30px rgba(0,0,0,.22) !important;
    }
    .dashboard-nav-button > button p {
        white-space:pre-line !important; text-align:left !important;
        line-height:1.55 !important; margin:0 !important;
    }
    .dashboard-nav-button > button p {
        white-space:pre-line !important; text-align:left !important;
        line-height:1.55 !important; margin:0 !important;
    }

    .dashboard-card {
        background:linear-gradient(145deg,#101824,#0c121c);
        border:1px solid #202c3d; border-radius:16px; padding:20px;
        min-height:138px; box-shadow:0 10px 30px rgba(0,0,0,.12);
        transition:all .18s ease;
    }
    .dashboard-card:hover { border-color:#315b94; box-shadow:0 14px 34px rgba(0,0,0,.22); transform:translateY(-2px); }
    .dashboard-card-icon { font-size:22px; margin-bottom:12px; }
    .dashboard-card-title { color:#fff; font-size:13px; font-weight:800; letter-spacing:.5px; margin-bottom:5px; }
    .dashboard-card-value { color:#fff; font-size:24px; font-weight:800; margin-bottom:4px; }
    .dashboard-card-text { color:#718096; font-size:12px; line-height:1.5; }
    .dashboard-card-link { color:#60a5fa; font-size:11px; font-weight:800; letter-spacing:.5px; text-transform:uppercase; margin-top:12px; }
    .dashboard-team-card {
        background:linear-gradient(145deg,#111827,#0d1420); border:1px solid #253247;
        border-radius:16px; padding:20px; min-height:190px;
        box-shadow:0 10px 30px rgba(0,0,0,.14); transition:all .18s ease;
    }
    .dashboard-team-card:hover { border-color:#315b94; transform:translateY(-2px); box-shadow:0 14px 34px rgba(0,0,0,.22); }
    .dashboard-team-logo { width:68px; height:68px; object-fit:contain; display:block; margin-bottom:12px; }
    .dashboard-team-name { color:#fff; font-size:17px; font-weight:800; margin-bottom:4px; }
    .dashboard-team-meta { color:#718096; font-size:12px; }
    [class*="st-key-dashboard-card-"] button {
        background:transparent !important; border:none !important; padding:0 !important;
        min-height:0 !important; width:auto !important; color:#60a5fa !important;
        font-size:11px !important; font-weight:800 !important; text-transform:uppercase;
        letter-spacing:.5px; box-shadow:none !important;
    }
    [class*="st-key-dashboard-card-"] button:hover {
        color:#93c5fd !important; background:transparent !important; border:none !important;
        transform:none !important; box-shadow:none !important;
    }

    .dashboard-link-hint {
        margin-top:10px; color:#60a5fa; font-size:11px; font-weight:800;
        letter-spacing:.5px; text-transform:uppercase;
    }
    .dashboard-stat-button > button {
        width:100% !important; min-height:104px !important; padding:18px 20px !important;
        border-radius:16px !important; text-align:left !important;
        background:linear-gradient(145deg,#101824,#0c121c) !important;
        border:1px solid #202c3d !important;
        transition:all .18s ease !important;
    }
    .dashboard-stat-button > button:hover {
        transform:translateY(-2px); border-color:#315b94 !important;
        box-shadow:0 12px 30px rgba(0,0,0,.22) !important;
    }
    .dashboard-stat-button > button p { white-space:pre-line !important; text-align:left !important; line-height:1.45 !important; }
    .dashboard-team-button > button {
        width:100% !important; min-height:165px !important; padding:18px 20px !important;
        border-radius:14px !important; text-align:left !important;
        background:#0f151f !important; border:1px solid #202a38 !important;
        transition:all .18s ease !important;
    }
    .dashboard-team-button > button:hover {
        transform:translateY(-2px); border-color:#315b94 !important;
        background:#111b2a !important; box-shadow:0 12px 30px rgba(0,0,0,.22) !important;
    }
    .page-jump { margin:0 0 20px; }
    .page-jump > button { border-radius:10px !important; }

    .section-title { font-size:20px; font-weight:750; color:#fff; margin-top:10px; margin-bottom:15px; }
    .muted { color:#8190a5; font-size:13px; }
    .tiny { color:#64748b; font-size:11px; }
    .score { font-size:34px; font-weight:800; color:#fff; letter-spacing:-1px; }
    .status-live { color:#fca5a5; font-weight:800; letter-spacing:.8px; }
    .status-final { color:#86efac; font-weight:800; letter-spacing:.8px; }
    .status-scheduled { color:#93c5fd; font-weight:800; letter-spacing:.8px; }
    .stats-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; padding:10px 0; border-bottom:1px solid #202a38; }
    .stats-row { display:grid; grid-template-columns:1fr 1.5fr 1fr; gap:10px; align-items:center; padding:9px 0; border-bottom:1px solid #182231; }

    .team-card, .watchlist-card, .search-result-card, .squad-player-card, .news-card {
        background:#0f151f; border:1px solid #202a38; border-radius:14px; padding:18px 20px; margin-bottom:12px;
    }
    .team-card { min-height:165px; }
    .team-logo-wrapper { height:70px; display:flex; align-items:center; margin-bottom:12px; }
    .team-logo { width:65px; height:65px; object-fit:contain; }
    .team-name, .watchlist-team-name, .search-result-name { font-size:16px; font-weight:700; color:#fff; margin-bottom:5px; }
    .team-meta, .watchlist-team-meta, .search-result-meta { font-size:12px; color:#738197; line-height:1.6; }

    .next-match-teams { display:flex; align-items:center; justify-content:center; gap:34px; margin:8px 0 24px; }
    .next-match-team { flex:1; max-width:250px; font-size:21px; font-weight:800; color:#fff; text-align:center; line-height:1.3; }
    .next-match-logo { width:78px; height:78px; object-fit:contain; margin:0 auto 10px; display:block; }
    .next-match-vs { font-size:14px; font-weight:700; color:#66758a; letter-spacing:1px; }
    .next-match-venue { font-size:14px; font-weight:600; color:#d8e1ec; text-align:center; margin-bottom:9px; }
    .next-match-meta { font-size:13px; color:#8190a5; text-align:center; line-height:1.7; }
    .next-match-team-label { margin-top:5px; font-size:10px; font-weight:700; letter-spacing:1px; color:#64748b; }
    .fixture-counter { text-align:center; font-size:11px; color:#64748b; font-weight:700; letter-spacing:.8px; margin:3px 0 5px; }

    .squad-team-logo { width:82px; height:82px; object-fit:contain; }
    .squad-team-name { font-size:25px; font-weight:800; color:#fff; margin-bottom:6px; }
    .squad-team-meta { font-size:13px; color:#8190a5; line-height:1.7; }
    .squad-player-card { min-height:350px; padding:14px; }
    .squad-player-photo { width:100%; height:210px; object-fit:contain; border-radius:10px; background:#111827; display:block; margin-bottom:12px; }
    .squad-player-name { font-size:15px; font-weight:800; color:#fff; margin-bottom:5px; }
    .squad-player-meta { font-size:12px; color:#8190a5; line-height:1.7; }
    .squad-status-available { color:#86efac; font-size:11px; font-weight:800; text-transform:uppercase; }
    .squad-status-injured { color:#fca5a5; font-size:11px; font-weight:800; text-transform:uppercase; }
    .squad-status-neutral { color:#cbd5e1; font-size:11px; font-weight:800; text-transform:uppercase; }
    .squad-injury { margin-top:8px; padding-top:8px; border-top:1px solid #202a38; color:#fca5a5; font-size:11px; line-height:1.6; }

    .standings-table { width:100%; border-collapse:collapse; font-size:13px; }
    .standings-table th { color:#64748b; text-transform:uppercase; letter-spacing:.7px; font-size:10px; text-align:left; padding:10px 8px; border-bottom:1px solid #253247; }
    .standings-table td { color:#dce4ef; padding:12px 8px; border-bottom:1px solid #182231; }
    .standings-table tr.highlight td { background:#111d2d; color:#fff; font-weight:700; }

    .incident { background:#111827; border:1px solid #202a38; border-radius:10px; padding:10px 12px; margin-bottom:8px; font-size:12px; color:#cbd5e1; }
    .social-card { padding:18px 20px; }
    .social-title { font-size:15px; font-weight:800; color:#fff; margin-bottom:7px; }
    .social-text { color:#9aa8bb; font-size:13px; line-height:1.6; }
    .broadcast-card { padding:16px 18px; }
    .broadcast-name { font-size:14px; font-weight:800; color:#fff; }

    .stButton > button { border-radius:9px; border:1px solid #263244; background:#121a27; color:#dbe5f1; font-weight:600; }
    .stButton > button:hover { border-color:#3b82f6; color:#fff; background:#172235; }
    .stTextInput input, .stSelectbox [data-baseweb="select"] { background:#0f151f !important; color:#fff !important; border-radius:10px !important; }
    [data-testid="stChatMessage"] { background:#0f151f; border:1px solid #202a38; border-radius:12px; }
    .sportiq-footer { margin-top:45px; padding-top:18px; border-top:1px solid #202733; text-align:center; font-size:11px; color:#536174; }
    .sidebar-section { color:#64748b; font-size:10px; font-weight:800; letter-spacing:1.2px; text-transform:uppercase; margin:20px 0 9px; }
    .chat-intro { background:linear-gradient(135deg,#111a28,#0e1520); border:1px solid #253247; border-radius:16px; padding:20px 22px; margin-bottom:18px; }
    .chat-intro-title { color:#fff; font-size:17px; font-weight:800; margin-bottom:5px; }
    .chat-intro-text { color:#8190a5; font-size:12px; line-height:1.6; }
    </style>
    """
)


# =========================================================
# SERVICES
# =========================================================

@st.cache_resource
def get_database():
    return DatabaseService()


@st.cache_resource
def get_ai_service(user_id):
    return AIService(user_id=user_id)


@st.cache_resource
def get_football_service():
    return KickoffService()


def get_watchlist(user_id):
    return get_database().get_teams(user_id)


@st.cache_data(ttl=3600)
def get_team_logo(team_name):
    if not team_name:
        return None
    try:
        football = get_football_service()
        team = football.get_bsd_team(team_name)
        if not team:
            return None
        team_id = team.get("id")
        return football.get_bsd_team_logo(team_id) if team_id is not None else None
    except Exception:
        return None


def ask_agent(user_id, message):
    return get_ai_service(user_id).run_agent(message)


def execute_mcp_tool(user_id, tool_name, arguments=None):
    return get_ai_service(user_id)._execute_mcp_tool(tool_name, arguments or {})


@st.cache_data(ttl=900)
def get_team_news(user_id, team_name):
    return execute_mcp_tool(user_id, "get_team_news", {"team_name": team_name})


@st.cache_data(ttl=900)
def get_team_squad(user_id, team_name):
    return execute_mcp_tool(user_id, "get_team_squad", {"team_name": team_name})


@st.cache_data(ttl=900)
def get_team_standings(user_id, team_name):
    return execute_mcp_tool(user_id, "get_league_standings", {"team_name": team_name})


@st.cache_data(ttl=3600)
def get_match_broadcasts(user_id, event_id, country_code=None):
    args = {"event_id": int(event_id)}
    if country_code:
        args["country_code"] = country_code
    return execute_mcp_tool(user_id, "get_match_broadcasts", args)


@st.cache_data(ttl=900)
def get_match_social(user_id, event_id, limit=10):
    return execute_mcp_tool(user_id, "get_match_social", {"event_id": int(event_id), "limit": limit})


@st.cache_data(ttl=900)
def get_team_social(user_id, team_name, limit=10):
    return execute_mcp_tool(user_id, "get_team_social", {"team_name": team_name, "limit": limit})


@st.cache_data(ttl=30)
def get_match_monitor(user_id, home_team, away_team, match_date):
    return execute_mcp_tool(
        user_id,
        "monitor_match",
        {
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
        },
    )


@st.cache_data(ttl=30)
def get_live_matches(user_id):
    return execute_mcp_tool(user_id, "get_live_matches", {})


def get_bsd_live_match_details(event_id):
    """Fetch uncached match details for live monitoring."""
    return get_football_service().get_bsd_match_details(int(event_id))


# =========================================================
# HELPERS
# =========================================================

def esc(value):
    return html.escape(str(value)) if value is not None else ""


def first_value(data, *keys, default=None):
    if not isinstance(data, dict):
        return default
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return default


def score_value(data, side):
    return first_value(
        data,
        f"{side}_score",
        f"{side}_goals",
        default=None,
    )


def normalize_status(value):
    return str(value or "").strip().lower()


def status_class(value):
    s = normalize_status(value)
    if any(x in s for x in ["live", "progress", "playing", "1h", "2h"]):
        return "status-live"
    if any(x in s for x in ["finished", "ft", "ended", "complete"]):
        return "status-final"
    return "status-scheduled"


def format_score(home_score, away_score):
    if home_score is None and away_score is None:
        return "—"
    return f"{home_score if home_score is not None else 0} - {away_score if away_score is not None else 0}"


def render_logo(url, size=72, fallback="◇"):
    if url:
        return f'<img src="{esc(url)}" style="width:{size}px;height:{size}px;object-fit:contain;" alt="team logo">'
    return f'<div style="width:{size}px;height:{size}px;display:flex;align-items:center;justify-content:center;font-size:{max(28, size//2)}px;">{fallback}</div>'


def render_fixture_card(fixture, label="UPCOMING FIXTURE", show_monitor=False, user_id=None):
    home = first_value(fixture, "home_team", default="Unknown")
    away = first_value(fixture, "away_team", default="Unknown")
    home_logo = first_value(fixture, "home_logo")
    away_logo = first_value(fixture, "away_logo")
    venue = first_value(fixture, "venue")
    venue_city = first_value(fixture, "venue_city")
    local_date = first_value(fixture, "local_date", default="Date unavailable")
    local_time = first_value(fixture, "local_time", default="Time unavailable")
    timezone_name = first_value(fixture, "local_timezone")
    competition = first_value(fixture, "competition_display_name", "competition_name", default="Competition unavailable")
    round_label = first_value(fixture, "round_label", "stage_name")
    event_id = first_value(fixture, "event_id", "id")
    venue_text = f"🏟️ {venue}" if venue else "🏟️ Venue unavailable"
    if venue_city:
        venue_text += f" • {venue_city}"
    competition_line = f"🏆 {competition}" + (f" • {round_label}" if round_label else "")
    timezone_text = f" • {timezone_name}" if timezone_name else ""
    location = first_value(fixture, "home_away")
    location_label = "🏠 HOME" if location == "Home" else "✈️ AWAY" if location == "Away" else "⚽ FIXTURE"

    st.html(
        f"""
        <div class="match-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:22px;">
                <div class="next-match-eyebrow">{esc(label)}</div>
                <div class="tiny">{esc(location_label)}</div>
            </div>
            <div style="display:flex;align-items:center;justify-content:center;gap:35px;margin-bottom:25px;">
                <div style="flex:1;text-align:center;">
                    {render_logo(home_logo, 72)}
                    <div style="font-size:18px;font-weight:800;color:#fff;line-height:1.3;">{esc(home)}</div>
                    <div class="tiny">HOME</div>
                </div>
                <div style="min-width:70px;text-align:center;font-size:13px;font-weight:800;color:#64748b;letter-spacing:1.5px;">VS</div>
                <div style="flex:1;text-align:center;">
                    {render_logo(away_logo, 72)}
                    <div style="font-size:18px;font-weight:800;color:#fff;line-height:1.3;">{esc(away)}</div>
                    <div class="tiny">AWAY</div>
                </div>
            </div>
            <div style="border-top:1px solid #202a38;padding-top:18px;text-align:center;">
                <div style="font-size:13px;font-weight:600;color:#d8e1ec;margin-bottom:9px;">{esc(venue_text)}</div>
                <div class="next-match-meta">📅 {esc(local_date)} &nbsp; • &nbsp; ⏰ {esc(local_time)}{esc(timezone_text)}<br>{esc(competition_line)}</div>
            </div>
        </div>
        """
    )

    if show_monitor and event_id:
        return event_id
    return None


def render_social_items(items, title="Social"):
    if not items:
        st.info(f"No {title.lower()} items are currently available.")
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        item_title = first_value(item, "title", "type", default="Social update")
        text = first_value(item, "text", "description", default="No text available.")
        published = first_value(item, "published_at", "publishedAt")
        url = first_value(item, "url")
        account = item.get("account") if isinstance(item.get("account"), dict) else {}
        handle = first_value(account, "handle", "name")
        media = item.get("media")
        media_url = None
        if isinstance(media, dict):
            media_url = first_value(media, "url", "video_url", "image_url")
        elif isinstance(media, list) and media and isinstance(media[0], dict):
            media_url = first_value(media[0], "url", "video_url", "image_url")
        st.html(
            f"""
            <div class="social-card">
                <div class="social-title">{esc(item_title)}</div>
                <div class="tiny">{esc(handle or '')}{' • ' if handle and published else ''}{esc(published or '')}</div>
                <div class="social-text" style="margin-top:9px;">{esc(text)}</div>
                {('<div style="margin-top:10px;"><a href="' + esc(media_url) + '" target="_blank" style="color:#60a5fa;font-size:12px;font-weight:700;text-decoration:none;">Media ↗</a></div>') if media_url else ''}
                {('<div style="margin-top:8px;"><a href="' + esc(url) + '" target="_blank" style="color:#60a5fa;font-size:12px;font-weight:700;text-decoration:none;">Open post ↗</a></div>') if url else ''}
            </div>
            """
        )


def render_broadcasts(items):
    if not items:
        st.info("No broadcast information is currently available.")
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        channel = first_value(item, "channel_name", "name", default="Broadcast")
        country = first_value(item, "country_code")
        link = first_value(item, "channel_link", "url")
        text = esc(channel) + (f" • {esc(country)}" if country else "")
        st.html(
            f"""
            <div class="broadcast-card">
                <div class="broadcast-name">📺 {text}</div>
                {('<div style="margin-top:7px;"><a href="' + esc(link) + '" target="_blank" style="color:#60a5fa;font-size:12px;font-weight:700;text-decoration:none;">Open broadcaster ↗</a></div>') if link else ''}
            </div>
            """
        )


def render_standings(result):
    rows = result.get("standings", []) if isinstance(result, dict) else []
    team_standing = result.get("team_standing") if isinstance(result, dict) else None
    if not rows:
        st.info("No standings are currently available.")
        return
    if not isinstance(rows, list):
        rows = [rows]

    def row_team_data(row):
        team = row.get("team") if isinstance(row.get("team"), dict) else {}
        team_name = first_value(team, "name", "team_name") or first_value(row, "team_name", "name", default="Unknown")
        team_id = first_value(team, "id", "team_id") or first_value(row, "team_id", "id")
        logo = (
            first_value(team, "logo", "logo_url", "team_logo", "team_logo_url", "crest", "badge")
            or first_value(row, "team_logo", "team_logo_url", "logo", "logo_url", "crest", "badge")
        )
        if not logo and team_id is not None:
            logo = get_football_service().get_bsd_team_logo(int(team_id))
        return team_name, logo

    # Render one real table.  The previous implementation opened a new
    # <table> for every club, which made the standings look like separate
    # cards instead of a single league table.
    table_rows = []

    selected_id = team_standing.get("team_id") if isinstance(team_standing, dict) else result.get("team_id")

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue

        team_name, team_logo = row_team_data(row)
        rank = first_value(row, "position", "rank", "place", default=index)
        mp = first_value(row, "played", "matches_played", "mp", "games_played", default="—")
        wins = first_value(row, "wins", "won", "w", default="—")
        draws = first_value(row, "draws", "draw", "d", default="—")
        losses = first_value(row, "losses", "lost", "l", default="—")
        gf = first_value(row, "goals_for", "gf", default="—")
        ga = first_value(row, "goals_against", "ga", default="—")
        gd = first_value(row, "goal_difference", "gd", default="—")
        pts = first_value(row, "points", "pts", default="—")
        row_team_id = first_value(row, "team_id", "id")
        nested_team = row.get("team") if isinstance(row.get("team"), dict) else {}
        row_team_id = row_team_id or first_value(nested_team, "id", "team_id")
        highlight = (
            selected_id is not None and str(row_team_id) == str(selected_id)
        ) or (
            selected_id is None
            and isinstance(team_standing, dict)
            and str(team_name).strip().lower() == str(first_value(team_standing, "team_name", "name", default="")).strip().lower()
        )
        logo_html = render_logo(team_logo, 30, "⚽")
        team_cell = f'<div style="display:flex;align-items:center;gap:10px;min-width:190px;">{logo_html}<span style="font-weight:700;color:#fff;">{esc(team_name)}</span></div>'
        row_class = "highlight" if highlight else ""

        table_rows.append(
            f'<tr class="{row_class}">'
            f'<td class="standings-pos">{esc(rank)}</td><td>{team_cell}</td>'
            f'<td>{esc(mp)}</td><td>{esc(wins)}</td><td>{esc(draws)}</td><td>{esc(losses)}</td>'
            f'<td>{esc(gf)}</td><td>{esc(ga)}</td><td>{esc(gd)}</td>'
            f'<td class="standings-points">{esc(pts)}</td></tr>'
        )

    if not table_rows:
        st.info("No usable standings rows were returned.")
        return

    st.html(
        '<div class="standings-card"><div style="overflow-x:auto;">'
        '<table class="standings-table"><thead><tr>'
        '<th>#</th><th>Team</th><th>MP</th><th>W</th><th>D</th><th>L</th>'
        '<th>GF</th><th>GA</th><th>GD</th><th>Pts</th>'
        '</tr></thead><tbody>'
        + "".join(table_rows)
        + '</tbody></table></div></div>'
    )


# =========================================================
# SESSION STATE
# =========================================================

for key, default in {
    "user_id": None,
    "username": None,
    "page": "Dashboard",
    "watchlist_search_results": None,
    "watchlist_search_query": "",
    "next_fixture_team_index": 0,
    "chat_messages": [],
    "match_center_team": None,
    "squad_team": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# =========================================================
# LOGIN
# =========================================================

if st.session_state.user_id is None:
    st.html(
        f"""
        <div style="max-width:700px;margin:105px auto 32px;text-align:center;">
            <div style="display:inline-flex;align-items:center;justify-content:center;width:110px;height:110px;border-radius:26px;background:#080b12;border:1px solid #29405d;box-shadow:0 18px 45px rgba(0,0,0,.25);margin-bottom:22px;overflow:hidden;"><img src="{SPORTIQ_LOGO_URI}" style="width:100%;height:100%;object-fit:cover;" alt="SportIQ logo"></div>
            <div style="font-size:46px;font-weight:800;color:#fff;letter-spacing:-1.8px;">Welcome to SportIQ</div>
            <div style="margin-top:11px;color:#8190a5;font-size:15px;">Your personal football intelligence workspace.</div>
            <div style="margin:20px auto 0;max-width:520px;color:#64748b;font-size:12px;line-height:1.7;">Follow your teams, explore fixtures and squads, track matches, read news, and ask the AI about your football world.</div>
        </div>
        """
    )
    username = st.text_input("What's your username?", placeholder="Enter your username")
    if st.button("Continue", type="primary", use_container_width=True):
        username = username.strip()
        if not username:
            st.error("Please enter a username.")
        else:
            user = get_database().get_or_create_user(username)
            st.session_state.user_id = user["id"]
            st.session_state.username = user["username"]
            st.rerun()
    st.stop()
    

user_id = st.session_state.user_id
username = st.session_state.username
teams = get_watchlist(user_id)
if not teams:
    st.session_state.next_fixture_team_index = 0
elif st.session_state.next_fixture_team_index >= len(teams):
    st.session_state.next_fixture_team_index = 0


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.html(f'<div class="sportiq-brand"><img class="brand-logo" src="{SPORTIQ_ICON_URI}" alt="SportIQ logo">SportIQ</div><div class="sportiq-subtitle">Football Intelligence, built around you</div>')
    st.html('<div class="sidebar-section">Workspace</div>')

    nav = [
        ("⌂  Dashboard", "Dashboard"),
        ("▣  Fixtures", "Fixtures"),
        ("☷  Standings", "Standings"),
        ("◉  Match Center", "Match Center"),
        ("▤  News", "News"),
        ("☆  Watchlist", "Watchlist"),
        ("♙  Squad", "Squad"),
        ("✦  AI Chat", "AI Chat"),
    ]
    for label, page in nav:
        if st.button(label, use_container_width=True, key=f"nav_{page}"):
            st.session_state.page = page
            st.rerun()

    st.html('<div class="sidebar-section">Following</div>')
    if teams:
        for team in teams:
            name = team.get("name")
            logo = get_team_logo(name)
            if logo:
                st.html(f'<div class="sidebar-team"><img class="sidebar-team-logo" src="{esc(logo)}"><span>{esc(name)}</span></div>')
            else:
                st.html(f'<div class="sidebar-team"><span><img class="brand-logo" src="{SPORTIQ_ICON_URI}" style="width:24px;height:24px;margin:0;border-radius:7px;vertical-align:middle;" alt="SportIQ logo"></span><span>{esc(name)}</span></div>')
    else:
        st.caption("No teams added yet.")

    st.html('<div class="sidebar-footer">Live football data • AI assistant<br>Built for your football workspace</div>')


# =========================================================
# DASHBOARD
# =========================================================

if st.session_state.page == "Dashboard":
    st.html(f'<div class="page-header"><div class="page-header-title">Welcome back, {esc(username)} 👋</div><div class="page-header-subtitle">Your football world, powered by AI.</div></div>')
    st.html('<div class="hero-card"><div class="hero-eyebrow">SPORTIQ</div><div class="hero-title">Your football command center</div><div class="hero-text">Everything you follow in one place — fixtures, standings, squads, news, match coverage, live events, and an AI assistant that can work with current football data.</div></div>')

    col1, col2, col3, col4 = st.columns(4)
    stats = [
        (col1, "👥", "FOLLOWED TEAMS", str(len(teams)), "Your followed clubs", "Open Watchlist →", "Watchlist"),
        (col2, "📅", "NEXT FIXTURE", "Ready" if teams else "—", "Upcoming match coverage", "Open Fixtures →", "Fixtures"),
        (col3, "📡", "MATCH CENTER", "Live", "Match monitoring & events", "Open Match Center →", "Match Center"),
        (col4, "🤖", "AI CHAT", "Ready", "Ask about your football world", "Open AI Chat →", "AI Chat"),
    ]
    for col, icon, label, value, text_value, link_text, page in stats:
        with col:
            st.html(
                f'<div class="dashboard-card">'
                f'<div class="dashboard-card-icon">{icon}</div>'
                f'<div class="dashboard-card-title">{esc(label)}</div>'
                f'<div class="dashboard-card-value">{esc(value)}</div>'
                f'<div class="dashboard-card-text">{esc(text_value)}</div>'
                f'</div>'
            )
            with st.container(key=f"dashboard-card-stat-{page.lower().replace(' ', '-')}"):
                if st.button(link_text, key=f"dashboard_stat_{page}"):
                    st.session_state.page = page
                    st.rerun()

    st.html('<div class="section-title" style="margin-top:30px;">Explore SportIQ</div>')
    q1, q2, q3, q4 = st.columns(4)
    quick = [
        (q1, "◫", "FIXTURES", "Upcoming matches and match coverage", "Open Fixtures →", "Fixtures"),
        (q2, "◉", "MATCH CENTER", "Live events, stats and monitoring", "Open Match Center →", "Match Center"),
        (q3, "◇", "SQUAD", "Players, positions and availability", "Open Squad →", "Squad"),
        (q4, "✦", "AI CHAT", "Ask natural-language football questions", "Open AI Chat →", "AI Chat"),
    ]
    for col, icon, title, text_value, link_text, page in quick:
        with col:
            st.html(
                f'<div class="dashboard-card">'
                f'<div class="dashboard-card-icon">{icon}</div>'
                f'<div class="dashboard-card-title">{esc(title)}</div>'
                f'<div class="dashboard-card-text">{esc(text_value)}</div>'
                f'</div>'
            )
            with st.container(key=f"dashboard-card-quick-{page.lower().replace(' ', '-')}"):
                if st.button(link_text, key=f"dashboard_nav_{page}"):
                    st.session_state.page = page
                    st.rerun()

    st.html('<div class="section-title" style="margin-top:25px;">More workspace</div>')
    m1, m2, m3, m4 = st.columns(4)
    more = [
        (m1, "▤", "STANDINGS", "League tables", "Open Standings →", "Standings"),
        (m2, "⌁", "NEWS", "Team news and social", "Open News →", "News"),
        (m3, "☆", "WATCHLIST", "Manage followed teams", "Open Watchlist →", "Watchlist"),
        (m4, "⌂", "DASHBOARD", "Return to overview", "Current page →", "Dashboard"),
    ]
    for col, icon, title, text_value, link_text, page in more:
        with col:
            st.html(
                f'<div class="dashboard-card">'
                f'<div class="dashboard-card-icon">{icon}</div>'
                f'<div class="dashboard-card-title">{esc(title)}</div>'
                f'<div class="dashboard-card-text">{esc(text_value)}</div>'
                f'</div>'
            )
            with st.container(key=f"dashboard-card-more-{page.lower().replace(' ', '-')}"):
                if st.button(link_text, key=f"dashboard_more_{page}"):
                    st.session_state.page = page
                    st.rerun()

    st.html('<div class="section-title">Next fixture</div>')
    if teams:
        index = st.session_state.next_fixture_team_index
        team_name = teams[index].get("name")
        if len(teams) > 1:
            a, b, c = st.columns([1,3,1])
            with a:
                if st.button("←", key="dashboard_prev", use_container_width=True):
                    st.session_state.next_fixture_team_index = (index - 1) % len(teams)
                    st.rerun()
            with b:
                st.html(f'<div class="fixture-counter">{esc(team_name)} • {index+1} of {len(teams)}</div>')
            with c:
                if st.button("→", key="dashboard_next", use_container_width=True):
                    st.session_state.next_fixture_team_index = (index + 1) % len(teams)
                    st.rerun()
        else:
            st.html(f'<div class="fixture-counter">{esc(team_name)}</div>')

        try:
            result = execute_mcp_tool(user_id, "get_upcoming_matches", {"team_name": team_name})
        except Exception as error:
            result = {"status":"error", "error":str(error)}
        fixtures = result.get("fixtures", []) if isinstance(result, dict) and result.get("status") == "success" else []
        if fixtures:
            render_fixture_card(fixtures[0])
            st.markdown('<div class="page-jump">', unsafe_allow_html=True)
            if st.button("Open Fixtures →", key="dashboard_open_fixtures", use_container_width=True):
                st.session_state.page = "Fixtures"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info(f"No upcoming fixture available for {team_name}.")
    else:
        st.info("Add a team to your watchlist to see its next match.")

    st.html('<div class="section-title">Your teams</div>')
    if teams:
        cols = st.columns(min(len(teams), 3))
        for i, team in enumerate(teams):
            with cols[i % len(cols)]:
                name = team.get("name")
                country = team.get("country") or "Unknown country"
                logo = get_team_logo(name)
                logo_html = render_logo(logo, 68, "⚽")
                st.html(
                    f'<div class="dashboard-team-card">'
                    f'{logo_html}'
                    f'<div class="dashboard-team-name">{esc(name)}</div>'
                    f'<div class="dashboard-team-meta">{esc(country)}</div>'
                    f'</div>'
                )
                with st.container(key=f"dashboard-card-team-{team.get('id', i)}"):
                    if st.button("Open Squad →", key=f"dashboard_team_{team.get('id', i)}"):
                        st.session_state.squad_team = name
                        st.session_state.page = "Squad"
                        st.rerun()
    else:
        st.info("Your watchlist is empty. Open Watchlist to add your first team.")


# =========================================================
# FIXTURES
# =========================================================

elif st.session_state.page == "Fixtures":
    st.html('<div class="page-header"><div class="page-header-title">Fixtures</div><div class="page-header-subtitle">Upcoming matches for your followed teams, with broadcast and social coverage.</div></div>')
    if not teams:
        st.info("Your watchlist is empty.")
    else:
        for team in teams:
            team_name = team.get("name")
            st.html(f'<div class="section-title">{esc(team_name)}</div>')
            try:
                result = execute_mcp_tool(user_id, "get_upcoming_matches", {"team_name": team_name})
            except Exception as error:
                st.error(f"Could not load fixtures for {team_name}: {error}")
                continue
            fixtures = result.get("fixtures", []) if isinstance(result, dict) and result.get("status") == "success" else []
            if not fixtures:
                st.info(f"No upcoming fixtures are currently available for {team_name}.")
                continue
            for fixture_index, fixture in enumerate(fixtures):
                event_id = render_fixture_card(fixture)
                event_id = event_id or first_value(fixture, "event_id", "id")
                if event_id:
                    with st.expander("📺 Broadcasts & social", expanded=False):
                        bcol, scol = st.columns(2)
                        with bcol:
                            st.markdown("#### 📺 TV / Broadcast")
                            try:
                                b = get_match_broadcasts(user_id, event_id)
                                render_broadcasts(b.get("broadcasts", []) if isinstance(b, dict) else [])
                            except Exception as error:
                                st.error(f"Broadcast lookup failed: {error}")
                        with scol:
                            st.markdown("#### 📱 Match social")
                            try:
                                s = get_match_social(user_id, event_id, 5)
                                render_social_items(s.get("social", []) if isinstance(s, dict) else [], "Social")
                            except Exception as error:
                                st.error(f"Social lookup failed: {error}")


# =========================================================
# STANDINGS
# =========================================================

elif st.session_state.page == "Standings":
    st.html('<div class="page-header"><div class="page-header-title">Standings</div><div class="page-header-subtitle">Current league tables for your followed teams.</div></div>')
    if not teams:
        st.info("Add teams to your watchlist to see their league standings.")
    else:
        team_names = [t.get("name") for t in teams if t.get("name")]
        selected = st.selectbox("Select team", team_names, key="standings_team")
        if selected:
            with st.spinner(f"Loading standings for {selected}..."):
                try:
                    result = get_team_standings(user_id, selected)
                except Exception as error:
                    result = {"status":"error", "error":str(error)}
            if not isinstance(result, dict) or result.get("status") != "success":
                st.error(result.get("error", "Could not load standings.") if isinstance(result, dict) else "Unexpected response.")
            else:
                league_name = result.get("league_name") or "League standings"
                season_id = result.get("season_id")
                st.html(f'<div class="section-title">{esc(league_name)}</div>')
                render_standings(result)


# =========================================================
# MATCH CENTER / MONITOR
# =========================================================

def render_match_center(user_id):
    st.html('<div class="page-header"><div class="page-header-title">Match Center</div><div class="page-header-subtitle">Your selected favourite team’s next match. The match state refreshes automatically.</div></div>')

    if not teams:
        st.info("Add a team to your watchlist to use Match Center.")
        return

    team_names = [team.get("name") for team in teams if team.get("name")]
    if not team_names:
        st.info("Your watchlist does not contain a usable team name.")
        return

    default_index = 0
    if st.session_state.match_center_team in team_names:
        default_index = team_names.index(st.session_state.match_center_team)

    selected_team = st.selectbox(
        "Favourite team",
        team_names,
        index=default_index,
        key="match_center_team_select",
    )
    st.session_state.match_center_team = selected_team

    try:
        upcoming = execute_mcp_tool(
            user_id,
            "get_upcoming_matches",
            {"team_name": selected_team},
        )
    except Exception as error:
        st.error(f"Could not load the next match for {selected_team}: {error}")
        return

    fixtures = upcoming.get("fixtures", []) if isinstance(upcoming, dict) and upcoming.get("status") == "success" else []
    if not fixtures:
        st.info(f"No upcoming match is currently available for {selected_team}.")
        return

    # get_upcoming_matches already returns genuinely future fixtures sorted by date.
    fixture = fixtures[0]
    home = fixture.get("home_team") or "Home"
    away = fixture.get("away_team") or "Away"
    match_date_value = fixture.get("local_date") or fixture.get("date") or ""
    match_date = str(match_date_value)[:10]

    st.html(
        f'<div class="monitor-card"><div class="next-match-eyebrow">NEXT MATCH</div>'
        f'<div style="font-size:25px;font-weight:800;color:#fff;margin-bottom:8px;">{esc(home)} vs {esc(away)}</div>'
        f'<div class="muted">{esc(fixture.get("local_date") or match_date)} • {esc(fixture.get("local_time") or "Time unavailable")}</div></div>'
    )

    st.caption("🟢 Match state refreshes every 15 seconds while this page remains open.")

    # Prefer the event ID already returned by the next-fixture tool. This
    # keeps Match Center tied directly to the user's next match instead of
    # doing a second free-text match search every refresh.
    event_id = first_value(fixture, "event_id", "fixture_id", "id")

    if event_id is None:
        try:
            discovery = execute_mcp_tool(
                user_id,
                "monitor_match",
                {
                    "home_team": home,
                    "away_team": away,
                    "match_date": match_date,
                },
            )
        except Exception as error:
            discovery = {"status": "error", "message": str(error)}

        if not isinstance(discovery, dict) or discovery.get("status") != "success":
            st.error(
                discovery.get("message", discovery.get("error", "Could not monitor the next match."))
                if isinstance(discovery, dict)
                else "Unexpected response from match monitor."
            )
            return

        event_id = first_value(discovery, "event_id", "id")

    if event_id is None:
        st.error("The next match was found, but it did not return an event ID.")
        return

    # Broadcasts and social are separate lookups.  They must not depend on
    # `discovery`: when the next-fixture response already supplied an event
    # ID, the monitor_match fallback above is intentionally skipped.
    broadcasts = []
    social = []

    try:
        broadcast_result = get_match_broadcasts(user_id, event_id)
        if isinstance(broadcast_result, dict):
            broadcasts = broadcast_result.get("broadcasts", []) or []
    except Exception:
        broadcasts = []

    try:
        social_result = get_match_social(user_id, event_id, 10)
        if isinstance(social_result, dict):
            social = social_result.get("social", []) or []
    except Exception:
        social = []

    try:
        detail = get_bsd_live_match_details(event_id)
    except Exception as error:
        detail = {"error": str(error)}

    if not isinstance(detail, dict) or not detail or detail.get("error"):
        st.error(
            detail.get("error", "Could not retrieve the  match details.")
            if isinstance(detail, dict)
            else "Unexpected response."
        )
        return
    home_data = detail.get("home_team") if isinstance(detail.get("home_team"), dict) else {}
    away_data = detail.get("away_team") if isinstance(detail.get("away_team"), dict) else {}
    home = detail.get("home_team_name") or first_value(home_data, "name", default=st.session_state.monitor_home)
    away = detail.get("away_team_name") or first_value(away_data, "name", default=st.session_state.monitor_away)
    home_logo = first_value(home_data, "logo", "logo_url")
    away_logo = first_value(away_data, "logo", "logo_url")
    competition_logo = detail.get("competition_logo") or detail.get("competition_logo_url")
    hs = detail.get("home_score")
    aws = detail.get("away_score")
    raw = detail.get("raw") or detail.get("detail_raw") or {}
    match_status_raw = detail.get("status") or raw.get("status")
    current_minute = raw.get("current_minute")
    competition = detail.get("competition_name") or raw.get("league_name") or "Competition unavailable"
    round_label = raw.get("round_label") or raw.get("round_name") or detail.get("round")
    venue_name = detail.get("venue_name") or first_value(detail.get("venue", {}), "name")
    venue_city = detail.get("venue_city") or first_value(detail.get("venue", {}), "city")

    status_map = {
        "not_started": "Scheduled",
        "scheduled": "Scheduled",
        "1st_half": "LIVE • 1st Half",
        "2nd_half": "LIVE • 2nd Half",
        "half_time": "HT",
        "extra_time": "LIVE • Extra Time",
        "penalty_shootout": "Penalty Shootout",
        "finished": "FT",
        "after_extra_time": "AET",
        "postponed": "Postponed",
        "cancelled": "Cancelled",
        "suspended": "Suspended",
    }
    status_text = status_map.get(str(match_status_raw).lower(), str(match_status_raw or "Status unavailable").replace("_", " ").title())
    if current_minute is not None and str(match_status_raw).lower() in {"1st_half", "2nd_half", "extra_time"}:
        status_text = f"{status_text} • {current_minute}'"

    status_cls = "status-live" if str(match_status_raw).lower() in {"1st_half", "2nd_half", "extra_time"} else status_class(match_status_raw)

    competition_badge = render_logo(competition_logo, 30, "🏆") if competition_logo else ""

    st.html(
        f"""
        <div class="monitor-card">
            <div style="display:flex;align-items:center;justify-content:center;gap:8px;" class="tiny">
                {competition_badge}
                <span>EVENT {esc(event_id)} • {esc(competition)}</span>
            </div>
            <div style="display:flex;align-items:center;justify-content:center;gap:24px;margin:25px 0 15px;">
                <div style="flex:1;text-align:right;">
                    <div style="display:flex;align-items:center;justify-content:flex-end;gap:14px;">
                        <div style="font-size:23px;font-weight:800;color:#fff;">{esc(home)}</div>
                        {render_logo(home_logo, 64, "⚽")}
                    </div>
                </div>
                <div style="text-align:center;min-width:180px;">
                    <div class="score">{esc(format_score(hs, aws))}</div>
                    <div class="{status_cls}">{esc(status_text)}</div>
                </div>
                <div style="flex:1;text-align:left;">
                    <div style="display:flex;align-items:center;justify-content:flex-start;gap:14px;">
                        {render_logo(away_logo, 64, "⚽")}
                        <div style="font-size:23px;font-weight:800;color:#fff;">{esc(away)}</div>
                    </div>
                </div>
            </div>
            <div style="text-align:center;" class="tiny">{esc(round_label or '')}{' • ' if round_label and venue_name else ''}{esc(venue_name or '')}{' • ' if venue_name and venue_city else ''}{esc(venue_city or '')}</div>
        </div>
        """
    )

    left, right = st.columns(2)
    incidents = detail.get("incidents") or []
    statistics = detail.get("statistics") or {}
    stats = statistics.get("stats") if isinstance(statistics, dict) else statistics
    with left:
        st.markdown("#### ⚡ Match events")
        if isinstance(incidents, list) and incidents:
            for incident in incidents:
                if not isinstance(incident, dict):
                    continue
                minute_i = first_value(incident, "minute", "time", default="—")
                kind = first_value(incident, "type", "incident_type", default="Event")
                player = first_value(incident, "player_name", "player", default="")
                incident_text = first_value(incident, "text", "detail", "description", default="")
                extra = " • " + esc(player) if player else ""
                st.html(f'<div class="incident"><b>{esc(minute_i)}</b> • {esc(kind)}{extra}<br>{esc(incident_text)}</div>')
        else:
            st.info("No match incidents are currently available.")

        st.markdown("#### 📊 Live statistics")
        if isinstance(stats, dict) and (stats.get("home") or stats.get("away")):
            home_stats = stats.get("home", {})
            away_stats = stats.get("away", {})
            stat_keys = [
                ("ball_possession", "Possession", "%"),
                ("accurate_passes", "Accurate passes", ""),
                ("pass_accuracy_pct", "Pass accuracy", "%"),
                ("duels", "Duels", ""),
                ("fouls", "Fouls", ""),
                ("offsides", "Offsides", ""),
                ("throw_ins", "Throw-ins", ""),
                ("clearances", "Clearances", ""),
                ("interceptions", "Interceptions", ""),
                ("recoveries", "Recoveries", ""),
                ("dangerous_attack", "Dangerous attacks", ""),
                ("attack", "Attacks", ""),
            ]
            rows = []
            for key, label, suffix in stat_keys:
                hv = home_stats.get(key)
                av = away_stats.get(key)
                if hv is None and av is None:
                    continue
                rows.append((label, hv, av, suffix))
            if rows:
                st.html('<div class="stats-grid"><div class="tiny">' + esc(home) + '</div><div class="tiny" style="text-align:center;">STAT</div><div class="tiny" style="text-align:right;">' + esc(away) + '</div></div>')
                for label, hv, av, suffix in rows:
                    htxt = f"{hv}{suffix}" if hv is not None else "—"
                    atxt = f"{av}{suffix}" if av is not None else "—"
                    st.html(f'<div class="stats-row"><div style="font-weight:700;color:#fff;">{esc(htxt)}</div><div style="text-align:center;color:#8190a5;font-size:12px;">{esc(label)}</div><div style="text-align:right;font-weight:700;color:#fff;">{esc(atxt)}</div></div>')
            else:
                st.info("No displayable statistics yet.")
        else:
            st.info("No live statistics are currently available.")

    with right:
        st.markdown("#### 📺 Broadcasts")
        render_broadcasts(broadcasts if isinstance(broadcasts, list) else [])
        st.markdown("#### 📱 Social")
        render_social_items(social if isinstance(social, list) else [], "Social")

    st.caption("🟢 Live monitoring is active. This page refreshes every 15 seconds while this tab remains open.")


if st.session_state.page == "Match Center":
    if hasattr(st, "fragment"):
        @st.fragment(run_every="15s")
        def _live_match_center():
            render_match_center(user_id)
        _live_match_center()
    else:
        render_match_center(user_id)


# =========================================================
# NEWS
# =========================================================

elif st.session_state.page == "News":
    st.html('<div class="page-header"><div class="page-header-title">News</div><div class="page-header-subtitle">Latest football news for your followed teams.</div></div>')
    if not teams:
        st.info("Your watchlist is empty.")
    else:
        for team in teams:
            name = team.get("name")
            st.html(f'<div class="section-title">📰 {esc(name)}</div>')
            try:
                result = get_team_news(user_id, name)
            except Exception as error:
                st.error(f"Could not load news for {name}: {error}")
                continue
            articles = result.get("articles", []) if isinstance(result, dict) and result.get("status") == "success" else []
            if not articles:
                st.info(f"No recent news found for {name}.")
                continue
            for article in articles:
                title = first_value(article, "title", default="Untitled article")
                description = first_value(article, "description", default="No description available.")
                source = first_value(article, "source", default="Unknown source")
                if isinstance(source, dict):
                    source = source.get("name") or source.get("source_name") or "Unknown source"
                published = first_value(article, "published_at", "publishedAt", default="Date unavailable")
                url = first_value(article, "url")
                article_link = ('<a href="' + esc(url) + '" target="_blank" style="color:#60a5fa;font-size:13px;font-weight:700;text-decoration:none;">Read article ↗</a>') if url else ''
                st.html(f'<div class="news-card"><div style="font-size:18px;font-weight:750;line-height:1.4;color:#fff;margin-bottom:10px;">{esc(title)}</div><div class="tiny">{esc(source)} • {esc(published)}</div><div style="font-size:13px;line-height:1.7;color:#9aa8bb;margin-top:12px;margin-bottom:12px;">{esc(description)}</div>{article_link}</div>')

        # Team social is a separate feed from news.
        st.html('<div class="section-title">📱 Team social</div>')
        for team in teams:
            name = team.get("name")
            with st.expander(name, expanded=False):
                try:
                    result = get_team_social(user_id, name, 10)
                    render_social_items(result.get("social", []) if isinstance(result, dict) else [], "Team social")
                except Exception as error:
                    st.error(f"Could not load social posts for {name}: {error}")


# =========================================================
# WATCHLIST
# =========================================================

elif st.session_state.page == "Watchlist":
    st.html('<div class="page-header"><div class="page-header-title">Watchlist</div><div class="page-header-subtitle">Manage the teams SportIQ follows.</div></div>')
    st.html('<div class="section-title">Your teams</div>')

    if teams:
        for team in teams:
            name = team.get("name")
            logo = get_team_logo(name)
            left, right = st.columns([5,1])
            with left:
                st.html(f'<div class="watchlist-card"><div style="display:flex;align-items:center;gap:15px;">{render_logo(logo,48)}<div><div class="watchlist-team-name">{esc(name)}</div><div class="watchlist-team-meta">{esc(team.get("country") or "Unknown country")}</div></div></div></div>')
            with right:
                st.write("")
                if st.button("Remove", key=f"remove_team_{team.get('id')}", use_container_width=True):
                    try:
                        result = execute_mcp_tool(user_id, "remove_team_from_watchlist", {"team_name": name})
                        if isinstance(result, dict) and result.get("status") == "success":
                            st.success(f"{name} removed.")
                            st.rerun()
                        else:
                            st.error(result.get("error", "Team could not be removed.") if isinstance(result, dict) else "Unexpected response.")
                    except Exception as error:
                        st.error(f"Could not remove team: {error}")
    else:
        st.info("Your watchlist is empty. Search below to add your first team.")

    st.html('<div class="section-title" style="margin-top:30px;">Add a team</div>')
    c1, c2 = st.columns([5,1])
    with c1:
        search_query = st.text_input("Search teams", value=st.session_state.watchlist_search_query, placeholder="Search for a football team...", label_visibility="collapsed")
    with c2:
        clicked = st.button("Search", type="primary", use_container_width=True)

    if clicked:
        q = search_query.strip()
        st.session_state.watchlist_search_query = q
        if not q:
            st.warning("Enter a team name to search.")
        else:
            try:
                result = execute_mcp_tool(user_id, "search_teams", {"team_name": q})
                st.session_state.watchlist_search_results = result.get("teams", []) if isinstance(result, dict) and result.get("status") == "success" else []
                if isinstance(result, dict) and result.get("status") != "success":
                    st.error(result.get("error", "Team search failed."))
            except Exception as error:
                st.session_state.watchlist_search_results = []
                st.error(f"Could not search teams: {error}")

    results = st.session_state.watchlist_search_results
    if results is not None:
        st.html('<div class="section-title" style="margin-top:25px;">Search results</div>')
        current_ids = {team.get("id") for team in teams}
        if not results:
            st.info("No teams found. Try a different search.")
        else:
            for index, result in enumerate(results):
                team_id = result.get("id")
                name = result.get("name")
                logo = result.get("logo")
                country = result.get("country") or "Unknown country"
                venue = result.get("venue")
                left, right = st.columns([5,1])
                with left:
                    venue_text = f" • {esc(venue)}" if venue else ""
                    st.html(
                        f'<div class="search-result-card"><div style="display:flex;align-items:center;gap:15px;">{render_logo(logo,48)}<div><div class="search-result-name">{esc(name)}</div><div class="search-result-meta">{esc(country)}{venue_text}</div></div></div></div>'
                    )
                with right:
                    st.write("")
                    if team_id in current_ids:
                        st.button("Following", key=f"following_{team_id}_{index}", disabled=True, use_container_width=True)
                    else:
                        if st.button("Add", key=f"add_{team_id}_{index}", type="primary", use_container_width=True):
                            try:
                                result_add = execute_mcp_tool(user_id, "add_team_to_watchlist", {"team_id": team_id})
                                if isinstance(result_add, dict) and result_add.get("status") in ("success", "already_exists"):
                                    st.session_state.watchlist_search_results = None
                                    st.success(f"{name} is now in your watchlist.")
                                    st.rerun()
                                else:
                                    st.error(result_add.get("error", "Team could not be added.") if isinstance(result_add, dict) else "Unexpected response.")
                            except Exception as error:
                                st.error(f"Could not add team: {error}")


# =========================================================
# SQUAD
# =========================================================

elif st.session_state.page == "Squad":
    st.html('<div class="page-header"><div class="page-header-title">Squad</div><div class="page-header-subtitle">Explore the players in your followed teams.</div></div>')
    if not teams:
        st.info("Your watchlist is empty.")
    else:
        names = [team.get("name") for team in teams if team.get("name")]
        squad_default = names.index(st.session_state.squad_team) if st.session_state.squad_team in names else 0
        selected = st.selectbox("Select team", names, index=squad_default, key="squad_team")
        if selected:
            try:
                result = get_team_squad(user_id, selected)
            except Exception as error:
                result = {"status":"error", "error":str(error)}
            if not isinstance(result, dict) or result.get("status") != "success":
                st.error(result.get("error", "Could not load squad.") if isinstance(result, dict) else "Unexpected response.")
            else:
                team_name = result.get("team") or selected
                logo = result.get("team_logo")
                leagues = result.get("leagues", [])
                players = result.get("players", [])
                st.html(f'<div class="squad-team-card"><div style="display:flex;align-items:center;gap:22px;">{render_logo(logo,82)}<div><div class="squad-team-name">{esc(team_name)}</div><div class="squad-team-meta">{esc(", ".join(map(str, leagues)) if leagues else "Competition unavailable")}<br>{len(players)} players</div></div></div></div>')
                groups = {"G":"Goalkeepers","D":"Defenders","M":"Midfielders","F":"Forwards"}
                grouped = {k:[] for k in groups}
                other = []
                for player in players:
                    position = str(player.get("position") or "").upper()
                    (grouped[position] if position in grouped else other).append(player)
                for position, title in groups.items():
                    plist = grouped[position]
                    if not plist:
                        continue
                    st.html(f'<div class="section-title">{title}</div>')
                    cols = st.columns(min(len(plist),4))
                    for i, player in enumerate(plist):
                        with cols[i % len(cols)]:
                            pname = player.get("name") or "Unknown player"
                            photo = player.get("photo")
                            availability = player.get("availability") or "Unknown"
                            av = str(availability).lower().strip()
                            status = '<div class="squad-status-available">🟢 Available</div>' if av == "available" else '<div class="squad-status-injured">🔴 Injured</div>' if av == "injured" else f'<div class="squad-status-neutral">⚪ {esc(availability)}</div>'
                            jersey = player.get("jersey_number")
                            nationality = player.get("nationality") or "Nationality unavailable"
                            injury = ""
                            if av == "injured":
                                details = []
                                if player.get("injury_type"): details.append(f'🩹 {esc(player.get("injury_type"))}')
                                if player.get("injury_expected_return"): details.append(f'↩️ Expected return: {esc(player.get("injury_expected_return"))}')
                                if details: injury = '<div class="squad-injury">' + '<br>'.join(details) + '</div>'
                            st.html(f'<div class="squad-player-card">{render_logo(photo,210,"👤")}<div class="squad-player-name">{esc(pname)}</div><div class="squad-player-meta">{esc(f"#{jersey}" if jersey is not None else "Jersey unavailable")} • {esc(nationality)}</div><div style="margin-top:9px;">{status}</div>{injury}</div>')
                if other:
                    st.html('<div class="section-title">Other</div>')
                    cols = st.columns(min(len(other),4))
                    for i, player in enumerate(other):
                        with cols[i % len(cols)]:
                            st.html(f'<div class="squad-player-card">{render_logo(player.get("photo"),210,"👤")}<div class="squad-player-name">{esc(player.get("name") or "Unknown player")}</div><div class="squad-player-meta">Position: {esc(player.get("position") or "Unknown")}</div></div>')


# =========================================================
# AI CHAT
# =========================================================

elif st.session_state.page == "AI Chat":
    st.html('<div class="page-header"><div class="page-header-title">AI Chat</div><div class="page-header-subtitle">Ask SportIQ about your football world.</div></div>')
    st.html('<div class="chat-intro"><div class="chat-intro-title">Talk football naturally.</div><div class="chat-intro-text">Ask about results, scorers, managers, fixtures, squads, standings, news, or your followed teams. SportIQ retrieves current data when your question needs it.</div></div>')
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.chat_input("Ask SportIQ anything...")
    if prompt:
        st.session_state.chat_messages.append({"role":"user","content":prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("SportIQ is thinking..."):
                try:
                    response = ask_agent(user_id, prompt)
                    answer = response if isinstance(response, str) else str(response)
                except Exception as error:
                    answer = f"Sorry, I couldn't process that request.\n\nError: {error}"
                st.markdown(answer)
        st.session_state.chat_messages.append({"role":"assistant","content":answer})


# =========================================================
# FOOTER
# =========================================================

st.html('<div class="sportiq-footer">SportIQ • AI-powered football intelligence</div>')
