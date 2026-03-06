import requests
from datetime import datetime, timedelta
import streamlit as st
import time
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Origin": "https://www.sofascore.com",
    "Referer": "https://www.sofascore.com/",
    "Cache-Control": "no-cache"
}

# ✅ TARGET LEAGUES - ONLY 8 LEAGUES YOU SELECTED
TARGET_LEAGUES = {
    'כדורגל ⚽': [
        'UEFA Champions League',           # ליגת האלופות
        'Ligat Winner',                    # ליגת העל בישראל
        'LaLiga',                          # ליגה הספרדית
        'Copa del Rey',                    # גביע הספרד
        'Supercopa de España',             # סופר גביע ספרד
        'Premier League',                  # ליגה האנגלית
        'FA Cup',                          # גביע באנגליה
        'EFL Cup',                         # קפה של ליגה באנגליה
        'Ligue 1',                         # ליגה הצרפתית
        'Coupe de France'                  # גביע צרפת
    ],
    'כדורסל 🏀': [
        'NBA',                             # NBA
        'Israeli Basketball League',       # ליגת כדורסל בישראל
        'Basketball League',               # גם ככה יש
        'CBA'                              # ליגת הכדורסל של סין
    ]
}

def get_israel_time(utc_timestamp):
    """המרה של UTC לשעון ישראלי עם DST"""
    try:
        if utc_timestamp == 0:
            return datetime.now()
        utc_time = datetime.utcfromtimestamp(utc_timestamp)
        # DST בישראל: מרץ-אוקטובר +3, אחרת +2
        is_dst = (utc_time.month in [3,4,5,6,7,8,9,10]) and utc_time.day > 20
        israel_offset = 3 if is_dst else 2
        return utc_time + timedelta(hours=israel_offset)
    except:
        return datetime.now()

def game_has_started(start_timestamp):
    """בדיקה האם המשחק כבר התחיל - בשעה ישראלית!"""
    try:
        if start_timestamp == 0:
            return False
        
        # ✅ FIX: השתמש בשעה ישראלית לשני הצדדים!
        game_time = get_israel_time(start_timestamp)
        
        # זמן ישראלי כעת
        utc_now = datetime.utcnow()
        is_dst = (utc_now.month in [3,4,5,6,7,8,9,10]) and utc_now.day > 20
        israel_offset = 3 if is_dst else 2
        now_israel = utc_now + timedelta(hours=israel_offset)
        
        # בדיקה: אם משחק התחיל
        is_started = game_time < now_israel
        
        return is_started
    except Exception as e:
        st.error(f"❌ שגיאה בבדיקת זמן משחק: {str(e)}")
        return False

@st.cache_data(ttl=1800)
def fetch_games_for_dates(sport="כדורגל ⚽", days=7):
    """טעינת משחקים עם סינון לפי ליגות נבחרות וביטול משחקים שכבר התחילו"""
    api_sport = "football" if sport == "כדורגל ⚽" else "basketball"
    today = datetime.now()
    games_by_date = {}
    target_league_names = TARGET_LEAGUES.get(sport, [])

    for i in range(days):
        target_date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://api.sofascore.com/api/v1/sport/{api_sport}/scheduled-events/{target_date}"
        games_by_date[target_date] = []
        
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                for event in res.json().get("events", []):
                    league = event.get("tournament", {}).get("name", "")
                    start_timestamp = event.get("startTimestamp", 0)
                    
                    # ✅ סינון 1: רק ליגות שבחרנו
                    league_match = False
                    for target_league in target_league_names:
                        if target_league.lower() in league.lower():
                            league_match = True
                            break
                    
                    if not league_match:
                        continue
                    
                    # ✅ סינון 2: משחקים שכבר התחילו
                    if game_has_started(start_timestamp):
                        continue
                    
                    israel_time = get_israel_time(start_timestamp)
                    games_by_date[target_date].append({
                        "id": event.get("id"),
                        "time": israel_time.strftime("%H:%M"),
                        "datetime": israel_time.strftime("%Y-%m-%d %H:%M"),
                        "date": target_date,
                        "league": league,
                        "home": event.get("homeTeam", {}).get("name", "Unknown"),
                        "home_id": event.get("homeTeam", {}).get("id"),
                        "away": event.get("awayTeam", {}).get("name", "Unknown"),
                        "away_id": event.get("awayTeam", {}).get("id"),
                        "start_timestamp": start_timestamp
                    })
                
                games_by_date[target_date].sort(key=lambda x: x['time'])
        except Exception as e: 
            st.warning(f"⚠️ שגיאה בטעינת משחקים ל-{target_date}: {str(e)}")
    
    return {k: v for k, v in games_by_date.items() if v}

