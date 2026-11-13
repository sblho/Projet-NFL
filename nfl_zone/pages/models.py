import feedparser
import requests
from django import forms
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
from wagtail.models import Page
from wagtail.models import Orderable, Page


# ==========================================
# 1. ÉLÉMENTS GLOBAUX (Site Settings)
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
# 2. PAGES DU SITE
# ==========================================

# --- ÉQUIPES ---


class TeamIndexPage(Page):

    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["TeamPage"]

    def get_divisions(self):
        return ["Est", "Nord", "Sud", "Ouest"]

GROUP_LABELS = {
    "offense": "Attaque",
    "defense": "Défense",
    "specialTeam": "Équipes spéciales",
    "specialTeams": "Équipes spéciales",
}


def get_team_roster(team_id):
    """Récupère et met en cache le roster ESPN d'une franchise à partir de son ID ESPN."""
    if not team_id:
        return []

    cache_key = f"nfl_roster_v1_{team_id}"
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

    # Mise en cache pendant 6 heures (21 600 secondes)
    if roster_groups:
        cache.set(cache_key, roster_groups, 21600)
    return roster_groups



# --- DEPTH CHART ---
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
        print(f"DEPTH CHART VIDE (team_id={team_id}), clés JSON:", list(data.keys()))
        return []

    def _slot_key(item):
        if not isinstance(item, dict):
            return 999
        val = item.get("slot")
        if val is None:
            val = item.get("rank")
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

    # --- NOUVEAUX CHAMPS : INFOS FRANCHISE & STADE ---
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
            (
                "rich_text",
                blocks.RichTextBlock(label="Texte / Bloc personnalisé"),
            ),
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
    def get_context(self, request):
        context = super().get_context(request)
        context["official_url"] = self.nfl_official_url or f"https://www.nfl.com/teams/{self.slug}/"

        # Correspondance slug Wagtail -> ID équipe ESPN pour filtrer les actus par franchise
        ESPN_TEAM_IDS = {
            "arizona-cardinals": "22", "atlanta-falcons": "1", "baltimore-ravens": "33",
            "buffalo-bills": "2", "carolina-panthers": "29", "chicago-bears": "3",
            "cincinnati-bengals": "4", "cleveland-browns": "5", "dallas-cowboys": "6",
            "denver-broncos": "7", "detroit-lions": "8", "green-bay-packers": "9",
            "houston-texans": "34", "indianapolis-colts": "11", "jacksonville-jaguars": "30",
            "kansas-city-chiefs": "12", "las-vegas-raiders": "13", "los-angeles-chargers": "24",
            "los-angeles-rams": "14", "miami-dolphins": "15", "minnesota-vikings": "16",
            "new-england-patriots": "17", "new-orleans-saints": "18", "new-york-giants": "19",
            "new-york-jets": "20", "philadelphia-eagles": "21", "pittsburgh-steelers": "23",
            "san-francisco-49ers": "25", "seattle-seahawks": "26", "tampa-bay-buccaneers": "27",
            "tennessee-titans": "10", "washington-commanders": "28",
        }

        cache_key = f"team_news_v2_{self.id}"
        news_items = cache.get(cache_key)

        if news_items is None:
            news_items = []
            headers = {"User-Agent": "Mozilla/5.0"}

            # 1. Si un flux RSS personnalisé est saisi dans l'admin Wagtail, on l'utilise en priorité
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

            # 2. Sinon, récupération automatique des actus de la franchise via l'API ESPN
            if not news_items:
                try:
                    params = {"limit": 4}
                    team_id = ESPN_TEAM_IDS.get(self.slug)
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

        context["news_items"] = news_items
        
        if news_items:
                cache.set(cache_key, news_items, 900)

        team_id = ESPN_TEAM_IDS.get(self.slug)
        context["news_items"] = news_items
        context["depth_chart"] = get_team_depth_chart(team_id)
        context["roster"] = get_team_roster(team_id)
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


# --- SAISONS ---


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

    def get_context(self, request):
        context = super().get_context(request)
        headers = {"User-Agent": "Mozilla/5.0"}
        games = []

        # Récupère le type de saison (2 = Régulière par défaut, 3 = Playoffs)
        season_type = request.GET.get("type", "2")
        selected_week = request.GET.get("week")

        # Si aucune semaine n'est sélectionnée, on force la Semaine 1 (ou le tour 1 en Playoffs)
        # pour éviter qu'ESPN ne renvoie les 272 matchs de toute l'année
        if not selected_week:
            selected_week = "1"

        current_week = selected_week

        # 1. MATCHS DE LA SEMAINE SÉLECTIONNÉE
        cache_key_games = f"nfl_season_{self.season_year}_type_{season_type}_week_{selected_week}"
        cached_games_data = cache.get(cache_key_games)

        if cached_games_data is None:
            try:
                url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
                params = {
                    "dates": self.season_year,
                    "seasontype": season_type,
                    "week": selected_week,
                }

                response = requests.get(url, params=params, headers=headers, timeout=10)
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
            current_week = cached_games_data["week"]

        # 2. CLASSEMENTS PAR DIVISION (AFC & NFC : Est, Nord, Sud, Ouest)
        cache_key_standings = f"nfl_div_standings_v2_{self.season_year}"
        standings = cache.get(cache_key_standings)
        if standings is None:
            standings = []
            try:
                resp = requests.get(
                    "https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
                    params={"season": self.season_year},
                    headers=headers,
                    timeout=10,
                ).json()

                # Répartition officielle des 32 franchises NFL par abréviation
                NFL_DIVISIONS = {
                    "AFC": {
                        "AFC Est": ["BUF", "MIA", "NE", "NYJ"],
                        "AFC Nord": ["BAL", "CIN", "CLE", "PIT"],
                        "AFC Sud": ["HOU", "IND", "JAX", "TEN"],
                        "AFC Ouest": ["DEN", "KC", "LV", "LAC"],
                    },
                    "NFC": {
                        "NFC Est": ["DAL", "NYG", "PHI", "WSH", "WAS"],
                        "NFC Nord": ["CHI", "DET", "GB", "MIN"],
                        "NFC Sud": ["ATL", "CAR", "NO", "TB"],
                        "NFC Ouest": ["ARI", "LAR", "LA", "SF", "SEA"],
                    },
                }

                for conf in resp.get("children", []):
                    conf_abbr = conf.get("abbreviation", "")
                    if conf_abbr not in NFL_DIVISIONS:
                        continue

                    entries = conf.get("standings", {}).get("entries", [])
                    if not entries:
                        for div in conf.get("children", []):
                            entries.extend(div.get("standings", {}).get("entries", []))

                    # Indexation des équipes par abréviation
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

        context["games"] = games
        context["season_type"] = str(season_type)
        context["current_week"] = str(current_week)
        context["weeks_range"] = [str(w) for w in range(1, 19)]
        context["playoff_rounds"] = [
            {"week": "1", "label": "Wild Card"},
            {"week": "2", "label": "Divisional"},
            {"week": "3", "label": "Finales Conf."},
            {"week": "5", "label": "🏆 Super Bowl"},
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


# --- CONTACT ---


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

# --- PAGES LÉGALES & CONTENU SIMPLE ---

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
