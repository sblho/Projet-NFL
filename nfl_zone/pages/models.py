from datetime import datetime
import feedparser
import requests
from django.core.cache import cache
from django.db import models
from modelcluster.fields import ParentalKey
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.embeds.blocks import EmbedBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable, Page
from wagtail.snippets.models import register_snippet


# ==========================================
# 1. CONSTANTES & UTILITAIRES NFL
# ==========================================

GROUP_LABELS = {
    "offense": "Attaque",
    "defense": "Défense",
    "specialTeam": "Équipes spéciales",
    "specialTeams": "Équipes spéciales",
    "injuredReserveOrOut": "Blessés (IR / Out)",
    "practiceSquad": "Practice Squad",
    "physicallyUnableToPerform": "Liste PUP",
    "suspended": "Suspendus",
}

ESPN_TEAM_IDS = {
    "arizona-cardinals": "22",
    "atlanta-falcons": "1",
    "baltimore-ravens": "33",
    "buffalo-bills": "2",
    "carolina-panthers": "29",
    "chicago-bears": "3",
    "cincinnati-bengals": "4",
    "cleveland-browns": "5",
    "dallas-cowboys": "6",
    "denver-broncos": "7",
    "detroit-lions": "8",
    "green-bay-packers": "9",
    "houston-texans": "34",
    "indianapolis-colts": "11",
    "jacksonville-jaguars": "30",
    "kansas-city-chiefs": "12",
    "las-vegas-raiders": "13",
    "los-angeles-chargers": "24",
    "los-angeles-rams": "14",
    "miami-dolphins": "15",
    "minnesota-vikings": "16",
    "new-england-patriots": "17",
    "new-orleans-saints": "18",
    "new-york-giants": "19",
    "new-york-jets": "20",
    "philadelphia-eagles": "21",
    "pittsburgh-steelers": "23",
    "san-francisco-49ers": "25",
    "seattle-seahawks": "26",
    "tampa-bay-buccaneers": "27",
    "tennessee-titans": "10",
    "washington-commanders": "28",
}

# Inclut les anciens codes (OAK, SD, STL, WSH) pour les classements 2015-2019
NFL_DIVISIONS = {
    "AFC": {
        "AFC Est": ["BUF", "MIA", "NE", "NYJ"],
        "AFC Nord": ["BAL", "CIN", "CLE", "PIT"],
        "AFC Sud": ["HOU", "IND", "JAX", "TEN"],
        "AFC Ouest": ["DEN", "KC", "LV", "OAK", "LAC", "SD"],
    },
    "NFC": {
        "NFC Est": ["DAL", "NYG", "PHI", "WSH", "WAS"],
        "NFC Nord": ["CHI", "DET", "GB", "MIN"],
        "NFC Sud": ["ATL", "CAR", "NO", "TB"],
        "NFC Ouest": ["ARI", "LAR", "LA", "STL", "SF", "SEA"],
    },
}

HISTORICAL_TEAM_ALIASES = {
    "stl": "rams",
    "st. louis": "rams",
    "st louis": "rams",
    "lar": "rams",
    "la": "rams",
    "sd": "chargers",
    "san diego": "chargers",
    "lac": "chargers",
    "oak": "raiders",
    "oakland": "raiders",
    "lv": "raiders",
    "wsh": "commanders",
    "redskins": "commanders",
    "football team": "commanders",
    "was": "commanders",
}


def resolve_team_page(identifier, teams_list):
    """Retrouve la TeamPage actuelle même si l'archive utilise un ancien nom ou code (STL, SD, OAK, WSH)."""
    if not identifier:
        return None
    key = str(identifier).strip().lower()
    mapped_keyword = HISTORICAL_TEAM_ALIASES.get(key, key)
    for team in teams_list:
        if mapped_keyword in team.title.lower() or mapped_keyword in team.slug.lower():
            return team
    return None


def get_season_selection(request, seasons_queryset, default_year=2026):
    """Factorise la récupération de la liste des saisons et de l'année active (?season=)."""
    seasons = list(
        seasons_queryset.values_list("season_year", flat=True)
        .distinct()
        .order_by("-season_year")
    )
    if not seasons:
        seasons = list(range(2026, 2014, -1))

    fallback = default_year if default_year in seasons else seasons[0]
    try:
        selected_season = int(request.GET.get("season", fallback))
    except (ValueError, TypeError):
        selected_season = fallback

    return seasons, selected_season


