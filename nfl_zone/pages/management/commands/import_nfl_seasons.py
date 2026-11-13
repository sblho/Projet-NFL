import requests
from django.core.management.base import BaseCommand
from pages.models import SeasonIndexPage, SeasonPage

# Résumés éditoriaux en français (modifiables librement ensuite dans Wagtail Admin)
HISTORICAL_SUMMARIES = {
    2024: (
        "<p><strong>Saison NFL 2024-2025 — Super Bowl LIX :</strong> Les <strong>Philadelphia Eagles</strong> "
        "remportent le deuxième Super Bowl de leur histoire en dominant les Kansas City Chiefs (40-22) à La Nouvelle-Orléans. "
        "Le quarterback <strong>Jalen Hurts</strong> est élu MVP de la finale.</p>"
    ),
    2023: (
        "<p><strong>Saison NFL 2023-2024 — Super Bowl LVIII :</strong> Au terme d'un thriller conclu en prolongation à Las Vegas, "
        "les <strong>Kansas City Chiefs</strong> conservent leur titre face aux San Francisco 49ers (25-22). "
        "<strong>Patrick Mahomes</strong> décroche son troisième trophée de MVP du Super Bowl.</p>"
    ),
    2022: (
        "<p><strong>Saison NFL 2022-2023 — Super Bowl LVII :</strong> Les <strong>Kansas City Chiefs</strong> s'imposent "
        "38-35 face aux Philadelphia Eagles à Glendale dans un duel offensif spectaculaire porté par <strong>Patrick Mahomes</strong> (MVP).</p>"
    ),
    2021: (
        "<p><strong>Saison NFL 2021-2022 — Super Bowl LVI :</strong> À domicile au SoFi Stadium, les <strong>Los Angeles Rams</strong> "
        "battent les Cincinnati Bengals (23-20) grâce à une fin de match décisive du receveur <strong>Cooper Kupp</strong> (MVP).</p>"
    ),
    2020: (
        "<p><strong>Saison NFL 2020-2021 — Super Bowl LV :</strong> Pour sa première saison en Floride, <strong>Tom Brady</strong> "
        "mène les <strong>Tampa Bay Buccaneers</strong> au sacre dans leur propre stade face aux Kansas City Chiefs (31-9).</p>"
    ),
    2019: (
        "<p><strong>Saison NFL 2019-2020 — Super Bowl LIV :</strong> Menés de 10 points dans le dernier quart-temps, les "
        "<strong>Kansas City Chiefs</strong> renversent les San Francisco 49ers (31-20) et offrent à Andy Reid son premier titre.</p>"
    ),
    2018: (
        "<p><strong>Saison NFL 2018-2019 — Super Bowl LIII :</strong> Au terme d'une bataille défensive historique à Atlanta, "
        "les <strong>New England Patriots</strong> dominent les Los Angeles Rams (13-3), avec <strong>Julian Edelman</strong> élu MVP.</p>"
    ),
    2017: (
        "<p><strong>Saison NFL 2017-2018 — Super Bowl LII :</strong> Portés par <strong>Nick Foles</strong> (MVP) et le célèbre « Philly Special », "
        "les <strong>Philadelphia Eagles</strong> décrochent leur premier Super Bowl face aux New England Patriots (41-33).</p>"
    ),
    2016: (
        "<p><strong>Saison NFL 2016-2017 — Super Bowl LI :</strong> Menés 28-3 au troisième quart-temps, les <strong>New England Patriots</strong> "
        "signent la plus grande remontée de l'histoire du Super Bowl pour battre les Atlanta Falcons en prolongation (34-28).</p>"
    ),
    2015: (
        "<p><strong>Saison NFL 2015-2016 — Super Bowl 50 :</strong> La défense intraitable des <strong>Denver Broncos</strong>, "
        "menée par le MVP <strong>Von Miller</strong>, étouffe les Carolina Panthers (24-10) pour le dernier match de Peyton Manning.</p>"
    ),
}


class Command(BaseCommand):
    help = "Importe les anciennes saisons NFL sous SeasonIndexPage tout en les laissant modifiables dans Wagtail Admin."

    def add_arguments(self, parser):
        parser.add_argument(
            "--start",
            type=int,
            default=2015,
            help="Première année de saison à importer (ex: 2015 pour 2015-2016).",
        )
        parser.add_argument(
            "--end",
            type=int,
            default=2025,
            help="Dernière année de saison à importer (ex: 2025 pour 2025-2026).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Met à jour le titre et l'introduction des saisons déjà existantes.",
        )

    def _fetch_super_bowl_summary(self, year):
        """Récupère automatiquement l'affiche et le score du Super Bowl via ESPN si aucun résumé manuel n'est défini."""
        if year in HISTORICAL_SUMMARIES:
            return HISTORICAL_SUMMARIES[year]

        try:
            url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
            params = {"dates": year, "seasontype": "3", "week": "5"}
            data = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=6).json()
            events = data.get("events", [])
            if events:
                comp = events[0].get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                if len(competitors) == 2:
                    t1, t2 = competitors[0], competitors[1]
                    n1 = t1.get("team", {}).get("displayName", "")
                    s1 = t1.get("score", "")
                    n2 = t2.get("team", {}).get("displayName", "")
                    s2 = t2.get("score", "")
                    if n1 and n2 and s1 and s2:
                        return (
                            f"<p><strong>Archives de la saison NFL {year}-{year + 1} :</strong> "
                            f"Finale du Super Bowl disputée entre les <strong>{n1}</strong> ({s1}) "
                            f"et les <strong>{n2}</strong> ({s2}). Retrouvez ci-dessous tous les résultats par semaine et les classements par division.</p>"
                        )
        except Exception:
            pass

        return (
            f"<p>Archives complètes de la saison NFL <strong>{year}-{year + 1}</strong> : "
            f"calendrier, résultats de la saison régulière, tableau des Playoffs et classements par division.</p>"
        )

    def handle(self, *args, **options):
        start_year = options["start"]
        end_year = options["end"]
        force = options["force"]

        if start_year > end_year:
            self.stdout.write(self.style.ERROR("L'année --start doit être inférieure ou égale à --end."))
            return

        index_page = SeasonIndexPage.objects.live().first() or SeasonIndexPage.objects.first()
        if not index_page:
            self.stdout.write(
                self.style.ERROR(
                    "Aucune page 'SeasonIndexPage' (Saisons) trouvée dans Wagtail. Crée d'abord la rubrique Saisons dans l'admin."
                )
            )
            return

        created_count = 0
        updated_count = 0

        # Import de la plus récente à la plus ancienne pour un affichage chronologique inversé
        for year in range(end_year, start_year - 1, -1):
            title = f"Saison {year}-{year + 1}"
            slug = f"saison-{year}-{year + 1}"
            intro_html = self._fetch_super_bowl_summary(year)

            existing_page = SeasonPage.objects.filter(season_year=year).first()

            if existing_page:
                if force:
                    existing_page.title = title
                    existing_page.intro = intro_html
                    revision = existing_page.save_revision()
                    revision.publish()
                    updated_count += 1
                    self.stdout.write(f"Mise à jour : {title}")
                else:
                    self.stdout.write(f"Ignorée (déjà présente) : {existing_page.title} ({year})")
                continue

            season_page = SeasonPage(
                title=title,
                slug=slug,
                season_year=year,
                intro=intro_html,
            )
            index_page.add_child(instance=season_page)
            revision = season_page.save_revision()
            revision.publish()
            created_count += 1
            self.stdout.write(f"Créée : {title}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImport des saisons terminé : {created_count} créée(s), {updated_count} mise(s) à jour."
            )
        )