def get_team_stats(team_id, include_home_away=False):
    """קבלת סטטיסטיקות נרחבות של הקבוצה"""
    stats = {
        "form": [], 
        "goals_scored": 0, 
        "goals_conceded": 0, 
        "wins": 0, 
        "draws": 0, 
        "losses": 0, 
        "total_games": 0, 
        "win_rate": 0, 
        "avg_goals_for": 0, 
        "avg_goals_against": 0, 
        "home_form": [], 
        "away_form": [],
        "last_5_form": []
    }
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/0"
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            events = res.json().get("events", [])[:20]  # 20 משחקים
            for idx, e in enumerate(events):
                h_score = e.get("homeScore", {}).get("current")
                a_score = e.get("awayScore", {}).get("current")
                if h_score is None or a_score is None: 
                    continue
                
                is_h = e.get("homeTeam", {}).get("id") == team_id
                
                stats["goals_scored"] += h_score if is_h else a_score
                stats["goals_conceded"] += a_score if is_h else h_score
                stats["total_games"] += 1
                
                if h_score == a_score:
                    stats["form"].append(("ת", "#4a6070")); stats["draws"] += 1
                elif (is_h and h_score > a_score) or (not is_h and a_score > h_score):
                    stats["form"].append(("נ", "#00ff88")); stats["wins"] += 1
                else:
                    stats["form"].append(("ה", "#ff3b5c")); stats["losses"] += 1
                
                # טופס 5 משחקים אחרונים
                if idx < 5:
                    stats["last_5_form"].append(stats["form"][-1])
            
            if stats["total_games"] > 0:
                stats["win_rate"] = (stats["wins"] / stats["total_games"]) * 100
                stats["avg_goals_for"] = stats["goals_scored"] / stats["total_games"]
                stats["avg_goals_against"] = stats["goals_conceded"] / stats["total_games"]
    except Exception as e: 
        st.warning(f"⚠️ שגיאה בקבלת סטטיסטיקות: {str(e)}")
    return stats