def get_team_roster(team_id):
    """Récupère et met en cache le roster ESPN d'une franchise à partir de son ID ESPN."""
    if not team_id:
        return []
    cache_key = f"nfl_roster_v2_{team_id}"
    cached_roster = cache.get(cache_key)
    if cached_roster is not None:
        return cached_roster

    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    roster_groups = []
    for group in data.get("athletes", []):
        raw_group = group.get("position", "")
        group_name = GROUP_LABELS.get(raw_group, raw_group.capitalize())
        players = []

        for p in group.get("items", []):
            exp_years = p.get("experience", {}).get("years", 0)
            players.append({
                "jersey": p.get("jersey", "-"),
                "name": p.get("fullName", ""),
                "position": p.get("position", {}).get("abbreviation", "-"),
                "age": p.get("age", "-"),
                "height": p.get("displayHeight", "-"),
                "weight": p.get("displayWeight", "-"),
                "experience": "Rookie" if exp_years == 0 else f"{exp_years} an{'s' if exp_years > 1 else ''}",
                "headshot": p.get("headshot", {}).get("href", ""),
            })

        if players:
            roster_groups.append({
                "group": group_name,
                "players": players,
            })

    if roster_groups:
        cache.set(cache_key, roster_groups, 21600)
    return roster_groups


def get_team_depth_chart(team_id):
    """Récupère et met en cache le depth chart ESPN d'une franchise."""
    if not team_id:
        return []

    cache_key = f"nfl_depth_chart_v3_{team_id}"
    cached_dc = cache.get(cache_key)
    if cached_dc is not None:
        return cached_dc

    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/depthcharts"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"ERREUR API DEPTH CHART (team_id={team_id}):", repr(e))
        return []

    units = (
        data.get("depthchart")
        or data.get("items")
        or data.get("team", {}).get("depthchart")
        or []
    )
    if not units:
        return []

    def _slot_key(item):
        if not isinstance(item, dict):
            return 999
        val = item.get("slot") if item.get("slot") is not None else item.get("rank")
        try:
            return int(val)
        except (TypeError, ValueError):
            return 999

    depth_chart = []
    for unit in units:
        if not isinstance(unit, dict):
            continue

        raw_name = unit.get("name", "")
        if "Special Teams" in raw_name:
            unit_name = "Équipes spéciales"
        elif "Defense" in raw_name:
            unit_name = raw_name.replace("Base ", "").replace("Defense", "Défense")
        elif "Offense" in raw_name:
            unit_name = raw_name.replace("Offense", "Attaque")
        elif any(tag in raw_name for tag in ["WR", "TE", "RB", "FB"]):
            unit_name = f"Attaque ({raw_name})"
        else:
            unit_name = raw_name or "Formation"

        positions_raw = unit.get("positions") or {}
        pos_iterable = (
            list(positions_raw.values())
            if isinstance(positions_raw, dict)
            else positions_raw
        )

        rows = []
        for pos_entry in pos_iterable:
            if not isinstance(pos_entry, dict):
                continue

            pos_info = pos_entry.get("position") or {}
            pos_abbr = pos_info.get("abbreviation", "-")
            pos_label = pos_info.get("name", pos_abbr)

            raw_athletes = pos_entry.get("athletes") or []
            if isinstance(raw_athletes, dict):
                raw_athletes = list(raw_athletes.values())

            athletes_sorted = sorted(raw_athletes, key=_slot_key)

            slots = []
            for item in athletes_sorted[:4]:
                if not isinstance(item, dict):
                    continue
                athlete = (
                    item.get("athlete")
                    if isinstance(item.get("athlete"), dict)
                    else item
                )
                name = (
                    athlete.get("displayName")
                    or athlete.get("fullName")
                    or athlete.get("shortName")
                    or athlete.get("name")
                )
                if name:
                    slots.append({
                        "name": name,
                        "jersey": athlete.get("jersey", ""),
                    })

            if slots:
                while len(slots) < 4:
                    slots.append(None)
                rows.append({
                    "abbr": pos_abbr,
                    "label": pos_label,
                    "slots": slots,
                })

        if rows:
            depth_chart.append({
                "unit": unit_name,
                "rows": rows,
            })

    if depth_chart:
        cache.set(cache_key, depth_chart, 21600)
    return depth_chart


# ==========================================
# 2. PARAMÈTRES GLOBAUX (Site Settings)
# ==========================================


