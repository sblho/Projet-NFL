import time
import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from wagtail.images.models import Image as WagtailImage

from pages.models import ArticleIndexPage, ArticlePage

NFL_HISTORY_ARTICLES = [
    # ==================== 1. HISTOIRE DE LA NFL ====================
    {
        "slug": "1920-naissance-de-la-nfl-a-canton",
        "title": "1920 : La naissance de la NFL dans une concession automobile à Canton",
        "categorie": "histoire",
        "chapeau": "Le 17 septembre 1920, onze dirigeants de clubs se réunissent à Canton (Ohio) pour structurer le football américain professionnel et fonder la future NFL.",
        "body": (
            "<p>Au sortir de la Première Guerre mondiale, le football américain professionnel souffre d'un manque total d'organisation : "
            "les salaires flambent, les joueurs changent d'équipe d'un dimanche à l'autre et les matchs universitaires attirent encore bien davantage les foules.</p>"
            "<h3>La réunion fondatrice du 17 septembre 1920</h3>"
            "<p>Pour assainir la discipline, les représentants de onze équipes se retrouvent le <strong>17 septembre 1920</strong> dans la concession "
            "automobile Hupmobile de Ralph Hay à <strong>Canton, dans l'Ohio</strong>. Ils fondent l'<em>American Professional Football Association (APFA)</em> "
            "et nomment l'immense champion olympique <strong>Jim Thorpe</strong> premier président de la ligue.</p>"
            "<h3>De l'APFA à la National Football League</h3>"
            "<p>Deux ans plus tard, en <strong>1922</strong>, l'organisation adopte son nom définitif : la <strong>National Football League (NFL)</strong>. "
            "Parmi les membres pionniers de cette époque fondatrice, seules deux franchises existent toujours aujourd'hui : les <strong>Chicago Bears</strong> "
            "(alors appelés Decatur Staleys) et les <strong>Arizona Cardinals</strong> (alors Chicago Cardinals).</p>"
        ),
    },
    {
        "slug": "fusion-afl-nfl-et-creation-du-super-bowl",
        "title": "La fusion AFL-NFL (1966-1970) et la naissance du Super Bowl",
        "categorie": "histoire",
        "chapeau": "Dans les années 1960, la rivalité entre la NFL historique et la jeune AFL donne naissance au Super Bowl et à l'architecture moderne à deux conférences.",
        "body": (
            "<p>En 1960, l'homme d'affaires texan Lamar Hunt lance l'<strong>American Football League (AFL)</strong> avec une philosophie résolument moderne : "
            "un jeu aérien spectaculaire, des maillots colorés et des contrats télévisés novateurs. Très vite, la concurrence fait exploser les salaires des jeunes talents issus de la Draft.</p>"
            "<h3>L'accord historique de juin 1966</h3>"
            "<p>Plutôt que de s'épuiser financièrement, les deux ligues annoncent leur fusion le <strong>8 juin 1966</strong>. L'accord prévoit dès janvier 1967 "
            "une grande finale opposant le champion de la NFL à celui de l'AFL : le <strong>Super Bowl</strong> est né.</p>"
            "<h3>Le tournant du Super Bowl III et les conférences AFC / NFC</h3>"
            "<p>Après deux premiers sacres des Green Bay Packers de Vince Lombardi, les <strong>New York Jets</strong> de Joe Namath créent un séisme en 1969 "
            "en battant les Baltimore Colts (16-7) lors du Super Bowl III, prouvant la valeur de l'AFL. En <strong>1970</strong>, la fusion devient totale avec la création "
            "des deux conférences actuelles : l'<strong>AFC</strong> et la <strong>NFC</strong>.</p>"
        ),
    },
    {
        "slug": "evolution-tactique-nfl-west-coast-offense",
        "title": "La révolution tactique : comment la West Coast Offense a transformé la NFL",
        "categorie": "histoire",
        "chapeau": "Imaginée par Bill Walsh dans les années 1970 et 1980, la West Coast Offense a remplacé le jeu de course traditionnel par des passes courtes ultra-rythmées.",
        "body": (
            "<p>Jusqu'à la fin des années 1970, la majorité des attaques NFL reposaient sur un schéma classique : courir lors des deux premières tentatives "
            "et tenter une longue passe verticale sur troisième tentative.</p>"
            "<h3>L'intuition géniale de Bill Walsh</h3>"
            "<p>Entraîneur des <strong>San Francisco 49ers</strong> à partir de 1979, <strong>Bill Walsh</strong> renverse cette logique. "
            "Il utilise des passes courtes, rapides et millimétrées dans les espaces libres pour étirer horizontalement les défenses adverses et ouvrir ensuite le jeu au sol.</p>"
            "<h3>Un héritage toujours présent aujourd'hui</h3>"
            "<p>Exécutée à la perfection par Joe Montana et Jerry Rice, cette philosophie offre trois Super Bowls aux 49ers dans les années 1980. "
            "Son arbre d'entraîneurs — de Mike Holmgren à Andy Reid en passant par Kyle Shanahan et Sean McVay — continue aujourd'hui de façonner la NFL moderne.</p>"
        ),
    },
    {
        "slug": "ere-moderne-salary-cap-et-expansion-internationale",
        "title": "1994 à nos jours : le Salary Cap, 32 franchises et la conquête mondiale",
        "categorie": "histoire",
        "chapeau": "Grâce au plafond salarial instauré en 1994 et au réalignement à 32 franchises en 2002, la NFL s'est imposée comme la ligue la plus compétitive du sport mondial.",
        "body": (
            "<p>L'année <strong>1994</strong> marque l'entrée de la NFL dans son ère économique moderne avec l'instauration conjointe de la <em>Free Agency</em> "
            "et du <strong>plafond salarial (Salary Cap)</strong>. Ce mécanisme garantit une parité unique : aucune franchise ne peut acheter tous les meilleurs joueurs, "
            "permettant à une équipe en difficulté de jouer le titre deux ans plus tard.</p>"
            "<h3>Le format à 32 franchises et 17 matchs</h3>"
            "<p>Avec l'arrivée des Houston Texans en <strong>2002</strong>, la ligue atteint son équilibre parfait : <strong>32 franchises</strong> réparties en 8 divisions de 4 équipes. "
            "En 2021, le calendrier régulier passe de 16 à 17 matchs par équipe.</p>"
            "<h3>Une ligue désormais planétaire</h3>"
            "<p>Longtemps centrée uniquement sur l'Amérique du Nord, la NFL multiplie désormais les rencontres délocalisées à Londres, Munich, Francfort, São Paulo, Madrid et Paris, "
            "faisant du Super Bowl l'événement sportif annuel le plus suivi de la planète.</p>"
        ),
    },

    # ==================== 2. LÉGENDES ET JOUEURS ====================
    {
        "slug": "joe-montana-legende-49ers",
        "title": "Joe Montana : « Joe Cool », l'architecte de la dynastie des 49ers",
        "categorie": "legendes",
        "chapeau": "Quadruple vainqueur du Super Bowl sans jamais lancer la moindre interception en finale, Joe Montana a incarné le sang-froid absolu au poste de quarterback.",
        "body": (
            "<p>Surnommé <strong>« Joe Cool »</strong> pour sa sérénité imperturbable dans les moments les plus brûlants, <strong>Joe Montana</strong> "
            "a mené les San Francisco 49ers à quatre titres du Super Bowl entre 1981 et 1989 (XVI, XIX, XXIII, XXIV).</p>"
            "<h3>Un bilan parfait au Super Bowl</h3>"
            "<ul>"
            "<li><strong>4 Super Bowls remportés</strong> en 4 participations avec San Francisco.</li>"
            "<li><strong>3 fois élu MVP du Super Bowl</strong> (XVI, XIX, XXIV).</li>"
            "<li><strong>11 touchdowns pour 0 interception</strong> cumulés lors de ses quatre finales.</li>"
            "<li>Intronisé au <strong>Pro Football Hall of Fame</strong> en 2000.</li>"
            "</ul>"
            "<p>Son drive légendaire de 92 yards dans les trois dernières minutes du Super Bowl XXIII face aux Cincinnati Bengals reste l'un des chefs-d'œuvre absolus du poste de quarterback.</p>"
        ),
    },
    {
        "slug": "jerry-rice-plus-grand-receveur-histoire",
        "title": "Jerry Rice : les records inaccessibles du plus grand receveur de tous les temps",
        "categorie": "legendes",
        "chapeau": "Doté d'une éthique de travail légendaire, Jerry Rice détient presque tous les records majeurs à la réception de l'histoire de la NFL.",
        "body": (
            "<p>Sélectionné en 1985 par Bill Walsh, <strong>Jerry Rice</strong> a redéfini l'exigence physique et technique du poste de Wide Receiver "
            "pendant vingt saisons au plus haut niveau.</p>"
            "<h3>Un livre de records à lui seul</h3>"
            "<ul>"
            "<li><strong>1 549 réceptions</strong> en carrière (record NFL).</li>"
            "<li><strong>22 895 yards à la réception</strong> (près de 5 400 yards d'avance sur le deuxième de l'histoire).</li>"
            "<li><strong>208 touchdowns totaux</strong> inscrits en saison régulière.</li>"
            "<li><strong>3 Super Bowls remportés</strong> avec les 49ers et MVP du Super Bowl XXIII (215 yards).</li>"
            "</ul>"
        ),
    },
    {
        "slug": "lawrence-taylor-revolution-defensive",
        "title": "Lawrence Taylor : le défenseur qui a forcé la NFL à réinventer son attaque",
        "categorie": "legendes",
        "chapeau": "Élu MVP de la NFL en 1986 — un exploit rarissime pour un joueur défensif — Lawrence Taylor a terrorisé les quarterbacks pendant treize saisons avec les Giants.",
        "body": (
            "<p>Avant l'arrivée de <strong>Lawrence Taylor</strong> chez les New York Giants en 1981, les linebackers extérieurs se contentaient surtout de défendre contre la course. "
            "« LT » a transformé le poste en une arme de destruction massive contre la passe.</p>"
            "<h3>Un impact historique sur le jeu</h3>"
            "<ul>"
            "<li><strong>MVP de la NFL en 1986</strong> (dernier défenseur à avoir remporté ce trophée).</li>"
            "<li><strong>3 fois Joueur Défensif de l'Année</strong> (1981, 1982, 1986).</li>"
            "<li><strong>2 Super Bowls remportés</strong> avec les New York Giants (XXI et XXV).</li>"
            "<li><strong>142 sacks</strong> en carrière (dont 20,5 lors de sa saison MVP en 1986).</li>"
            "</ul>"
            "<p>Sa vitesse et sa puissance ont contraint toutes les franchises NFL à surpayer et spécialiser le poste de <em>Left Tackle</em> pour protéger l'angle mort des quarterbacks.</p>"
        ),
    },
    {
        "slug": "barry-sanders-magicien-detroit-lions",
        "title": "Barry Sanders : le magicien des appuis des Detroit Lions",
        "categorie": "legendes",
        "chapeau": "Capable de faire manquer plusieurs défenseurs dans un mouchoir de poche, Barry Sanders a électrisé la NFL pendant dix saisons avant de se retirer au sommet.",
        "body": (
            "<p>Peu de joueurs dans l'histoire du sport ont procuré autant d'émotions à chaque ballon touché que <strong>Barry Sanders</strong>. "
            "Doté d'un centre de gravité ultra-bas et de changements de direction fulgurants, le running back des Detroit Lions rendait impuissantes les meilleures défenses.</p>"
            "<h3>Dix saisons de magie pure</h3>"
            "<ul>"
            "<li><strong>15 269 yards à la course</strong> en seulement 10 saisons (moyenne exceptionnelle de 5,0 yards par portée).</li>"
            "<li><strong>MVP de la NFL en 1997</strong> après une saison à <strong>2 053 yards au sol</strong>.</li>"
            "<li><strong>10 sélections au Pro Bowl</strong> en 10 saisons disputées.</li>"
            "<li>Intronisé au Pro Football Hall of Fame en 2004.</li>"
            "</ul>"
        ),
    },
    {
        "slug": "peyton-manning-le-sheriff-nfl",
        "title": "Peyton Manning : « Le Shérif », maître tacticien de la ligne d'engagement",
        "categorie": "legendes",
        "chapeau": "Premier quarterback titulaire à remporter le Super Bowl avec deux franchises différentes, Peyton Manning a porté la lecture pré-snap au rang d'art.",
        "body": (
            "<p>Célèbre pour ses ajustements incessants sur la ligne d'engagement ponctués de son mythique cri <em>« Omaha ! »</em>, "
            "<strong>Peyton Manning</strong> a dominé la NFL pendant dix-huit saisons sous les couleurs des Indianapolis Colts puis des Denver Broncos.</p>"
            "<h3>Un palmarès individuel unique</h3>"
            "<ul>"
            "<li><strong>5 fois élu MVP de la NFL</strong> (record absolu de la ligue).</li>"
            "<li><strong>2 Super Bowls remportés</strong> : Super Bowl XLI avec Indianapolis (MVP) et Super Bowl 50 avec Denver.</li>"
            "<li><strong>71 940 yards à la passe</strong> et <strong>539 touchdowns</strong> en carrière (dont 55 touchdowns sur la seule saison 2013).</li>"
            "</ul>"
        ),
    },
    {
        "slug": "drew-brees-legende-new-orleans-hall-of-fame",
        "title": "Drew Brees : le héros de La Nouvelle-Orléans consacré au Hall of Fame",
        "categorie": "legendes",
        "espn_headshot_id": "2580",
        "chapeau": "Arrivé à La Nouvelle-Orléans au lendemain de l'ouragan Katrina, Drew Brees a offert aux Saints leur premier Super Bowl et rejoint le Hall of Fame en 2026.",
        "body": (
            "<p>En 2006, alors que plusieurs équipes doutent de sa capacité à retrouver son bras après une grave blessure à l'épaule, "
            "<strong>Drew Brees</strong> signe aux New Orleans Saints et lie à jamais son destin à une ville en pleine reconstruction.</p>"
            "<h3>La précision incarnée</h3>"
            "<ul>"
            "<li><strong>Vainqueur et MVP du Super Bowl XLIV</strong> en février 2010 face aux Colts.</li>"
            "<li><strong>80 358 yards à la passe</strong> et <strong>571 touchdowns</strong> en carrière.</li>"
            "<li><strong>5 saisons à plus de 5 000 yards</strong> (record NFL) et 67,7 % de passes complétées en carrière.</li>"
            "<li>Intronisé au <strong>Pro Football Hall of Fame</strong> dès sa première année d'éligibilité (Classe 2026).</li>"
            "</ul>"
        ),
    },
    {
        "slug": "tom-brady-sept-super-bowls-goat",
        "title": "Tom Brady : du 199e choix de Draft aux sept bagues du Super Bowl",
        "categorie": "legendes",
        "espn_headshot_id": "2330",
        "chapeau": "Ignoré par toutes les franchises pendant six tours lors de la Draft 2000, Tom Brady s'est forgé le plus grand palmarès de l'histoire de la NFL.",
        "body": (
            "<p>L'histoire de <strong>Tom Brady</strong> est le plus grand conte de fées compétitif du sport moderne. Choisi au <strong>199e rang</strong> "
            "en 2000, quatrième quarterback dans la hiérarchie des New England Patriots à ses débuts, il saisit sa chance en 2001 et bâtit avec Bill Belichick "
            "une dynastie sans équivalent sur vingt ans.</p>"
            "<h3>Les chiffres d'une carrière hors norme</h3>"
            "<ul>"
            "<li><strong>7 Super Bowls remportés</strong> : 6 avec New England et 1 avec les Tampa Bay Buccaneers (Super Bowl LV).</li>"
            "<li><strong>5 trophées de MVP du Super Bowl</strong> (record absolu).</li>"
            "<li><strong>3 fois MVP de la saison régulière</strong> (2007, 2010, 2017).</li>"
            "<li>Recordman NFL des yards à la passe (<strong>89 214</strong>) et des touchdowns (<strong>649</strong>).</li>"
            "</ul>"
        ),
    },

    # ==================== 3. GRANDS MOMENTS ====================
    {
        "slug": "immaculate-reception-1972-steelers-raiders",
        "title": "1972 : « The Immaculate Reception », l'action qui a lancé la dynastie des Steelers",
        "categorie": "moments",
        "chapeau": "Le 23 décembre 1972, à 22 secondes de la fin, Franco Harris attrape au ras de la pelouse une passe déviée et offre aux Steelers la première victoire en Playoffs de leur histoire.",
        "body": (
            "<p>Pendant près de quarante ans, les Pittsburgh Steelers n'avaient jamais remporté le moindre match de Playoffs. Tout bascule le <strong>23 décembre 1972</strong> "
            "face aux Oakland Raiders.</p>"
            "<h3>22 secondes pour entrer dans la légende</h3>"
            "<p>Menés 7-6 sur une 4e tentative et 10 yards à parcourir depuis leurs propres 40 yards, les Steelers jouent leur dernière carte. "
            "Sous pression, Terry Bradshaw lance vers John Fuqua : le ballon percute le défenseur Jack Tatum et rebondit vers l'arrière. "
            "Surgissant de nulle part, le rookie <strong>Franco Harris</strong> capte le ballon à quelques centimètres du sol et file sur 60 yards inscrire le touchdown de la victoire (13-7).</p>"
            "<p>Élue <strong>« Plus grande action des 100 ans de la NFL »</strong>, cette action marque le début de la grande dynastie de Pittsburgh (4 Super Bowls entre 1974 et 1979).</p>"
        ),
    },
    {
        "slug": "the-catch-1982-joe-montana-dwight-clark",
        "title": "1982 : « The Catch », le saut miraculeux de Dwight Clark sur une passe de Joe Montana",
        "categorie": "moments",
        "chapeau": "Le 10 janvier 1982, acculé vers la ligne de touche en finale de conférence NFC, Joe Montana adresse une passe haute captée du bout des doigts par Dwight Clark.",
        "body": (
            "<p>En finale de conférence NFC le <strong>10 janvier 1982</strong>, les San Francisco 49ers affrontent les Dallas Cowboys, "
            "géants incontestés de la décennie précédente. Menés 27-21 à moins de cinq minutes du terme, les 49ers entament une remontée de 89 yards.</p>"
            "<h3>Un geste gravé dans l'éternité</h3>"
            "<p>À 58 secondes de la fin, sur une 3e tentative à 6 yards de l'en-but, <strong>Joe Montana</strong> est poursuivi par trois défenseurs vers la droite du terrain. "
            "En déséquilibre, il lance le ballon très haut au fond de la end zone : <strong>Dwight Clark</strong> s'élève dans les airs et capte la passe du bout des doigts "
            "pour égaliser avant la transformation victorieuse (28-27). San Francisco décroche deux semaines plus tard le premier Super Bowl de son histoire.</p>"
        ),
    },
    {
        "slug": "helmet-catch-2008-giants-patriots-super-bowl-xlii",
        "title": "2008 : « The Helmet Catch », quand les Giants ont brisé la saison parfaite des Patriots",
        "categorie": "moments",
        "chapeau": "Invaincus depuis 18 matchs, les New England Patriots pensaient toucher à la perfection au Super Bowl XLII avant la réception irréelle de David Tyree contre son casque.",
        "body": (
            "<p>Le <strong>3 février 2008</strong>, les New England Patriots de Tom Brady et Randy Moss se présentent au Super Bowl XLII avec un bilan immaculé de <strong>18 victoires et 0 défaite</strong>, "
            "à un match de devenir la première équipe de l'histoire à boucler une saison à 19-0.</p>"
            "<h3>L'action la plus improbable de l'histoire du Super Bowl</h3>"
            "<p>Menés 14-10 dans les deux dernières minutes, les <strong>New York Giants</strong> jouent une 3e tentative et 5 yards. Agrippé par le maillot par plusieurs défenseurs "
            "et sur le point d'être plaqué, <strong>Eli Manning</strong> s'extirpe miraculeusement de la poche et lance plein axe : le receveur remplaçant <strong>David Tyree</strong> "
            "saute et plaque le ballon d'une main contre son casque tout en chutant sous le plaquage de Rodney Harrison. Quelques actions plus tard, Plaxico Burress inscrit le touchdown de la victoire (17-14).</p>"
        ),
    },
    {
        "slug": "remontee-28-3-patriots-falcons-super-bowl-li",
        "title": "2017 : La remontée historique 28-3 des Patriots au Super Bowl LI",
        "categorie": "moments",
        "chapeau": "Menés de 25 points à la fin du troisième quart-temps face aux Atlanta Falcons, les New England Patriots réalisent le plus grand comeback de l'histoire du Super Bowl.",
        "body": (
            "<p>Jusqu'au <strong>5 février 2017</strong>, aucune équipe n'avait jamais remonté plus de 10 points de retard lors d'un Super Bowl. "
            "À Houston, les Atlanta Falcons de Matt Ryan dominent totalement la rencontre et mènent <strong>28-3</strong> à moins de 18 minutes de la fin.</p>"
            "<h3>31 points sans réponse et une première prolongation</h3>"
            "<p>Portés par Tom Brady, une réception acrobatique insensée de Julian Edelman au ras du sol et un sack décisif de Dont'a Hightower, "
            "les Patriots inscrivent 25 points consécutifs — dont deux conversions à deux points — pour égaliser à 28-28. En prolongation, "
            "James White franchit la ligne d'en-but et offre à New England un cinquième titre légendaire (34-28).</p>"
        ),
    },
    {
        "slug": "super-bowl-lx-2026-revanche-seattle-seahawks",
        "title": "2026 : Super Bowl LX, la revanche défensive des Seattle Seahawks face aux Patriots",
        "categorie": "moments",
        "chapeau": "Onze ans après la désillusion du Super Bowl XLIX, les Seattle Seahawks étouffent New England (29-13) au Levi's Stadium et décrochent le deuxième titre de leur histoire.",
        "body": (
            "<p>Le <strong>8 février 2026</strong> à Santa Clara, l'affiche du <strong>Super Bowl LX</strong> ravive immédiatement les souvenirs de 2015 : "
            "les <strong>Seattle Seahawks</strong> retrouvent les <strong>New England Patriots</strong> onze ans après l'interception cruelle de Malcolm Butler sur la ligne d'en-but.</p>"
            "<h3>Une démonstration de maîtrise collective</h3>"
            "<p>Sous l'impulsion de l'entraîneur Mike Macdonald, la défense de Seattle verrouille complètement l'attaque adverse pendant trois quart-temps, "
            "tandis que le running back <strong>Kenneth Walker III</strong> multiplie les courses décisives pour décrocher le trophée de <strong>MVP du Super Bowl LX</strong>. "
            "Victorieux <strong>29-13</strong>, les Seahawks soulèvent le deuxième trophée Vince Lombardi de leur histoire.</p>"
        ),
    },
]


