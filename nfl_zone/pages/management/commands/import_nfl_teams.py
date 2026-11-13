import time
import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from wagtail.images.models import Image as WagtailImage

from pages.models import (
    TeamIndexPage,
    TeamKeyPlayer,
    TeamPage,
    get_team_depth_chart,
    get_team_roster,
)

# Référentiel des 32 franchises (aligné avec ESPN_TEAM_IDS et les choix de TeamPage)
NFL_TEAMS_DATA = [
    # --- AFC EST ---
    {
        "slug": "buffalo-bills",
        "title": "Buffalo Bills",
        "espn_id": "2",
        "conference": "AFC",
        "ville": "Orchard Park, New York",
        "stade_nom": "Highmark Stadium",
        "stade_capacite": 71608,
        "coach_fallback": "Sean McDermott",
        "annee_creation": 1960,
        "super_bowls": "Aucun (4 participations : XXV, XXVI, XXVII, XXVIII)",
        "description": "<p>Fondés en 1960, les Buffalo Bills sont célèbres pour la ferveur de leur public, la « Bills Mafia », et pour avoir disputé quatre Super Bowls consécutifs au début des années 1990.</p>",
    },
    {
        "slug": "miami-dolphins",
        "title": "Miami Dolphins",
        "espn_id": "15",
        "conference": "AFC",
        "division": "Est",
        "ville": "Miami Gardens, Floride",
        "stade_nom": "Hard Rock Stadium",
        "stade_capacite": 65326,
        "coach_fallback": "Mike McDaniel",
        "annee_creation": 1966,
        "super_bowls": "2 (VII, VIII)",
        "description": "<p>Les Miami Dolphins sont la seule franchise de l'histoire de la NFL à avoir réalisé une saison parfaite invaincue, remportant le Super Bowl VII en 1972 sous la direction de Don Shula.</p>",
    },
    {
        "slug": "new-england-patriots",
        "title": "New England Patriots",
        "espn_id": "17",
        "conference": "AFC",
        "division": "Est",
        "ville": "Foxborough, Massachusetts",
        "stade_nom": "Gillette Stadium",
        "stade_capacite": 64628,
        "coach_fallback": "Mike Vrabel",
        "annee_creation": 1960,
        "super_bowls": "6 (XXXVI, XXXVIII, XXXIX, XLIX, LI, LIII)",
        "description": "<p>Portés par la dynastie historique du duo Bill Belichick – Tom Brady, les New England Patriots codétiennent le record de six Super Bowls remportés.</p>",
    },
    {
        "slug": "new-york-jets",
        "title": "New York Jets",
        "espn_id": "20",
        "conference": "AFC",
        "division": "Est",
        "ville": "East Rutherford, New Jersey",
        "stade_nom": "MetLife Stadium",
        "stade_capacite": 82500,
        "coach_fallback": "Aaron Glenn",
        "annee_creation": 1960,
        "super_bowls": "1 (III)",
        "description": "<p>Les New York Jets ont marqué l'histoire du football américain en remportant le Super Bowl III en 1969 grâce à la célèbre garantie du quarterback Joe Namath.</p>",
    },
    # --- AFC NORD ---
    {
        "slug": "baltimore-ravens",
        "title": "Baltimore Ravens",
        "espn_id": "33",
        "conference": "AFC",
        "division": "Nord",
        "ville": "Baltimore, Maryland",
        "stade_nom": "M&T Bank Stadium",
        "stade_capacite": 71008,
        "coach_fallback": "John Harbaugh",
        "annee_creation": 1996,
        "super_bowls": "2 (XXXV, XLVII)",
        "description": "<p>Créés en 1996, les Baltimore Ravens se sont bâtis une réputation d'excellence défensive autour de légendes comme Ray Lewis et Ed Reed.</p>",
    },
    {
        "slug": "cincinnati-bengals",
        "title": "Cincinnati Bengals",
        "espn_id": "4",
        "conference": "AFC",
        "division": "Nord",
        "ville": "Cincinnati, Ohio",
        "stade_nom": "Paycor Stadium",
        "stade_capacite": 65515,
        "coach_fallback": "Zac Taylor",
        "annee_creation": 1968,
        "super_bowls": "Aucun (3 participations : XVI, XXIII, LVI)",
        "description": "<p>Fondés par le légendaire entraîneur Paul Brown en 1968, les Cincinnati Bengals sont reconnus pour leur attaque spectaculaire et leurs casques rayés emblématiques.</p>",
    },
    {
        "slug": "cleveland-browns",
        "title": "Cleveland Browns",
        "espn_id": "5",
        "conference": "AFC",
        "division": "Nord",
        "ville": "Cleveland, Ohio",
        "stade_nom": "Huntington Bank Field",
        "stade_capacite": 67431,
        "coach_fallback": "Kevin Stefanski",
        "annee_creation": 1946,
        "super_bowls": "Aucun (4 titres NFL avant l'ère Super Bowl)",
        "description": "<p>Franchise historique de l'Ohio soutenue par la célèbre « Dawg Pound », les Cleveland Browns ont dominé le football américain dans les années 1950.</p>",
    },
    {
        "slug": "pittsburgh-steelers",
        "title": "Pittsburgh Steelers",
        "espn_id": "23",
        "conference": "AFC",
        "division": "Nord",
        "ville": "Pittsburgh, Pennsylvanie",
        "stade_nom": "Acrisure Stadium",
        "stade_capacite": 68400,
        "coach_fallback": "Mike Tomlin",
        "annee_creation": 1933,
        "super_bowls": "6 (IX, X, XIII, XIV, XL, XLIII)",
        "description": "<p>Plus ancienne franchise de l'AFC, les Pittsburgh Steelers sont célèbres pour leur défense légendaire « Steel Curtain » et leur remarquable stabilité d'encadrement.</p>",
    },
    # --- AFC SUD ---
    {
        "slug": "houston-texans",
        "title": "Houston Texans",
        "espn_id": "34",
        "conference": "AFC",
        "division": "Sud",
        "ville": "Houston, Texas",
        "stade_nom": "NRG Stadium",
        "stade_capacite": 72220,
        "coach_fallback": "DeMeco Ryans",
        "annee_creation": 2002,
        "super_bowls": "Aucun",
        "description": "<p>Plus jeune franchise de la NFL, entrée dans la ligue en 2002, les Houston Texans incarnent le renouveau du football professionnel à Houston.</p>",
    },
    {
        "slug": "indianapolis-colts",
        "title": "Indianapolis Colts",
        "espn_id": "11",
        "conference": "AFC",
        "division": "Sud",
        "ville": "Indianapolis, Indiana",
        "stade_nom": "Lucas Oil Stadium",
        "stade_capacite": 67000,
        "coach_fallback": "Shane Steichen",
        "annee_creation": 1953,
        "super_bowls": "2 (V, XLI)",
        "description": "<p>D'abord basés à Baltimore avec Johnny Unitas puis installés à Indianapolis où Peyton Manning a brillé, les Colts possèdent un riche héritage offensif.</p>",
    },
    {
        "slug": "jacksonville-jaguars",
        "title": "Jacksonville Jaguars",
        "espn_id": "30",
        "conference": "AFC",
        "division": "Sud",
        "ville": "Jacksonville, Floride",
        "stade_nom": "EverBank Stadium",
        "stade_capacite": 67814,
        "coach_fallback": "Liam Coen",
        "annee_creation": 1995,
        "super_bowls": "Aucun",
        "description": "<p>Arrivés en NFL en 1995, les Jacksonville Jaguars ont rapidement atteint deux finales de conférence AFC dès leurs premières années d'existence.</p>",
    },
    {
        "slug": "tennessee-titans",
        "title": "Tennessee Titans",
        "espn_id": "10",
        "conference": "AFC",
        "division": "Sud",
        "ville": "Nashville, Tennessee",
        "stade_nom": "Nissan Stadium",
        "stade_capacite": 69143,
        "coach_fallback": "Brian Callahan",
        "annee_creation": 1960,
        "super_bowls": "Aucun (1 participation : XXXIV)",
        "description": "<p>Anciennement connus sous le nom des Houston Oilers avant leur déménagement à Nashville, les Tennessee Titans sont restés célèbres pour le « Music City Miracle ».</p>",
    },
    # --- AFC OUEST ---
    {
        "slug": "denver-broncos",
        "title": "Denver Broncos",
        "espn_id": "7",
        "conference": "AFC",
        "division": "Ouest",
        "ville": "Denver, Colorado",
        "stade_nom": "Empower Field at Mile High",
        "stade_capacite": 76125,
        "coach_fallback": "Sean Payton",
        "annee_creation": 1960,
        "super_bowls": "3 (XXXII, XXXIII, 50)",
        "description": "<p>Évoluant en altitude à Denver, les Broncos ont remporté trois Super Bowls grâce aux quarterbacks légendaires John Elway et Peyton Manning.</p>",
    },
    {
        "slug": "kansas-city-chiefs",
        "title": "Kansas City Chiefs",
        "espn_id": "12",
        "conference": "AFC",
        "division": "Ouest",
        "ville": "Kansas City, Missouri",
        "stade_nom": "GEHA Field at Arrowhead Stadium",
        "stade_capacite": 76416,
        "coach_fallback": "Andy Reid",
        "annee_creation": 1960,
        "super_bowls": "4 (IV, LIV, LVII, LVIII)",
        "description": "<p>Portés par le tandem Andy Reid – Patrick Mahomes et l'ambiance électrique d'Arrowhead Stadium, les Kansas City Chiefs dominent la NFL moderne.</p>",
    },
    {
        "slug": "las-vegas-raiders",
        "title": "Las Vegas Raiders",
        "espn_id": "13",
        "conference": "AFC",
        "division": "Ouest",
        "ville": "Paradise (Las Vegas), Nevada",
        "stade_nom": "Allegiant Stadium",
        "stade_capacite": 65000,
        "coach_fallback": "Pete Carroll",
        "annee_creation": 1960,
        "super_bowls": "3 (XI, XV, XVIII)",
        "description": "<p>Célèbres pour leurs couleurs argent et noir et la devise « Just Win, Baby » d'Al Davis, les Raiders évoluent désormais dans le ultra-moderne Allegiant Stadium.</p>",
    },
    {
        "slug": "los-angeles-chargers",
        "title": "Los Angeles Chargers",
        "espn_id": "24",
        "conference": "AFC",
        "division": "Ouest",
        "ville": "Inglewood (Los Angeles), Californie",
        "stade_nom": "SoFi Stadium",
        "stade_capacite": 70240,
        "coach_fallback": "Jim Harbaugh",
        "annee_creation": 1960,
        "super_bowls": "Aucun (1 participation : XXIX)",
        "description": "<p>Reconnus pour leur jeu aérien spectaculaire depuis l'ère Don Coryell, les Los Angeles Chargers partagent l'impressionnant SoFi Stadium en Californie.</p>",
    },
    # --- NFC EST ---
    {
        "slug": "dallas-cowboys",
        "title": "Dallas Cowboys",
        "espn_id": "6",
        "conference": "NFC",
        "division": "Est",
        "ville": "Arlington, Texas",
        "stade_nom": "AT&T Stadium",
        "stade_capacite": 80000,
        "coach_fallback": "Brian Schottenheimer",
        "annee_creation": 1960,
        "super_bowls": "5 (VI, XII, XXVII, XXVIII, XXX)",
        "description": "<p>Surnommés « America's Team », les Dallas Cowboys constituent l'une des franchises les plus emblématiques et médiatisées du sport mondial.</p>",
    },
    {
        "slug": "new-york-giants",
        "title": "New York Giants",
        "espn_id": "19",
        "conference": "NFC",
        "division": "Est",
        "ville": "East Rutherford, New Jersey",
        "stade_nom": "MetLife Stadium",
        "stade_capacite": 82500,
        "coach_fallback": "Brian Daboll",
        "annee_creation": 1925,
        "super_bowls": "4 (XXI, XXV, XLII, XLVI)",
        "description": "<p>Fondés en 1925, les New York Giants ont écrit certaines des plus grandes pages de la NFL, notamment leurs victoires mémorables aux Super Bowls XLII et XLVI.</p>",
    },
    {
        "slug": "philadelphia-eagles",
        "title": "Philadelphia Eagles",
        "espn_id": "21",
        "conference": "NFC",
        "division": "Est",
        "ville": "Philadelphie, Pennsylvanie",
        "stade_nom": "Lincoln Financial Field",
        "stade_capacite": 67594,
        "coach_fallback": "Nick Sirianni",
        "annee_creation": 1933,
        "super_bowls": "2 (LII, LIX)",
        "description": "<p>Soutenus par l'un des publics les plus passionnés de la ligue, les Philadelphia Eagles ont soulevé le trophée Vince Lombardi lors des Super Bowls LII et LIX.</p>",
    },
    {
        "slug": "washington-commanders",
        "title": "Washington Commanders",
        "espn_id": "28",
        "conference": "NFC",
        "division": "Est",
        "ville": "Landover, Maryland",
        "stade_nom": "Northwest Stadium",
        "stade_capacite": 62000,
        "coach_fallback": "Dan Quinn",
        "annee_creation": 1932,
        "super_bowls": "3 (XVII, XXII, XXVI)",
        "description": "<p>Franchise historique de la capitale américaine fondée en 1932, Washington a remporté trois Super Bowls sous la conduite de l'entraîneur Joe Gibbs.</p>",
    },
    # --- NFC NORD ---
    {
        "slug": "chicago-bears",
        "title": "Chicago Bears",
        "espn_id": "3",
        "conference": "NFC",
        "division": "Nord",
        "ville": "Chicago, Illinois",
        "stade_nom": "Soldier Field",
        "stade_capacite": 61500,
        "coach_fallback": "Ben Johnson",
        "annee_creation": 1920,
        "super_bowls": "1 (XX)",
        "description": "<p>Membres fondateurs de la NFL en 1920 sous l'impulsion de George Halas, les Chicago Bears restent célèbres pour leur défense historique de 1985.</p>",
    },
    {
        "slug": "detroit-lions",
        "title": "Detroit Lions",
        "espn_id": "8",
        "conference": "NFC",
        "division": "Nord",
        "ville": "Détroit, Michigan",
        "stade_nom": "Ford Field",
        "stade_capacite": 65000,
        "coach_fallback": "Dan Campbell",
        "annee_creation": 1930,
        "super_bowls": "Aucun (4 titres NFL avant l'ère Super Bowl)",
        "description": "<p>Traditionnels hôtes du match de Thanksgiving depuis 1934, les Detroit Lions ont retrouvé les sommets de la NFC sous l'impulsion de Dan Campbell.</p>",
    },
    {
        "slug": "green-bay-packers",
        "title": "Green Bay Packers",
        "espn_id": "9",
        "conference": "NFC",
        "division": "Nord",
        "ville": "Green Bay, Wisconsin",
        "stade_nom": "Lambeau Field",
        "stade_capacite": 81441,
        "coach_fallback": "Matt LaFleur",
        "annee_creation": 1919,
        "super_bowls": "4 (I, II, XXXI, XLV)",
        "description": "<p>Seule franchise détenue par ses supporters, les Green Bay Packers évoluent dans le mythique Lambeau Field et totalisent 13 titres de champions NFL.</p>",
    },
    {
        "slug": "minnesota-vikings",
        "title": "Minnesota Vikings",
        "espn_id": "16",
        "conference": "NFC",
        "division": "Nord",
        "ville": "Minneapolis, Minnesota",
        "stade_nom": "U.S. Bank Stadium",
        "stade_capacite": 66860,
        "coach_fallback": "Kevin O'Connell",
        "annee_creation": 1961,
        "super_bowls": "Aucun (4 participations : IV, VIII, IX, XI)",
        "description": "<p>Réputés pour leur ambiance « Skol » à l'U.S. Bank Stadium, les Minnesota Vikings figurent parmi les équipes les plus régulières de la NFC.</p>",
    },
    # --- NFC SUD ---
    {
        "slug": "atlanta-falcons",
        "title": "Atlanta Falcons",
        "espn_id": "1",
        "conference": "NFC",
        "division": "Sud",
        "ville": "Atlanta, Géorgie",
        "stade_nom": "Mercedes-Benz Stadium",
        "stade_capacite": 71000,
        "coach_fallback": "Raheem Morris",
        "annee_creation": 1966,
        "super_bowls": "Aucun (2 participations : XXXIII, LI)",
        "description": "<p>Installés dans le spectaculaire Mercedes-Benz Stadium à toit rétractable, les Atlanta Falcons représentent la capitale de la Géorgie depuis 1966.</p>",
    },
    {
        "slug": "carolina-panthers",
        "title": "Carolina Panthers",
        "espn_id": "29",
        "conference": "NFC",
        "division": "Sud",
        "ville": "Charlotte, Caroline du Nord",
        "stade_nom": "Bank of America Stadium",
        "stade_capacite": 74867,
        "coach_fallback": "Dave Canales",
        "annee_creation": 1995,
        "super_bowls": "Aucun (2 participations : XXXVIII, 50)",
        "description": "<p>Représentant les deux Carolines depuis 1995, les Carolina Panthers ont disputé deux Super Bowls dans leur histoire moderne.</p>",
    },
    {
        "slug": "new-orleans-saints",
        "title": "New Orleans Saints",
        "espn_id": "18",
        "conference": "NFC",
        "division": "Sud",
        "ville": "La Nouvelle-Orléans, Louisiane",
        "stade_nom": "Caesars Superdome",
        "stade_capacite": 73208,
        "coach_fallback": "Kellen Moore",
        "annee_creation": 1967,
        "super_bowls": "1 (XLIV)",
        "description": "<p>Symboles de résilience à La Nouvelle-Orléans, les Saints ont offert à leur ville un sacre historique au Super Bowl XLIV menés par Drew Brees et Sean Payton.</p>",
    },
    {
        "slug": "tampa-bay-buccaneers",
        "title": "Tampa Bay Buccaneers",
        "espn_id": "27",
        "conference": "NFC",
        "division": "Sud",
        "ville": "Tampa, Floride",
        "stade_nom": "Raymond James Stadium",
        "stade_capacite": 69218,
        "coach_fallback": "Todd Bowles",
        "annee_creation": 1976,
        "super_bowls": "2 (XXXVII, LV)",
        "description": "<p>Première équipe de l'histoire à remporter un Super Bowl dans son propre stade (Super Bowl LV), les Buccaneers sont célèbres pour leur bateau pirate.</p>",
    },
    # --- NFC OUEST ---
    {
        "slug": "arizona-cardinals",
        "title": "Arizona Cardinals",
        "espn_id": "22",
        "conference": "NFC",
        "division": "Ouest",
        "ville": "Glendale, Arizona",
        "stade_nom": "State Farm Stadium",
        "stade_capacite": 63400,
        "coach_fallback": "Jonathan Gannon",
        "annee_creation": 1898,
        "super_bowls": "Aucun (1 participation : XLIII)",
        "description": "<p>Plus ancienne franchise professionnelle encore en activité aux États-Unis (fondée en 1898 à Chicago), les Cardinals évoluent en Arizona depuis 1988.</p>",
    },
    {
        "slug": "los-angeles-rams",
        "title": "Los Angeles Rams",
        "espn_id": "14",
        "conference": "NFC",
        "division": "Ouest",
        "ville": "Inglewood (Los Angeles), Californie",
        "stade_nom": "SoFi Stadium",
        "stade_capacite": 70240,
        "coach_fallback": "Sean McVay",
        "annee_creation": 1936,
        "super_bowls": "2 (XXXIV, LVI)",
        "description": "<p>Des « Greatest Show on Turf » à leur triomphe à domicile au Super Bowl LVI sous Sean McVay, les Los Angeles Rams cultivent un jeu offensif novateur.</p>",
    },
    {
        "slug": "san-francisco-49ers",
        "title": "San Francisco 49ers",
        "espn_id": "25",
        "conference": "NFC",
        "division": "Ouest",
        "ville": "Santa Clara, Californie",
        "stade_nom": "Levi's Stadium",
        "stade_capacite": 68500,
        "coach_fallback": "Kyle Shanahan",
        "annee_creation": 1946,
        "super_bowls": "5 (XVI, XIX, XXIII, XXIV, XXIX)",
        "description": "<p>Franchise mythique de la baie de San Francisco, les 49ers ont révolutionné l'attaque en NFL avec Bill Walsh, Joe Montana, Steve Young et Jerry Rice.</p>",
    },
    {
        "slug": "seattle-seahawks",
        "title": "Seattle Seahawks",
        "espn_id": "26",
        "conference": "NFC",
        "division": "Ouest",
        "ville": "Seattle, Washington",
        "stade_nom": "Lumen Field",
        "stade_capacite": 68740,
        "coach_fallback": "Mike Macdonald",
        "annee_creation": 1976,
        "super_bowls": "1 (XLVIII)",
        "description": "<p>Portés par le vacarme légendaire du « 12th Man » au Lumen Field, les Seattle Seahawks ont marqué la décennie 2010 avec la défense « Legion of Boom ».</p>",
    },
]