@register_setting
class SocialMediaSettings(BaseGenericSetting):
    twitter = models.URLField(blank=True, null=True, help_text="Lien Twitter / X")
    facebook = models.URLField(blank=True, null=True, help_text="Lien Facebook")
    instagram = models.URLField(blank=True, null=True, help_text="Lien Instagram")
    youtube = models.URLField(blank=True, null=True, help_text="Chaîne YouTube")

    panels = [
        FieldPanel("twitter"),
        FieldPanel("facebook"),
        FieldPanel("instagram"),
        FieldPanel("youtube"),
    ]


@register_setting
class NavigationSettings(BaseGenericSetting):
    privacy_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Page de politique de confidentialité",
    )
    terms_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Page des conditions d'utilisation",
    )

    panels = [
        FieldPanel("privacy_page"),
        FieldPanel("terms_page"),
    ]


# ==========================================
# 3. PAGES DU SITE
# ==========================================


class TeamIndexPage(Page):
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["TeamPage"]

    def get_divisions(self):
        return ["Est", "Nord", "Sud", "Ouest"]


class TeamPage(Page):
    """Fiche par équipe (ex: Kansas City Chiefs)"""

    CONFERENCE_CHOICES = [
        ("AFC", "AFC"),
        ("NFC", "NFC"),
    ]
    DIVISION_CHOICES = [
        ("Est", "Est"),
        ("Nord", "Nord"),
        ("Sud", "Sud"),
        ("Ouest", "Ouest"),
    ]

    conference = models.CharField(max_length=5, choices=CONFERENCE_CHOICES)
    division = models.CharField(max_length=10, choices=DIVISION_CHOICES)
    logo = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    ville = models.CharField(max_length=100, blank=True, verbose_name="Ville / État")
    stade_nom = models.CharField(max_length=150, blank=True, verbose_name="Nom du stade")
    stade_capacite = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Capacité du stade"
    )
    stade_image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Photo du stade",
    )
    entraineur_principal = models.CharField(
        max_length=120, blank=True, verbose_name="Entraîneur principal (Head Coach)"
    )
    annee_creation = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Année de création"
    )
    super_bowls = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Super Bowls remportés",
        help_text="Ex: 4 (IV, LIV, LVII, LVIII) ou Aucun",
    )

    description = RichTextField(blank=True)
    nfl_official_url = models.URLField(
        blank=True,
        verbose_name="Lien officiel NFL.com",
        help_text="ex: https://www.nfl.com/teams/kansas-city-chiefs/",
    )
    rss_feed_url = models.URLField(
        blank=True,
        verbose_name="Flux RSS NFL / Actualités",
        help_text="URL du flux RSS (ex: https://www.nfl.com/news/rss)",
    )
    media_embeds = StreamField(
        [
            ("embed", EmbedBlock(label="Intégration Vidéo / Média NFL")),
            ("rich_text", blocks.RichTextBlock(label="Texte / Bloc personnalisé")),
        ],
        blank=True,
        use_json_field=True,
        verbose_name="Médias intégrés NFL.com",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("conference"),
                FieldPanel("division"),
                FieldPanel("logo"),
                FieldPanel("ville"),
                FieldPanel("annee_creation"),
                FieldPanel("super_bowls"),
            ],
            heading="Identité de la franchise",
        ),
        MultiFieldPanel(
            [
                FieldPanel("entraineur_principal"),
                FieldPanel("stade_nom"),
                FieldPanel("stade_capacite"),
                FieldPanel("stade_image"),
            ],
            heading="Staff & Stade",
        ),
        InlinePanel("key_players", label="Joueurs clés"),
        FieldPanel("description"),
        MultiFieldPanel(
            [
                FieldPanel("nfl_official_url"),
                FieldPanel("rss_feed_url"),
                FieldPanel("media_embeds"),
            ],
            heading="Liens officiels & Médias",
        ),
    ]

    parent_page_types = ["TeamIndexPage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        team_id = ESPN_TEAM_IDS.get(self.slug)

        # 1. Actualités (Flux RSS prioritaire, sinon API ESPN mise en cache 15 min)
        cache_key = f"team_news_v2_{self.id}"
        news_items = cache.get(cache_key)

        if news_items is None:
            news_items = []
            headers = {"User-Agent": "Mozilla/5.0"}

            if self.rss_feed_url:
                try:
                    resp = requests.get(self.rss_feed_url, headers=headers, timeout=5)
                    feed = feedparser.parse(resp.content)
                    news_items = [
                        {"title": e.get("title", ""), "link": e.get("link", "")}
                        for e in feed.entries[:4]
                    ]
                except Exception:
                    news_items = []

            if not news_items:
                try:
                    params = {"limit": 4}
                    if team_id:
                        params["team"] = team_id

                    resp = requests.get(
                        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news",
                        params=params,
                        headers=headers,
                        timeout=5,
                    ).json()

                    for article in resp.get("articles", [])[:4]:
                        link = article.get("links", {}).get("web", {}).get("href", "")
                        if article.get("headline") and link:
                            news_items.append({
                                "title": article["headline"],
                                "link": link,
                            })
                except Exception:
                    news_items = []

            if news_items:
                cache.set(cache_key, news_items, 900)

        # 2. Statistiques collectives et individuelles (2015-2016 à 2026-2027)
        seasons, selected_season = get_season_selection(request, self.season_stats)

        context["official_url"] = self.nfl_official_url or f"https://www.nfl.com/teams/{self.slug}/"
        context["news_items"] = news_items
        context["depth_chart"] = get_team_depth_chart(team_id)
        context["roster"] = get_team_roster(team_id)
        context["available_seasons"] = seasons
        context["selected_season"] = selected_season
        context["team_stats"] = self.season_stats.filter(season_year=selected_season).first()
        context["players_stats"] = self.player_stats.filter(season_year=selected_season)
        return context


class TeamKeyPlayer(Orderable):
    """Joueurs clés administrables directement dans la fiche d'une équipe"""

    page = ParentalKey(
        TeamPage, on_delete=models.CASCADE, related_name="key_players"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom du joueur")
    poste = models.CharField(
        max_length=20,
        verbose_name="Poste",
        help_text="Ex: QB, WR, RB, TE, DE, LB, CB...",
    )
    numero = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Numéro de maillot"
    )
    photo = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    bio_courte = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Description / Palmarès rapide",
        help_text="Ex: 3x MVP du Super Bowl, capitaine de l'attaque",
    )

    panels = [
        FieldPanel("nom"),
        FieldPanel("poste"),
        FieldPanel("numero"),
        FieldPanel("photo"),
        FieldPanel("bio_courte"),
    ]