class Command(BaseCommand):
    help = "Importe en français l'Histoire de la NFL, les Légendes & joueurs et les Grands moments dans ArticleIndexPage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Met à jour les articles déjà existants (y compris ceux modifiés dans l'admin).",
        )

    def _get_or_create_portrait(self, title, espn_id):
        if not espn_id:
            return None

        img_title = f"Portrait {title[:60]}"
        existing = WagtailImage.objects.filter(title=img_title).first()
        if existing:
            return existing

        url = f"https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png"
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            if resp.status_code == 200 and resp.content:
                img = WagtailImage(
                    title=img_title,
                    file=ContentFile(resp.content, name=f"legend-{espn_id}.png"),
                )
                img.save()
                return img
        except Exception:
            pass
        return None

    def handle(self, *args, **options):
        force = options["force"]
        index_page = ArticleIndexPage.objects.live().first() or ArticleIndexPage.objects.first()

        if not index_page:
            self.stdout.write(
                self.style.ERROR(
                    "Aucune page 'ArticleIndexPage' (Histoire) trouvée dans Wagtail. Vérifie qu'elle existe et est publiée."
                )
            )
            return

        created_count = 0
        updated_count = 0

        for item in NFL_HISTORY_ARTICLES:
            slug = item["slug"]
            existing = ArticlePage.objects.filter(slug=slug).first()
            cover_img = self._get_or_create_portrait(item["title"], item.get("espn_headshot_id"))

            if existing:
                if force:
                    existing.title = item["title"]
                    existing.categorie = item["categorie"]
                    existing.chapeau = item["chapeau"]
                    existing.body = item["body"]
                    if cover_img and not existing.image_couverture:
                        existing.image_couverture = cover_img
                    rev = existing.save_revision()
                    rev.publish()
                    updated_count += 1
                    self.stdout.write(f"Mis à jour : {item['title']}")
                else:
                    self.stdout.write(f"Ignoré (déjà présent) : {item['title']}")
                continue

            article = ArticlePage(
                title=item["title"],
                slug=slug,
                categorie=item["categorie"],
                chapeau=item["chapeau"],
                image_couverture=cover_img,
                body=item["body"],
            )
            index_page.add_child(instance=article)
            rev = article.save_revision()
            rev.publish()
            created_count += 1
            self.stdout.write(f"Créé : {item['title']}")

            # Pause courte pour garantir un ordre chronologique propre sur first_published_at
            time.sleep(0.05)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImport Histoire terminé : {created_count} article(s) créé(s), {updated_count} mis à jour."
            )
        )