@st.cache_data(ttl=1800)
def get_h2h_data(game_id, home_id, away_id):
    """קבלת נתוני H2H מורחבים"""
    h2h_data = {
        "matches": [], 
        "head_to_head": {
            "home_wins": 0, 
            "away_wins": 0, 
            "draws": 0, 
            "total": 0, 
            "home_goals": 0, 
            "away_goals": 0,
            "avg_goals": 0
        }
    }
    try:
        res = requests.get(f"https://api.sofascore.com/api/v1/event/{game_id}/h2h/events", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            for e in res.json().get("events", []):
                h_score = e.get("homeScore", {}).get("current")
                a_score = e.get("awayScore", {}).get("current")
                
                if h_score is None or a_score is None: 
                    continue
                
                h2h_data["matches"].append({
                    "date": get_israel_time(e.get("startTimestamp", 0)).strftime("%d/%m/%Y"),
                    "home": e.get("homeTeam", {}).get("name", ""), 
                    "away": e.get("awayTeam", {}).get("name", ""),
                    "home_score": h_score, 
                    "away_score": a_score,
                    "result": "ניצחון בית" if h_score > a_score else ("ניצחון חוץ" if a_score > h_score else "תיקו")
                })
                h2h_data["head_to_head"]["total"] += 1
                h2h_data["head_to_head"]["home_goals"] += h_score
                h2h_data["head_to_head"]["away_goals"] += a_score
                
                if h_score > a_score: 
                    h2h_data["head_to_head"]["home_wins"] += 1
                elif a_score > h_score: 
                    h2h_data["head_to_head"]["away_wins"] += 1
                else: 
                    h2h_data["head_to_head"]["draws"] += 1
                
                if len(h2h_data["matches"]) >= 15: 
                    break
        
        # חישוב ממוצע שערים
        if h2h_data["head_to_head"]["total"] > 0:
            total_goals = h2h_data["head_to_head"]["home_goals"] + h2h_data["head_to_head"]["away_goals"]
            h2h_data["head_to_head"]["avg_goals"] = total_goals / h2h_data["head_to_head"]["total"]
    except Exception as e: 
        st.warning(f"⚠️ שגיאה בקבלת H2H: {str(e)}")
    
    return h2h_data

def get_odds_from_the_odds_api(home_team, away_team):
    """קבלת יחסים מ-The Odds API"""
    odds_data = {"1": "לא זמין", "X": "לא זמין", "2": "לא זמין", "over_2_5": "-", "under_2_5": "-"}
    api_key = os.environ.get("ODDS_API_KEY") or st.secrets.get("ODDS_API_KEY", "")
    if not api_key: 
        return odds_data
        
    try:
        url = "https://api.the-odds-api.com/v4/sports/upcoming/odds/"
        params = {"apiKey": api_key, "regions": "eu", "markets": "h2h,totals", "oddsFormat": "decimal"}
        res = requests.get(url, params=params, timeout=5)
        
        if res.status_code == 200:
            for game in res.json():
                api_home = game['home_team'].lower()
                api_away = game['away_team'].lower()
                
                if (home_team[:5].lower() in api_home) or (away_team[:5].lower() in api_away):
                    bookmaker = game['bookmakers'][0] 
                    h2h_market = next((m for m in bookmaker['markets'] if m['key'] == 'h2h'), None)
                    if h2h_market:
                        for outcome in h2h_market['outcomes']:
                            if outcome['name'] == game['home_team']: 
                                odds_data["1"] = outcome['price']
                            elif outcome['name'] == game['away_team']: 
                                odds_data["2"] = outcome['price']
                            elif outcome['name'] == 'Draw': 
                                odds_data["X"] = outcome['price']
                    break
    except: 
        pass
    
    return odds_data

def get_missing_players(game_id):
    """קבלת רשימת שחקנים נפצעים"""
    missing = {"home": [], "away": []}
    try:
        res = requests.get(f"https://api.sofascore.com/api/v1/event/{game_id}/lineups", headers=HEADERS, timeout=8).json()
        home_missing = [f"{p.get('player', {}).get('name', '')}" for p in res.get("home", {}).get("missingPlayers", [])]
        away_missing = [f"{p.get('player', {}).get('name', '')}" for p in res.get("away", {}).get("missingPlayers", [])]
        missing["home"] = home_missing if home_missing else ["סגל מלא ✅"]
        missing["away"] = away_missing if away_missing else ["סגל מלא ✅"]
    except:
        missing["home"] = ["נתונים לא זמינים"]
        missing["away"] = ["נתונים לא זמינים"]
    
    return missing

@st.cache_data(ttl=1800)
def get_game_deep_data(game_id, home_id, away_id, home_team="", away_team=""):
    """קבלת כל נתוני המשחק בעומק"""
    data = {
        "odds": {"1": "לא זמין", "X": "לא זמין", "2": "לא זמין", "over_2_5": "-", "under_2_5": "-"},
        "h2h_matches": [], 
        "h2h_summary": {}, 
        "home_stats": {}, 
        "away_stats": {}, 
        "missing_home": [], 
        "missing_away": []
    }
    
    try:
        res = requests.get(f"https://api.sofascore.com/api/v1/event/{game_id}/odds/1/all", headers=HEADERS, timeout=5).json()
        if res.get("markets"):
            for market in res.get("markets", []):
                if market.get("marketName") in ["1x2", "Moneyline"]:
                    for choice in market.get("choices", []): 
                        data["odds"][choice.get("name")] = choice.get("fractionalValue", "לא זמין")
    except: 
        pass
    
    if data["odds"]["1"] == "לא זמין":
        fallback = get_odds_from_the_odds_api(home_team, away_team)
        if fallback["1"] != "לא זמין": 
            data["odds"] = fallback

    h2h = get_h2h_data(game_id, home_id, away_id)
    data["h2h_matches"] = h2h["matches"]
    data["h2h_summary"] = h2h["head_to_head"]
    
    data["home_stats"] = get_team_stats(home_id)
    data["away_stats"] = get_team_stats(away_id)
    
    missing = get_missing_players(game_id)
    data["missing_home"] = missing["home"]
    data["missing_away"] = missing["away"]
    
    return data