class SeasonIndexPage(Page):
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["SeasonPage"]


class SeasonPage(Page):
    season_year = models.IntegerField(
        default=2026,
        verbose_name="Année de la saison",
        help_text="Ex: 2026 pour la saison 2026-2027",
    )
    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("season_year"),
        FieldPanel("intro"),
    ]

    parent_page_types = ["SeasonIndexPage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        headers = {"User-Agent": "Mozilla/5.0"}

        seasons, selected_season = get_season_selection(
            request, TeamSeasonStats.objects.all(), default_year=self.season_year
        )
        season_type = str(request.GET.get("type", "2"))
        selected_week = str(request.GET.get("week") or "1")
        current_week = selected_week

        # 1. MATCHS DE LA SEMAINE SÉLECTIONNÉE (API ESPN)
        games = []
        cache_key_games = f"nfl_season_{selected_season}_type_{season_type}_week_{selected_week}"
        cached_games_data = cache.get(cache_key_games)

        if cached_games_data is None:
            try:
                response = requests.get(
                    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
                    params={
                        "dates": selected_season,
                        "seasontype": season_type,
                        "week": selected_week,
                    },
                    headers=headers,
                    timeout=10,
                )
                data = response.json()
                current_week = str(data.get("week", {}).get("number", selected_week))

                for event in data.get("events", []):
                    competition = event.get("competitions", [{}])[0]
                    competitors = competition.get("competitors", [])

                    home_team = next((c for c in competitors if c.get("homeAway") == "home"), {})
                    away_team = next((c for c in competitors if c.get("homeAway") == "away"), {})
                    status_type = event.get("status", {}).get("type", {})

                    games.append({
                        "status": status_type.get("shortDetail", "À venir"),
                        "completed": status_type.get("completed", False),
                        "home_name": home_team.get("team", {}).get("displayName"),
                        "home_logo": home_team.get("team", {}).get("logo"),
                        "home_score": home_team.get("score", "-"),
                        "away_name": away_team.get("team", {}).get("displayName"),
                        "away_logo": away_team.get("team", {}).get("logo"),
                        "away_score": away_team.get("score", "-"),
                    })

                if games:
                    cache.set(cache_key_games, {"games": games, "week": current_week}, 600)
            except Exception as e:
                print("ERREUR SEASON GAMES:", e)
                games = []
        else:
            games = cached_games_data["games"]
            current_week = str(cached_games_data["week"])

        # 2. CLASSEMENTS PAR DIVISION (avec anciens codes OAK, SD, STL, WSH inclus)
        cache_key_standings = f"nfl_div_standings_v3_{selected_season}"
        standings = cache.get(cache_key_standings)

        if standings is None:
            standings = []
            try:
                resp = requests.get(
                    "https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
                    params={"season": selected_season},
                    headers=headers,
                    timeout=10,
                ).json()

                for conf in resp.get("children", []):
                    conf_abbr = conf.get("abbreviation", "")
                    if conf_abbr not in NFL_DIVISIONS:
                        continue

                    entries = conf.get("standings", {}).get("entries", [])
                    if not entries:
                        for div in conf.get("children", []):
                            entries.extend(div.get("standings", {}).get("entries", []))

                    teams_by_abbr = {}
                    for entry in entries:
                        team = entry.get("team", {})
                        abbr = team.get("abbreviation", "")
                        stats_val = {s.get("name"): s.get("value", 0) for s in entry.get("stats", [])}
                        stats_disp = {s.get("name"): s.get("displayValue", "0") for s in entry.get("stats", [])}
                        teams_by_abbr[abbr] = {
                            "name": team.get("shortDisplayName", team.get("displayName", "")),
                            "logo": team.get("logos", [{}])[0].get("href", ""),
                            "wins": int(stats_val.get("wins", 0)),
                            "losses": int(stats_val.get("losses", 0)),
                            "ties": int(stats_val.get("ties", 0)),
                            "pct": stats_disp.get("winPercent", ".000"),
                        }

                    divisions_list = []
                    for div_name, abbr_list in NFL_DIVISIONS[conf_abbr].items():
                        div_teams = [teams_by_abbr[a] for a in abbr_list if a in teams_by_abbr]
                        div_teams.sort(key=lambda x: (x["wins"], float(x["pct"] or 0)), reverse=True)
                        if div_teams:
                            divisions_list.append({
                                "name": div_name,
                                "teams": div_teams,
                            })

                    if divisions_list:
                        standings.append({
                            "conference": conf_abbr,
                            "divisions": divisions_list,
                        })

                if standings:
                    cache.set(cache_key_standings, standings, 900)
            except Exception as e:
                print("ERREUR SEASON STANDINGS:", e)
                standings = []

        # 3. LIBELLÉ DE SEMAINE ACTIF & BOXSCORES SYNCHRONISÉS SEMAINE PAR SEMAINE
        playoff_labels = {
            "1": "Wild Card",
            "2": "Divisional",
            "3": "Finales Conf.",
            "4": "Super Bowl",
            "5": "Super Bowl",
        }
        if season_type == "3":
            selected_week_label = playoff_labels.get(str(current_week), "Super Bowl")
        else:
            selected_week_label = f"Semaine {current_week}"

        def _boxscore_sort_key(match_obj):
            try:
                return (datetime.strptime(match_obj.match_date, "%d/%m/%Y"), match_obj.id)
            except Exception:
                return (datetime.max, match_obj.id)

        week_boxscores = sorted(
            MatchBoxScore.objects.filter(
                season_year=selected_season,
                week_label=selected_week_label,
            ).select_related("away_team", "home_team"),
            key=_boxscore_sort_key,
        )

        # 4. STATISTIQUES COLLECTIVES & LEADERS JOUEURS (2015-2026)
        season_players = PlayerSeasonStats.objects.filter(season_year=selected_season)

        context["available_seasons"] = seasons
        context["selected_season"] = selected_season
        context["selected_week_label"] = selected_week_label
        context["full_standings"] = (
            TeamSeasonStats.objects.filter(season_year=selected_season)
            .select_related("team")
            .order_by("-wins", "losses", "-points_for")
        )
        context["boxscores"] = week_boxscores
        context["top_passers"] = season_players.filter(pass_yards__gt=0).order_by("-pass_yards")[:5]
        context["top_rushers"] = season_players.filter(rush_yards__gt=0).order_by("-rush_yards")[:5]
        context["top_receivers"] = season_players.filter(rec_yards__gt=0).order_by("-rec_yards")[:5]
        context["top_defenders"] = season_players.filter(tackles__gt=0).order_by("-sacks", "-tackles")[:5]

        context["games"] = games
        context["season_type"] = season_type
        context["current_week"] = str(current_week)
        context["weeks_range"] = [str(w) for w in range(1, 19)]
        context["playoff_rounds"] = [
            {"week": "1", "label": "Wild Card"},
            {"week": "2", "label": "Divisional"},
            {"week": "3", "label": "Finales Conf."},
            {"week": "5", "label": "Super Bowl"},
        ]
        context["standings"] = standings
        return context


# --- HISTOIRE ET ARTICLES ---


class ArticleIndexPage(Page):
    """Page racine de la rubrique Histoire"""

    intro = RichTextField(blank=True, verbose_name="Introduction de la rubrique")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["ArticlePage"]

    def get_context(self, request):
        context = super().get_context(request)
        selected_cat = request.GET.get("cat", "")

        articles = ArticlePage.objects.live().descendant_of(self).order_by("-first_published_at")
        if selected_cat in ["histoire", "legendes", "moments"]:
            articles = articles.filter(categorie=selected_cat)

        context["articles"] = articles
        context["selected_cat"] = selected_cat
        context["categories"] = ArticlePage.CATEGORY_CHOICES
        return context


class ArticlePage(Page):
    """Articles (Histoire de la NFL, Légendes & joueurs, Grands moments)"""

    CATEGORY_CHOICES = [
        ("histoire", "Histoire de la NFL"),
        ("legendes", "Légendes et joueurs"),
        ("moments", "Grands moments"),
    ]

    categorie = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    chapeau = models.TextField(blank=True, help_text="Courte description de l'article")
    image_couverture = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    body = RichTextField()

    content_panels = Page.content_panels + [
        FieldPanel("categorie"),
        FieldPanel("chapeau"),
        FieldPanel("image_couverture"),
        FieldPanel("body"),
    ]

    parent_page_types = ["ArticleIndexPage"]


# --- CONTACT & PAGES LÉGALES ---


class FormField(AbstractFormField):
    page = ParentalKey(
        "pages.ContactPage",
        on_delete=models.CASCADE,
        related_name="form_fields",
    )


class ContactPage(AbstractEmailForm):
    """Page Contact avec constructeur de formulaire dynamique Wagtail"""

    intro = RichTextField(blank=True, verbose_name="Texte d'introduction")
    thank_you_text = RichTextField(
        blank=True,
        verbose_name="Message de confirmation après envoi",
    )
    rgpd_notice = models.TextField(
        blank=True,
        default="Les informations recueillies via ce formulaire sont uniquement utilisées pour répondre à votre demande et ne sont jamais cédées à des tiers.",
        verbose_name="Mention légale / RGPD",
    )

    content_panels = AbstractEmailForm.content_panels + [
        FormSubmissionsPanel(),
        FieldPanel("intro"),
        InlinePanel("form_fields", label="Champs du formulaire"),
        FieldPanel("rgpd_notice"),
        FieldPanel("thank_you_text"),
        MultiFieldPanel(
            [
                FieldRowPanel(
                    [
                        FieldPanel("from_address", classname="col6"),
                        FieldPanel("to_address", classname="col6"),
                    ]
                ),
                FieldPanel("subject"),
            ],
            heading="Configuration de l'envoi d'e-mail",
        ),
    ]


class StandardPage(Page):
    """Page éditoriale simple (Conditions d'utilisation, Politique de confidentialité, Mentions légales)"""

    last_updated = models.DateField(
        blank=True,
        null=True,
        verbose_name="Date de dernière mise à jour",
    )
    body = RichTextField(verbose_name="Contenu de la page")

    content_panels = Page.content_panels + [
        FieldPanel("last_updated"),
        FieldPanel("body"),
    ]

    parent_page_types = ["home.HomePage"]


# ==========================================
# 4. SNIPPETS & STATISTIQUES (LIVE & ARCHIVES)
# ==========================================


@register_snippet
class LiveMatchBanner(models.Model):
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activer le bandeau sur le site",
        help_text="Si plusieurs bandeaux sont actifs, le plus récent sera affiché.",
    )
    badge_label = models.CharField(
        max_length=40,
        default="EN DIRECT • NFL",
        verbose_name="Libellé du badge",
    )
    away_team = models.CharField(max_length=60, verbose_name="Équipe extérieure")
    away_score = models.PositiveIntegerField(default=0, verbose_name="Score extérieur")
    home_team = models.CharField(max_length=60, verbose_name="Équipe domicile")
    home_score = models.PositiveIntegerField(default=0, verbose_name="Score domicile")
    quarter_info = models.CharField(
        max_length=40,
        default="Q4 • 02:14",
        verbose_name="Quart-temps / Chrono",
    )
    match_link = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Lien vers le match (optionnel)",
        help_text="URL interne (ex: /saisons/2026/) ou externe.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel("is_active"),
        MultiFieldPanel(
            [
                FieldPanel("badge_label"),
                FieldPanel("quarter_info"),
                FieldPanel("match_link"),
            ],
            heading="Informations de diffusion",
        ),
        MultiFieldPanel(
            [
                FieldPanel("away_team"),
                FieldPanel("away_score"),
                FieldPanel("home_team"),
                FieldPanel("home_score"),
            ],
            heading="Affiche & Score en direct",
        ),
    ]

    class Meta:
        verbose_name = "Bandeau Match en direct"
        verbose_name_plural = "Bandeaux Matchs en direct"
        ordering = ["-updated_at"]

    def __str__(self):
        etat = "ACTIF" if self.is_active else "Inactif"
        return f"[{etat}] {self.away_team} {self.away_score} - {self.home_score} {self.home_team} ({self.quarter_info})"


