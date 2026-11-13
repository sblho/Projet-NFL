import feedparser
import requests
from django.core.cache import cache
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page


class HomePage(Page):
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    def get_context(self, request):
        context = super().get_context(request)
        headers = {"User-Agent": "Mozilla/5.0"}

        # 1. APERÇU DES SCORES (home_games)
        home_games = cache.get("nfl_home_games")
        if home_games is None:
            home_games = []
            try:
                resp = requests.get(
                    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
                    headers=headers,
                    timeout=10,
                ).json()
                for event in resp.get("events", [])[:4]:
                    comp = event.get("competitions", [{}])[0]
                    competitors = comp.get("competitors", [])
                    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
                    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
                    home_games.append({
                        "status": event.get("status", {}).get("type", {}).get("shortDetail", ""),
                        "home_abbr": home.get("team", {}).get("abbreviation", ""),
                        "home_logo": home.get("team", {}).get("logo", ""),
                        "home_score": home.get("score", "-"),
                        "away_abbr": away.get("team", {}).get("abbreviation", ""),
                        "away_logo": away.get("team", {}).get("logo", ""),
                        "away_score": away.get("score", "-"),
                    })
                if home_games:
                    cache.set("nfl_home_games", home_games, 600)
            except Exception as e:
                print("ERREUR SCORES:", e)

        # 2. TOP CLASSEMENT (home_standings : dictionnaire {"AFC": [...], "NFC": [...]})
        home_standings = cache.get("nfl_home_standings_dict")
        if home_standings is None:
            home_standings = {}
            try:
                resp = requests.get(
                    "https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
                    headers=headers,
                    timeout=10,
                ).json()
                for conf in resp.get("children", []):
                    conf_name = conf.get("abbreviation", conf.get("name", ""))
                    teams = []
                    entries = conf.get("standings", {}).get("entries", [])
                    if not entries:
                        for div in conf.get("children", []):
                            entries.extend(div.get("standings", {}).get("entries", []))

                    for entry in entries:
                        team = entry.get("team", {})
                        stats_val = {s.get("name"): s.get("value", 0) for s in entry.get("stats", [])}
                        stats_disp = {s.get("name"): s.get("displayValue", "0") for s in entry.get("stats", [])}
                        teams.append({
                            "name": team.get("shortDisplayName", team.get("displayName", "")),
                            "logo": team.get("logos", [{}])[0].get("href", ""),
                            "wins": int(stats_val.get("wins", 0)),
                            "losses": int(stats_val.get("losses", 0)),
                            "pct": stats_disp.get("winPercent", ".000"),
                        })
                    if teams:
                        teams.sort(key=lambda x: (x["wins"], float(x["pct"] or 0)), reverse=True)
                        home_standings[conf_name] = teams[:4]
                if home_standings:
                    cache.set("nfl_home_standings_dict", home_standings, 900)
            except Exception as e:
                print("ERREUR CLASSEMENT:", e)

        # 3. DERNIÈRES ACTUALITÉS (home_news)
        home_news = cache.get("nfl_home_news_list")
        if home_news is None:
            home_news = []
            try:
                news_resp = requests.get(
                    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news",
                    headers=headers,
                    timeout=10,
                ).json()
                for article in news_resp.get("articles", [])[:4]:
                    home_news.append({
                        "title": article.get("headline", ""),
                        "link": article.get("links", {}).get("web", {}).get("href", "#"),
                        "published": article.get("published", "")[:10],
                    })
                if home_news:
                    cache.set("nfl_home_news_list", home_news, 900)
            except Exception as e:
                print("ERREUR NEWS:", e)

        context["home_games"] = home_games
        context["home_standings"] = home_standings
        context["home_news"] = home_news
        return context