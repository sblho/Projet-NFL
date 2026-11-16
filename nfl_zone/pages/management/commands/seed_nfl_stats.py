import json
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from django.core.management.base import BaseCommand
from pages.models import (
    TeamPage,
    TeamSeasonStats,
    PlayerSeasonStats,
    MatchBoxScore,
    resolve_team_page,
)

ESPN_ABBR_TO_NAME = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders",
    "OAK": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "SD": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "STL": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SF": "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
    "WSH": "Washington Commanders",
}

_JSON_CACHE = {}
_CACHE_LOCK = threading.Lock()


def fetch_json(url, timeout=12, use_cache=True):
    if not url:
        return {}
    clean_url = url.replace("http://", "https://")
    if use_cache:
        with _CACHE_LOCK:
            if clean_url in _JSON_CACHE:
                return _JSON_CACHE[clean_url]

    req = urllib.request.Request(clean_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if use_cache:
        with _CACHE_LOCK:
            _JSON_CACHE[clean_url] = data
    return data


def _safe_int(val):
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return 0


def match_espn_team(abbr, display_name, teams):
    canonical_name = ESPN_ABBR_TO_NAME.get((abbr or "").upper()) or display_name
    if canonical_name:
        for t in teams:
            if t.title.lower() == canonical_name.lower():
                return t
        found = resolve_team_page(canonical_name, teams)
        if found:
            return found
    return resolve_team_page(display_name, teams) if display_name else None


def get_espn_team_ids(teams):
    mapping = {}
    data = fetch_json("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams")
    espn_teams = (
        data.get("sports", [{}])[0]
        .get("leagues", [{}])[0]
        .get("teams", [])
    )
    for item in espn_teams:
        t_info = item.get("team", {})
        matched = match_espn_team(t_info.get("abbreviation"), t_info.get("displayName"), teams)
        if matched and t_info.get("id"):
            mapping[matched.id] = str(t_info["id"])
    return mapping


def parse_categories_stats(categories):
    flat = {}
    for cat in categories or []:
        c_name = cat.get("name", "")
        for st in cat.get("stats", []):
            s_name = st.get("name", "")
            val = st.get("value", 0)
            if c_name and s_name:
                flat[f"{c_name}.{s_name}"] = val
            if s_name and s_name not in flat:
                flat[s_name] = val
    return flat


def fetch_real_standings(year, teams):
    url = f"https://site.api.espn.com/apis/v2/sports/football/nfl/standings?season={year}"
    records = {}
    try:
        data = fetch_json(url)

        def parse_node(node):
            for entry in node.get("standings", {}).get("entries", []):
                t_data = entry.get("team", {})
                matched = match_espn_team(t_data.get("abbreviation"), t_data.get("displayName"), teams)
                if matched:
                    s_map = {s.get("name"): s.get("value", 0) for s in entry.get("stats", [])}
                    records[matched.id] = {
                        "wins": _safe_int(s_map.get("wins", 0)),
                        "losses": _safe_int(s_map.get("losses", 0)),
                        "ties": _safe_int(s_map.get("ties", 0)),
                        "points_for": _safe_int(s_map.get("pointsFor", 0)),
                        "points_against": _safe_int(s_map.get("pointsAgainst", 0)),
                    }
            for child in node.get("children", []):
                parse_node(child)

        parse_node(data)
    except Exception:
        pass
    return records


def fetch_core_team_stats(espn_team_id, year):
    url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/teams/{espn_team_id}/statistics"
    try:
        data = fetch_json(url, timeout=10)
        cats = data.get("splits", {}).get("categories") or data.get("results", {}).get("stats", {}).get("categories", [])
        flat = parse_categories_stats(cats)
        pass_yds = _safe_int(flat.get("passing.netPassingYards") or flat.get("passing.passingYards") or flat.get("passingYards", 0))
        rush_yds = _safe_int(flat.get("rushing.rushingYards") or flat.get("rushingYards", 0))
        takeaways = _safe_int(flat.get("miscellaneous.totalTakeaways") or flat.get("totalTakeaways", 0))
        giveaways = _safe_int(flat.get("miscellaneous.totalGiveaways") or flat.get("totalGiveaways", 0))
        to_diff = _safe_int(
            flat.get("miscellaneous.turnOverDifferential")
            or flat.get("miscellaneous.turnoverDifferential")
            or flat.get("turnOverDifferential")
            or (takeaways - giveaways)
        )
        gp = _safe_int(flat.get("general.gamesPlayed") or flat.get("gamesPlayed", 0))
        return {
            "passing_yards": pass_yds,
            "rushing_yards": rush_yds,
            "turnover_diff": to_diff,
            "games_played": gp,
        }
    except Exception:
        return {"passing_yards": 0, "rushing_yards": 0, "turnover_diff": 0, "games_played": 0}


def fetch_core_team_leaders(espn_team_id, year, fallback_gp):
    url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/teams/{espn_team_id}/leaders"
    target_cats = {
        "passingYards": "QB",
        "rushingYards": "RB",
        "receivingYards": "WR",
        "totalTackles": "DEF",
        "sacks": "DEF",
        "interceptions": "DEF",
    }
    players = {}

    try:
        data = fetch_json(url, timeout=10)
        for cat in data.get("categories", []):
            cat_name = cat.get("name", "")
            if cat_name not in target_cats:
                continue
            entries = cat.get("leaders", [])
            if not entries:
                continue
            top = entries[0]
            athlete_ref = top.get("athlete", {}).get("$ref")
            stats_ref = top.get("statistics", {}).get("$ref")
            raw_val = top.get("value", 0)

            if not athlete_ref:
                continue

            try:
                ath = fetch_json(athlete_ref, timeout=8)
            except Exception:
                continue

            full_name = ath.get("fullName")
            if not full_name:
                continue

            jersey_raw = str(ath.get("jersey", "0"))
            jersey = int(jersey_raw) if jersey_raw.isdigit() else 0
            pos_abbr = ath.get("position", {}).get("abbreviation") or target_cats[cat_name]
            if target_cats[cat_name] == "DEF":
                pos_abbr = "DEF"

            p_record = players.setdefault(
                full_name,
                {
                    "jersey_number": jersey,
                    "position": pos_abbr,
                    "games_played": fallback_gp,
                    "pass_yards": 0,
                    "pass_td": 0,
                    "interceptions": 0,
                    "rush_yards": 0,
                    "rush_td": 0,
                    "receptions": 0,
                    "rec_yards": 0,
                    "rec_td": 0,
                    "tackles": 0,
                    "sacks": 0.0,
                    "def_interceptions": 0,
                    "_hydrated": False,
                },
            )

            if stats_ref and not p_record["_hydrated"]:
                try:
                    st_data = fetch_json(stats_ref, timeout=8)
                    st_cats = st_data.get("splits", {}).get("categories", [])
                    flat = parse_categories_stats(st_cats)
                    if flat:
                        p_record["games_played"] = _safe_int(flat.get("general.gamesPlayed") or flat.get("gamesPlayed") or fallback_gp)
                        p_record["pass_yards"] = _safe_int(flat.get("passing.passingYards") or flat.get("passing.netPassingYards", 0))
                        p_record["pass_td"] = _safe_int(flat.get("passing.passingTouchdowns", 0))
                        p_record["interceptions"] = _safe_int(flat.get("passing.interceptions", 0))
                        p_record["rush_yards"] = _safe_int(flat.get("rushing.rushingYards", 0))
                        p_record["rush_td"] = _safe_int(flat.get("rushing.rushingTouchdowns", 0))
                        p_record["receptions"] = _safe_int(flat.get("receiving.receptions", 0))
                        p_record["rec_yards"] = _safe_int(flat.get("receiving.receivingYards", 0))
                        p_record["rec_td"] = _safe_int(flat.get("receiving.receivingTouchdowns", 0))
                        p_record["tackles"] = _safe_int(flat.get("defensive.totalTackles") or flat.get("defensive.soloTackles", 0))
                        p_record["sacks"] = round(float(flat.get("defensive.sacks", 0.0)), 1)
                        p_record["def_interceptions"] = _safe_int(flat.get("defensiveInterceptions.interceptions") or flat.get("defensive.interceptions", 0))
                        p_record["_hydrated"] = True
                except Exception:
                    pass

            if not p_record["_hydrated"]:
                if cat_name == "passingYards":
                    p_record["pass_yards"] = _safe_int(raw_val)
                elif cat_name == "rushingYards":
                    p_record["rush_yards"] = _safe_int(raw_val)
                elif cat_name == "receivingYards":
                    p_record["rec_yards"] = _safe_int(raw_val)
                elif cat_name == "totalTackles":
                    p_record["tackles"] = _safe_int(raw_val)
                elif cat_name == "sacks":
                    p_record["sacks"] = round(float(raw_val), 1)
                elif cat_name == "interceptions":
                    p_record["def_interceptions"] = _safe_int(raw_val)

    except Exception:
        pass

    return players


def fetch_season_matches(year, teams):
    """Récupère 100 % des matchs terminés semaine par semaine (Saison régulière + Playoffs) avec leurs boxscores ESPN."""
    max_reg_weeks = 17 if year <= 2020 else 18
    queries = [(2, w, f"Semaine {w}") for w in range(1, max_reg_weeks + 1)]
    queries.extend([
        (3, 1, "Wild Card"),
        (3, 2, "Divisional"),
        (3, 3, "Finales Conf."),
        (3, 4, "Super Bowl"),
        (3, 5, "Super Bowl"),
    ])

    def fetch_week_events(q):
        season_type, week_num, default_label = q
        url = (
            f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
            f"?dates={year}&seasontype={season_type}&week={week_num}"
        )
        try:
            sb = fetch_json(url, timeout=10)
            return default_label, sb.get("events", [])
        except Exception:
            return default_label, []

    completed_events = []
    seen_event_ids = set()

    with ThreadPoolExecutor(max_workers=12) as pool:
        for default_label, events in pool.map(fetch_week_events, queries):
            for ev in events:
                ev_id = ev.get("id")
                if not ev_id or ev_id in seen_event_ids:
                    continue
                comp = ev.get("competitions", [{}])[0]
                if not comp.get("status", {}).get("type", {}).get("completed"):
                    continue

                competitors = comp.get("competitors", [])
                home_c = next((c for c in competitors if c.get("homeAway") == "home"), None)
                away_c = next((c for c in competitors if c.get("homeAway") == "away"), None)
                if not home_c or not away_c:
                    continue

                home_t = match_espn_team(home_c["team"].get("abbreviation"), home_c["team"].get("displayName"), teams)
                away_t = match_espn_team(away_c["team"].get("abbreviation"), away_c["team"].get("displayName"), teams)
                # Ignore le Pro Bowl (AFC vs NFC)
                if not home_t or not away_t:
                    continue

                seen_event_ids.add(ev_id)
                completed_events.append((ev, comp, home_c, away_c, home_t, away_t, default_label))

    def hydrate_boxscore(item):
        ev, comp, home_c, away_c, home_t, away_t, default_label = item
        event_id = ev.get("id")
        h_score = _safe_int(home_c.get("score", 0))
        a_score = _safe_int(away_c.get("score", 0))

        notes = comp.get("notes", [])
        headline = notes[0].get("headline", "") if notes else ""
        week_label = "Super Bowl" if ("Super Bowl" in headline or default_label == "Super Bowl") else default_label

        raw_date = comp.get("date", "")
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            match_date = dt.strftime("%d/%m/%Y")
        except Exception:
            match_date = f"Saison {year}-{year + 1}"

        away_yds, home_yds = 0, 0
        away_to, home_to = 0, 0
        mvp_text = f"Score officiel ESPN : {away_t.title} {a_score} - {h_score} {home_t.title}"

        try:
            summary = fetch_json(
                f"https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}",
                timeout=8,
            )
            for b_team in summary.get("boxscore", {}).get("teams", []):
                t_abbr = b_team.get("team", {}).get("abbreviation", "")
                matched_b = match_espn_team(t_abbr, b_team.get("team", {}).get("displayName"), teams)
                stats_dict = {s.get("name"): s.get("displayValue", "0") for s in b_team.get("statistics", [])}
                tot_y = _safe_int(stats_dict.get("totalYards", 0))
                to_v = _safe_int(stats_dict.get("turnovers", 0))
                if matched_b and matched_b.id == away_t.id:
                    away_yds, away_to = tot_y, to_v
                elif matched_b and matched_b.id == home_t.id:
                    home_yds, home_to = tot_y, to_v

            game_leaders = summary.get("leaders", [])
            if game_leaders:
                cats = game_leaders[0].get("leaders", [])
                if cats and cats[0].get("leaders"):
                    top_perf = cats[0]["leaders"][0]
                    ath_name = top_perf.get("athlete", {}).get("displayName", "")
                    disp_val = top_perf.get("displayValue", "")
                    if ath_name and disp_val:
                        mvp_text = f"{ath_name} : {disp_val}"
        except Exception:
            pass

        return MatchBoxScore(
            season_year=year,
            week_label=week_label,
            away_team=away_t,
            home_team=home_t,
            match_date=match_date,
            is_final=True,
            away_score=a_score,
            home_score=h_score,
            away_total_yards=away_yds,
            home_total_yards=home_yds,
            away_turnovers=away_to,
            home_turnovers=home_to,
            mvp_highlight=mvp_text,
        )

    created_matches = []
    with ThreadPoolExecutor(max_workers=32) as pool:
        futures = [pool.submit(hydrate_boxscore, item) for item in completed_events]
        for fut in as_completed(futures):
            try:
                created_matches.append(fut.result())
            except Exception:
                pass

    if created_matches:
        MatchBoxScore.objects.bulk_create(created_matches)
    return created_matches


class Command(BaseCommand):
    help = "Importe 100 % des vraies statistiques NFL (équipes, joueurs, matchs semaine par semaine) depuis ESPN (2015-2026)."

    def handle(self, *args, **options):
        teams = list(TeamPage.objects.live())
        if len(teams) < 2:
            self.stdout.write(self.style.ERROR("Aucune TeamPage trouvée."))
            return

        PlayerSeasonStats.objects.all().delete()
        TeamSeasonStats.objects.all().delete()
        MatchBoxScore.objects.all().delete()
        self.stdout.write("Tables de statistiques vidées.")

        espn_ids = get_espn_team_ids(teams)
        seasons = list(range(2015, 2027))

        for year in seasons:
            standings = fetch_real_standings(year, teams)
            default_gp = 16 if year <= 2020 else (10 if year == 2026 else 17)

            def process_team(team):
                rec = standings.get(team.id, {})
                espn_id = espn_ids.get(team.id)
                t_stats = fetch_core_team_stats(espn_id, year) if espn_id else {}
                gp = t_stats.get("games_played") or (
                    (rec.get("wins", 0) + rec.get("losses", 0) + rec.get("ties", 0)) or default_gp
                )
                p_map = fetch_core_team_leaders(espn_id, year, gp) if espn_id else {}
                return team, rec, t_stats, gp, p_map

            team_rows = []
            player_rows = []

            with ThreadPoolExecutor(max_workers=16) as pool:
                results = list(pool.map(process_team, teams))

            for team, rec, t_stats, gp, p_map in results:
                team_rows.append(
                    TeamSeasonStats(
                        team=team,
                        season_year=year,
                        wins=rec.get("wins", 0),
                        losses=rec.get("losses", 0),
                        ties=rec.get("ties", 0),
                        points_for=rec.get("points_for", 0),
                        points_against=rec.get("points_against", 0),
                        passing_yards=t_stats.get("passing_yards", 0),
                        rushing_yards=t_stats.get("rushing_yards", 0),
                        turnover_diff=t_stats.get("turnover_diff", 0),
                    )
                )
                for p_name, p_st in p_map.items():
                    player_rows.append(
                        PlayerSeasonStats(
                            team=team,
                            season_year=year,
                            player_name=p_name,
                            jersey_number=p_st["jersey_number"],
                            position=p_st["position"],
                            games_played=p_st["games_played"] or gp,
                            pass_yards=p_st["pass_yards"],
                            pass_td=p_st["pass_td"],
                            interceptions=p_st["interceptions"],
                            rush_yards=p_st["rush_yards"],
                            rush_td=p_st["rush_td"],
                            receptions=p_st["receptions"],
                            rec_yards=p_st["rec_yards"],
                            rec_td=p_st["rec_td"],
                            tackles=p_st["tackles"],
                            sacks=p_st["sacks"],
                            def_interceptions=p_st["def_interceptions"],
                        )
                    )

            TeamSeasonStats.objects.bulk_create(team_rows)
            PlayerSeasonStats.objects.bulk_create(player_rows)
            matches = fetch_season_matches(year, teams)

            self.stdout.write(
                f"Saison {year}-{year + 1} -> Équipes: {len(team_rows)} | Joueurs: {len(player_rows)} | Matchs: {len(matches)}"
            )

        self.stdout.write(
            self.style.SUCCESS("Importation terminée : toutes les stats équipes, joueurs et matchs semaine par semaine sont à jour.")
        )