@register_snippet
class TeamSeasonStats(models.Model):
    team = models.ForeignKey(
        "pages.TeamPage",
        on_delete=models.CASCADE,
        related_name="season_stats",
        verbose_name="Franchise",
    )
    season_year = models.PositiveIntegerField(default=2026, verbose_name="Saison")
    wins = models.PositiveIntegerField(default=0, verbose_name="Victoires (V)")
    losses = models.PositiveIntegerField(default=0, verbose_name="Défaites (D)")
    ties = models.PositiveIntegerField(default=0, verbose_name="Nuls (N)")
    points_for = models.PositiveIntegerField(default=0, verbose_name="Points marqués")
    points_against = models.PositiveIntegerField(default=0, verbose_name="Points encaissés")
    passing_yards = models.PositiveIntegerField(default=0, verbose_name="Yards à la passe")
    rushing_yards = models.PositiveIntegerField(default=0, verbose_name="Yards au sol")
    turnover_diff = models.IntegerField(default=0, verbose_name="Différentiel Turnovers")

    panels = [
        MultiFieldPanel([FieldPanel("team"), FieldPanel("season_year")], heading="Franchise & Saison"),
        MultiFieldPanel([FieldPanel("wins"), FieldPanel("losses"), FieldPanel("ties")], heading="Bilan"),
        MultiFieldPanel(
            [
                FieldPanel("points_for"),
                FieldPanel("points_against"),
                FieldPanel("passing_yards"),
                FieldPanel("rushing_yards"),
                FieldPanel("turnover_diff"),
            ],
            heading="Statistiques collectives",
        ),
    ]

    class Meta:
        verbose_name = "Statistiques Équipe (Saison)"
        verbose_name_plural = "Statistiques Équipes (Saison)"
        ordering = ["-season_year", "-wins", "losses"]
        unique_together = ("team", "season_year")

    @property
    def win_pct(self):
        total = self.wins + self.losses + self.ties
        if total == 0:
            return ".000"
        return f"{(self.wins + 0.5 * self.ties) / total:.3f}".lstrip("0")

    def __str__(self):
        return f"{self.team.title} ({self.season_year}-{self.season_year + 1}) : {self.wins}-{self.losses}"