class Command(BaseCommand):
    help = "Importe ou met à jour les 32 franchises NFL (infos, logos, stades, staff et joueurs clés) tout en restant éditables dans Wagtail Admin."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Réécrit aussi les joueurs clés et descriptions déjà modifiés dans l'admin.",
        )

    def _get_or_create_wagtail_image(self, title, image_url, filename):
        """Télécharge une image (logo ou portrait) et la sauvegarde dans la médiathèque Wagtail sans doublon."""
        if not image_url:
            return None

        existing = WagtailImage.objects.filter(title=title).first()
        if existing:
            return existing

        try:
            resp = requests.get(image_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            if resp.status_code == 200 and resp.content:
                img = WagtailImage(
                    title=title,
                    file=ContentFile(resp.content, name=filename),
                )
                img.save()
                return img
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  [Image ignorée] {title}: {e}"))
        return None

    def _fetch_espn_team_details(self, espn_id, fallback):
        """Enrichit les données locales avec les infos live de l'API ESPN (stade, capacité, logo, head coach)."""
        headers = {"User-Agent": "Mozilla/5.0"}
        details = {
            "logo_url": "",
            "stade_nom": fallback["stade_nom"],
            "stade_capacite": fallback["stade_capacite"],
            "ville": fallback["ville"],
            "coach": fallback["coach_fallback"],
        }

        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{espn_id}"
            data = requests.get(url, headers=headers, timeout=6).json()
            team = data.get("team", {})

            logos = team.get("logos", [])
            if logos:
                details["logo_url"] = logos[0].get("href", "")

            franchise = team.get("franchise", {})
            venue = franchise.get("venue") or team.get("venue") or {}
            if venue.get("fullName"):
                details["stade_nom"] = venue["fullName"]
            if venue.get("capacity"):
                details["stade_capacite"] = int(venue["capacity"])

            addr = venue.get("address", {})
            if addr.get("city") and addr.get("state"):
                details["ville"] = f"{addr['city']}, {addr['state']}"
        except Exception:
            pass

        # Récupération du Head Coach actuel via l'endpoint /coaches d'ESPN
        try:
            coach_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{espn_id}/coaches"
            cdata = requests.get(coach_url, headers=headers, timeout=5).json()
            for item in cdata.get("items", []):
                role = (item.get("position") or item.get("title") or "").lower()
                first = item.get("firstName", "")
                last = item.get("lastName", "")
                full = f"{first} {last}".strip()
                if full and ("head" in role or not role):
                    details["coach"] = full
                    break
        except Exception:
            pass

        return details

    def _build_key_players(self, team_page, espn_id):
        """Sélectionne automatiquement 4 titulaires majeurs (QB, WR, RB + star défensive) depuis le Depth Chart / Roster ESPN."""
        depth_chart = get_team_depth_chart(espn_id)
        roster = get_team_roster(espn_id)

        # Indexation des joueurs du roster par nom pour récupérer numéro et photo portrait
        roster_lookup = {}
        for section in roster:
            for p in section.get("players", []):
                roster_lookup[p["name"].lower()] = p

        target_positions = ["QB", "WR", "RB", "DE", "EDGE", "LB", "CB", "S", "DT"]
        picked = []
        seen_names = set()

        for target_pos in target_positions:
            if len(picked) >= 4:
                break
            for unit in depth_chart:
                for row in unit.get("rows", []):
                    if row["abbr"].upper() == target_pos and row["slots"] and row["slots"][0]:
                        starter = row["slots"][0]
                        name = starter["name"]
                        if name.lower() not in seen_names:
                            seen_names.add(name.lower())
                            r_info = roster_lookup.get(name.lower(), {})
                            jersey_raw = starter.get("jersey") or r_info.get("jersey")
                            try:
                                jersey_num = int(jersey_raw)
                            except (TypeError, ValueError):
                                jersey_num = None

                            picked.append({
                                "nom": name,
                                "poste": row["abbr"].upper(),
                                "numero": jersey_num,
                                "headshot": r_info.get("headshot", ""),
                                "bio_courte": f"Titulaire ({row['label']})",
                            })
                            break

        # Complément depuis le roster si moins de 4 joueurs trouvés
        if len(picked) < 4:
            for section in roster:
                for p in section.get("players", []):
                    if len(picked) >= 4:
                        break
                    if p["name"].lower() not in seen_names:
                        seen_names.add(p["name"].lower())
                        try:
                            jersey_num = int(p.get("jersey"))
                        except (TypeError, ValueError):
                            jersey_num = None
                        picked.append({
                            "nom": p["name"],
                            "poste": p["position"],
                            "numero": jersey_num,
                            "headshot": p.get("headshot", ""),
                            "bio_courte": f"Joueur cadre ({p['position']})",
                        })

        for idx, kp in enumerate(picked[:4]):
            photo_img = None
            if kp["headshot"]:
                safe_slug = kp["nom"].lower().replace(" ", "-").replace("'", "")
                photo_img = self._get_or_create_wagtail_image(
                    title=f"Portrait {kp['nom']}",
                    image_url=kp["headshot"],
                    filename=f"player-{safe_slug}.png",
                )
            TeamKeyPlayer.objects.create(
                page=team_page,
                sort_order=idx,
                nom=kp["nom"],
                poste=kp["poste"],
                numero=kp["numero"],
                photo=photo_img,
                bio_courte=kp["bio_courte"],
            )

    def handle(self, *args, **options):
        force = options["force"]
        index_page = TeamIndexPage.objects.live().first() or TeamIndexPage.objects.first()

        if not index_page:
            self.stdout.write(
                self.style.ERROR(
                    "Aucune page 'TeamIndexPage' (Équipes) trouvée dans Wagtail. Crée d'abord la rubrique Équipes dans l'admin."
                )
            )
            return

        created_count = 0
        updated_count = 0

        for item in NFL_TEAMS_DATA:
            slug = item["slug"]
            title = item["title"]
            espn_id = item["espn_id"]

            self.stdout.write(f"Traitement de {title}...")
            details = self._fetch_espn_team_details(espn_id, item)

            logo_img = self._get_or_create_wagtail_image(
                title=f"Logo {title}",
                image_url=details["logo_url"],
                filename=f"{slug}-logo.png",
            )

            existing_page = TeamPage.objects.filter(slug=slug).first()

            if existing_page:
                team_page = existing_page
                team_page.title = title
                team_page.conference = item["conference"]
                team_page.division = item["division"]
                if logo_img and (not team_page.logo or force):
                    team_page.logo = logo_img
                team_page.ville = details["ville"]
                team_page.stade_nom = details["stade_nom"]
                team_page.stade_capacite = details["stade_capacite"]
                team_page.entraineur_principal = details["coach"]
                team_page.annee_creation = item["annee_creation"]
                team_page.super_bowls = item["super_bowls"]
                if not team_page.description or force:
                    team_page.description = item["description"]
                if not team_page.nfl_official_url:
                    team_page.nfl_official_url = f"https://www.nfl.com/teams/{slug}/"

                revision = team_page.save_revision()
                revision.publish()
                updated_count += 1
            else:
                team_page = TeamPage(
                    title=title,
                    slug=slug,
                    conference=item["conference"],
                    division=item["division"],
                    logo=logo_img,
                    ville=details["ville"],
                    stade_nom=details["stade_nom"],
                    stade_capacite=details["stade_capacite"],
                    entraineur_principal=details["coach"],
                    annee_creation=item["annee_creation"],
                    super_bowls=item["super_bowls"],
                    description=item["description"],
                    nfl_official_url=f"https://www.nfl.com/teams/{slug}/",
                )
                index_page.add_child(instance=team_page)
                revision = team_page.save_revision()
                revision.publish()
                created_count += 1

            # Import des joueurs clés uniquement s'il n'y en a pas encore (ou si --force)
            if force:
                team_page.key_players.all().delete()
            if not team_page.key_players.exists():
                self._build_key_players(team_page, espn_id)
                revision = team_page.save_revision()
                revision.publish()

            time.sleep(0.2)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImport terminé : {created_count} équipe(s) créée(s), {updated_count} mise(s) à jour."
            )
        )