@register_snippet
class PlayerSeasonStats(models.Model):
    POSITION_CHOICES = [
        ("QB", "Quarterback (QB)"),
        ("RB", "Running Back (RB)"),
        ("WR", "Wide Receiver (WR)"),
        ("TE", "Tight End (TE)"),
        ("DEF", "Défense (DL/LB/DB)"),
    ]

    team = models.ForeignKey(
        "pages.TeamPage",
        on_delete=models.CASCADE,
        related_name="player_stats",
        verbose_name="Équipe",
    )
    season_year = models.PositiveIntegerField(default=2026, verbose_name="Saison")
    player_name = models.CharField(max_length=100, verbose_name="Nom du joueur")
    jersey_number = models.PositiveIntegerField(default=0, verbose_name="Numéro")
    position = models.CharField(max_length=5, choices=POSITION_CHOICES, default="QB", verbose_name="Poste")
    games_played = models.PositiveIntegerField(default=0, verbose_name="Matchs joués")

    pass_yards = models.IntegerField(default=0, verbose_name="Yards passe")
    pass_td = models.PositiveIntegerField(default=0, verbose_name="TD passe")
    interceptions = models.PositiveIntegerField(default=0, verbose_name="Interceptions lancées")
    rush_yards = models.IntegerField(default=0, verbose_name="Yards course")
    rush_td = models.PositiveIntegerField(default=0, verbose_name="TD course")
    receptions = models.PositiveIntegerField(default=0, verbose_name="Réceptions")
    rec_yards = models.IntegerField(default=0, verbose_name="Yards réception")
    rec_td = models.PositiveIntegerField(default=0, verbose_name="TD réception")

    tackles = models.PositiveIntegerField(default=0, verbose_name="Plaquages")
    sacks = models.DecimalField(max_digits=4, decimal_places=1, default=0.0, verbose_name="Sacks")
    def_interceptions = models.PositiveIntegerField(default=0, verbose_name="Interceptions (Déf)")

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("team"),
                FieldPanel("season_year"),
                FieldPanel("player_name"),
                FieldPanel("jersey_number"),
                FieldPanel("position"),
                FieldPanel("games_played"),
            ],
            heading="Identité du joueur",
        ),
        MultiFieldPanel(
            [
                FieldPanel("pass_yards"),
                FieldPanel("pass_td"),
                FieldPanel("interceptions"),
                FieldPanel("rush_yards"),
                FieldPanel("rush_td"),
                FieldPanel("receptions"),
                FieldPanel("rec_yards"),
                FieldPanel("rec_td"),
            ],
            heading="Statistiques Offensives",
        ),
        MultiFieldPanel(
            [
                FieldPanel("tackles"),
                FieldPanel("sacks"),
                FieldPanel("def_interceptions"),
            ],
            heading="Statistiques Défensives",
        ),
    ]

    class Meta:
        verbose_name = "Statistiques Joueur"
        verbose_name_plural = "Statistiques Joueurs"
        ordering = ["-season_year", "-pass_yards", "-rush_yards", "-rec_yards", "-tackles"]

    def __str__(self):
        return f"{self.player_name} ({self.position} - {self.team.title} {self.season_year})"


@register_snippet
class MatchBoxScore(models.Model):
    season_year = models.PositiveIntegerField(default=2026, verbose_name="Saison")
    week_label = models.CharField(
        max_length=40,
        default="Semaine 1",
        verbose_name="Semaine / Tour",
        help_text="Ex: Semaine 1, Wild Card, Super Bowl LX",
    )
    match_date = models.CharField(max_length=50, default="Dim. 19h00", verbose_name="Date / Horaire")
    is_final = models.BooleanField(default=True, verbose_name="Match terminé (FINAL)")

    away_team = models.ForeignKey(
        "pages.TeamPage",
        on_delete=models.CASCADE,
        related_name="away_matches",
        verbose_name="Équipe extérieure",
    )
    home_team = models.ForeignKey(
        "pages.TeamPage",
        on_delete=models.CASCADE,
        related_name="home_matches",
        verbose_name="Équipe domicile",
    )
    away_score = models.PositiveIntegerField(default=0, verbose_name="Score extérieur")
    home_score = models.PositiveIntegerField(default=0, verbose_name="Score domicile")

    away_total_yards = models.PositiveIntegerField(default=0, verbose_name="Yards totaux (Ext.)")
    home_total_yards = models.PositiveIntegerField(default=0, verbose_name="Yards totaux (Dom.)")
    away_turnovers = models.PositiveIntegerField(default=0, verbose_name="Turnovers (Ext.)")
    home_turnovers = models.PositiveIntegerField(default=0, verbose_name="Turnovers (Dom.)")
    mvp_highlight = models.CharField(
        max_length=140,
        blank=True,
        verbose_name="Performance clé du match",
        help_text="Ex: B. Purdy : 298 yds, 3 TD • C. McCaffrey : 114 yds",
    )

    panels = [
        MultiFieldPanel([FieldPanel("season_year"), FieldPanel("week_label"), FieldPanel("match_date"), FieldPanel("is_final")], heading="Contexte"),
        MultiFieldPanel([FieldPanel("away_team"), FieldPanel("away_score"), FieldPanel("home_team"), FieldPanel("home_score")], heading="Score"),
        MultiFieldPanel(
            [
                FieldPanel("away_total_yards"),
                FieldPanel("home_total_yards"),
                FieldPanel("away_turnovers"),
                FieldPanel("home_turnovers"),
                FieldPanel("mvp_highlight"),
            ],
            heading="Statistiques du match (Boxscore)",
        ),
    ]

    class Meta:
        verbose_name = "Statistiques Match (Boxscore)"
        verbose_name_plural = "Statistiques Matchs (Boxscores)"
        ordering = ["-season_year", "-id"]

    def __str__(self):
        return f"{self.week_label} ({self.season_year}) : {self.away_team.title} {self.away_score} - {self.home_score} {self.home_team.title}"