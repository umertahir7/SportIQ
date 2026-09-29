import os
import re

import requests
from dotenv import load_dotenv


load_dotenv()


class NewsService:

    def __init__(self):

        self.api_key = os.getenv("NEWS_API_KEY")
        self.base_url = "https://newsapi.org/v2"

        if not self.api_key:
            raise ValueError(
                "NEWS_API_KEY not found in .env file"
            )

        # ======================================================
        # IMPORTANT PLAYERS
        # ======================================================

        self.team_players = {

            "real madrid": [
                "kylian mbappe",
                "mbappe",
                "vinicius junior",
                "vinicius",
                "vini jr",
                "rodrygo",
                "brahim diaz",
                "brahim",
                "endrick",
                "carlos espi",
                "carlos espí",
                "espi",
                "espí",
                "yan diomande",
                "diomande",
                "jude bellingham",
                "bellingham",
                "fede valverde",
                "valverde",
                "eduardo camavinga",
                "camavinga",
                "aurelien tchouameni",
                "tchouameni",
                "arda guler",
                "arda güler",
                "guler",
                "bernardo silva",
                "bernardo",
                "thiago",
                "thibaut courtois",
                "courtois",
                "lunin",
                "antonio rudiger",
                "rüdiger",
                "rudiger",
                "eder militao",
                "militao",
                "dean huijsen",
                "huijsen",
                "trent alexander arnold",
                "alexander arnold",
                "trent",
                "ibrahima konate",
                "ibrahima konaté",
                "konate",
                "ferland mendy",
                "mendy",
                "asencio",
                "alvaro carreras",
                "carreras",
                "cucurella",
                "dumfries",
            ],

            "chelsea": [
                "cole palmer",
                "palmer",
                "joao pedro",
                "joão pedro",
                "danny welbeck",
                "welbeck",
                "emmanuel emegha",
                "emegha",
                "estevao",
                "estevao willian",
                "estêvão",
                "jamie gittens",
                "gittens",
                "morgan rogers",
                "pedro neto",
                "moises caicedo",
                "caicedo",
                "enzo fernandez",
                "enzo",
                "romeo lavia",
                "lavia",
                "jordan henderson",
                "henderson",
                "dario essugo",
                "essugo",
                "geovany quenda",
                "reece james",
                "levi colwill",
                "colwill",
                "wesley fofana",
                "fofana",
                "maxence lacroix",
                "lacroix",
                "jorrel hato",
                "hato",
                "marco palestra",
                "palestra",
                "valentin barco",
                "barco",
                "pep chavarria",
                "pep chavarri",
                "tosin adarabioyo",
                "tosin",
                "josh acheampong",
                "acheampong",
                "emiliano martinez",
                "emi martinez",
                "robert sanchez",
                "filip jorgensen",
                "jorgensen",
                "mike penders",
                "penders",
            ],

            "al-nassr": [
                "cristiano ronaldo",
                "ronaldo",
                "sadio mane",
                "sadio mané",
                "joao felix",
                "joão felix",
                "angelo gabriel",
                "angelo",
                "kingsley coman",
                "coman",
                "ayman yahya",
                "abdullah al-hamdan",
                "al-hamdan",
                "mohammed maran",
                "samu costa",
                "samú costa",
                "sami al-naji",
                "abdullah al-khaibari",
                "al-khaibari",
                "ali al-hassan",
                "hayder abdulkareem",
                "rakan al-ghamdi",
                "al-ghamdi",
                "inigo martinez",
                "iñigo martinez",
                "iñigo martínez",
                "mohamed simakan",
                "simakan",
                "sultan al-ghannam",
                "al-ghannam",
                "nader al-sharari",
                "al-sharari",
                "abdulelah al-amri",
                "al-amri",
                "saad al-nasser",
                "al-nasser",
                "nawaf boushal",
                "boushal",
                "salem al-najdi",
                "al-najdi",
                "nawaf bu washl",
                "bento",
                "nawaf al-aqidi",
                "al-aqidi",
            ],
        }

        # ======================================================
        # TEAM ALIASES
        # ======================================================

        self.team_aliases = {

            "real madrid": [
                "real madrid",
                "real madrid cf",
            ],

            "chelsea": [
                "chelsea",
                "chelsea fc",
                "chelsea football club",
            ],

            "al-nassr": [
                "al-nassr",
                "al nassr",
                "alnassr",
            ],
        }

        # ======================================================
        # OTHER MAJOR FOOTBALL TEAMS
        # ======================================================

        self.major_team_aliases = {

            "arsenal": [
                "arsenal",
                "arsenal fc",
            ],

            "manchester united": [
                "manchester united",
                "man utd",
                "man united",
            ],

            "manchester city": [
                "manchester city",
                "man city",
            ],

            "liverpool": [
                "liverpool",
                "liverpool fc",
            ],

            "tottenham": [
                "tottenham",
                "tottenham hotspur",
                "spurs",
            ],

            "barcelona": [
                "barcelona",
                "fc barcelona",
            ],

            "atletico madrid": [
                "atletico madrid",
                "atletico",
            ],

            "bayern munich": [
                "bayern munich",
                "bayern",
            ],

            "borussia dortmund": [
                "borussia dortmund",
                "dortmund",
            ],

            "juventus": [
                "juventus",
            ],

            "inter milan": [
                "inter milan",
                "inter",
            ],

            "ac milan": [
                "ac milan",
                "milan",
            ],

            "paris saint-germain": [
                "paris saint germain",
                "psg",
            ],

            "al-hilal": [
                "al-hilal",
                "al hilal",
            ],

            "al-ittihad": [
                "al-ittihad",
                "al ittihad",
            ],

            "al-ahli": [
                "al-ahli",
                "al ahli",
            ],
        }

        # ======================================================
        # FOOTBALL CONTEXT
        # ======================================================

        self.football_context_terms = [

            "football",
            "soccer",
            "footballer",
            "football club",
            "soccer club",
            "football team",
            "soccer team",

            "match",
            "fixture",
            "fixtures",
            "goal",
            "goals",
            "scored",
            "scoring",

            "striker",
            "midfielder",
            "defender",
            "goalkeeper",

            "manager",
            "coach",
            "captain",
            "squad",
            "lineup",
            "starting eleven",
            "starting xi",

            "transfer",
            "transfers",
            "loan",
            "signing",
            "signed",
            "contract",
            "renewal",

            "season",
            "league",
            "cup",
            "tournament",

            "champions league",
            "europa league",
            "conference league",

            "premier league",
            "la liga",
            "laliga",
            "bundesliga",
            "serie a",
            "ligue 1",
            "saudi pro league",

            "red card",
            "yellow card",
            "penalty",
            "assist",

            "kickoff",
            "kick-off",
            "half-time",
            "full-time",
            "extra time",
            "penalty shootout",

            "injury",
            "injured",
            "fitness",
            "sidelined",

            "football news",
            "soccer news",
            "transfer news",
            "transfer window",

            "sporting director",
            "head coach",
            "first team",
            "academy",
        ]

        # ======================================================
        # MATCH / COMPETITION SIGNALS
        # ======================================================

        self.match_signals = [
            " vs ",
            " v ",
            " win ",
            " wins ",
            " won ",
            " defeat ",
            " defeats ",
            " defeated ",
            " beat ",
            " beats ",
            " draw ",
            " draws ",
            " drew ",
            " lose ",
            " loses ",
            " lost ",
            " player ratings",
            "match report",
            "match preview",
            "fixture",
            "fixtures",
            "game",
            "match",
            "score",
            "scores",
            "scored",
            "goal",
            "goals",
        ]

        # ======================================================
        # TRANSFER / CLUB NEWS SIGNALS
        # ======================================================

        self.club_news_signals = [
            "transfer",
            "transfers",
            "signing",
            "signed",
            "joins",
            "joined",
            "join",
            "interested",
            "interest",
            "bid",
            "offer",
            "contract",
            "renew",
            "renewal",
            "extends",
            "extension",
            "loan",
            "manager",
            "coach",
            "head coach",
            "squad",
            "lineup",
            "injury",
            "injured",
            "fitness",
            "sidelined",
            "training",
            "club",
        ]

    # ==========================================================
    # NORMALIZE TEXT
    # ==========================================================

    def normalize_text(self, text):

        if not text:
            return ""

        text = str(text).lower()

        text = (
            text
            .replace("-", " ")
            .replace("–", " ")
            .replace("—", " ")
            .replace("’", "'")
            .replace("‘", "'")
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()

    # ==========================================================
    # GET TEAM KEY
    # ==========================================================

    def get_team_key(self, team_name):

        normalized = self.normalize_text(
            team_name
        )

        if normalized in [
            "real madrid",
            "real madrid cf",
        ]:
            return "real madrid"

        if normalized in [
            "chelsea",
            "chelsea fc",
            "chelsea football club",
        ]:
            return "chelsea"

        if normalized in [
            "al nassr",
            "al-nassr",
            "alnassr",
        ]:
            return "al-nassr"

        return normalized

    # ==========================================================
    # GET TEAM ALIASES
    # ==========================================================

    def get_team_aliases(self, team_name):

        team_key = self.get_team_key(
            team_name
        )

        return self.team_aliases.get(
            team_key,
            [team_key]
        )

    # ==========================================================
    # GET PLAYERS
    # ==========================================================

    def get_players(self, team_name):

        team_key = self.get_team_key(
            team_name
        )

        return self.team_players.get(
            team_key,
            []
        )

    # ==========================================================
    # TERM MATCHING
    # ==========================================================

    def contains_any(self, text, terms):

        normalized_text = self.normalize_text(
            text
        )

        for term in terms:

            normalized_term = self.normalize_text(
                term
            )

            if not normalized_term:
                continue

            pattern = (
                r"\b"
                + re.escape(normalized_term)
                + r"\b"
            )

            if re.search(
                pattern,
                normalized_text
            ):
                return True

        return False

    # ==========================================================
    # COUNT MATCHES
    # ==========================================================

    def count_matches(self, text, terms):

        normalized_text = self.normalize_text(
            text
        )

        count = 0

        for term in terms:

            normalized_term = self.normalize_text(
                term
            )

            if not normalized_term:
                continue

            pattern = (
                r"\b"
                + re.escape(normalized_term)
                + r"\b"
            )

            if re.search(
                pattern,
                normalized_text
            ):
                count += 1

        return count

    # ==========================================================
    # FOOTBALL CONTEXT SCORE
    # ==========================================================

    def get_football_context_score(
        self,
        article
    ):

        title = article.get(
            "title"
        ) or ""

        description = article.get(
            "description"
        ) or ""

        content = article.get(
            "content"
        ) or ""

        text = (
            f"{title} "
            f"{description} "
            f"{content}"
        )

        matches = self.count_matches(
            text,
            self.football_context_terms
        )

        if matches >= 5:
            return 5

        if matches >= 3:
            return 4

        if matches >= 2:
            return 3

        if matches >= 1:
            return 2

        return 0

    # ==========================================================
    # GET TEAM MATCH STRENGTH
    # ==========================================================

    def get_team_match_strength(
        self,
        article,
        team_name
    ):
        """
        3 = team in title
        2 = team in description
        1 = team only in content
        0 = no team mention
        """

        title = article.get(
            "title"
        ) or ""

        description = article.get(
            "description"
        ) or ""

        content = article.get(
            "content"
        ) or ""

        aliases = self.get_team_aliases(
            team_name
        )

        if self.contains_any(
            title,
            aliases
        ):
            return 3

        if self.contains_any(
            description,
            aliases
        ):
            return 2

        if self.contains_any(
            content,
            aliases
        ):
            return 1

        return 0

    # ==========================================================
    # GET PLAYER MATCH STRENGTH
    # ==========================================================

    def get_player_match_strength(
        self,
        article,
        team_name
    ):
        """
        2 = player in title
        1 = player in description/content
        0 = no player match
        """

        title = article.get(
            "title"
        ) or ""

        description = article.get(
            "description"
        ) or ""

        content = article.get(
            "content"
        ) or ""

        players = self.get_players(
            team_name
        )

        if self.contains_any(
            title,
            players
        ):
            return 2

        if self.contains_any(
            f"{description} {content}",
            players
        ):
            return 1

        return 0

    # ==========================================================
    # GET OTHER TEAMS IN TEXT
    # ==========================================================

    def get_other_major_teams(
        self,
        text,
        target_team
    ):
        """
        Return major clubs mentioned in the supplied text,
        excluding the requested team.
        """

        normalized_text = self.normalize_text(
            text
        )

        target_key = self.get_team_key(
            target_team
        )

        found_teams = []

        for team_key, aliases in (
            self.major_team_aliases.items()
        ):

            if team_key == target_key:
                continue

            if self.contains_any(
                normalized_text,
                aliases
            ):
                found_teams.append(
                    team_key
                )

        return found_teams

    # ==========================================================
    # MATCH SIGNAL CHECK
    # ==========================================================

    def has_match_signal(
        self,
        text
    ):

        normalized_text = self.normalize_text(
            text
        )

        for signal in self.match_signals:

            if signal in normalized_text:
                return True

        return False

    # ==========================================================
    # CLUB NEWS SIGNAL CHECK
    # ==========================================================

    def has_club_news_signal(
        self,
        text
    ):

        normalized_text = self.normalize_text(
            text
        )

        for signal in self.club_news_signals:

            if signal in normalized_text:
                return True

        return False

    # ==========================================================
    # TEAM FOCUS CHECK
    # ==========================================================

    def is_team_focused_article(
        self,
        article,
        team_name
    ):
        """
        Determine whether the requested team is genuinely
        the subject of the article.

        This prevents incidental mentions such as:

        "Chelsea legend predicts Man United transfer"

        from being treated as Chelsea news.
        """

        title = article.get(
            "title"
        ) or ""

        description = article.get(
            "description"
        ) or ""

        content = article.get(
            "content"
        ) or ""

        aliases = self.get_team_aliases(
            team_name
        )

        players = self.get_players(
            team_name
        )

        # ------------------------------------------------------
        # BASIC MATCHES
        # ------------------------------------------------------

        team_in_title = self.contains_any(
            title,
            aliases
        )

        team_in_description = self.contains_any(
            description,
            aliases
        )

        team_in_content = self.contains_any(
            content,
            aliases
        )

        player_in_title = self.contains_any(
            title,
            players
        )

        player_in_description = self.contains_any(
            description,
            players
        )

        player_in_content = self.contains_any(
            content,
            players
        )

        # ------------------------------------------------------
        # FOOTBALL CONTEXT
        # ------------------------------------------------------

        context_score = (
            self.get_football_context_score(
                article
            )
        )

        if context_score == 0:
            return False

        # ------------------------------------------------------
        # OTHER MAJOR CLUBS
        # ------------------------------------------------------

        other_teams_in_title = (
            self.get_other_major_teams(
                title,
                team_name
            )
        )

        other_teams_in_description = (
            self.get_other_major_teams(
                description,
                team_name
            )
        )

        # ------------------------------------------------------
        # CASE 1:
        # TEAM + PLAYER IN TITLE
        # ------------------------------------------------------

        if (
            team_in_title
            and player_in_title
        ):
            return True

        # ------------------------------------------------------
        # CASE 2:
        # PLAYER IN TITLE
        # ------------------------------------------------------

        if player_in_title:

            if (
                other_teams_in_title
                and not team_in_title
            ):
                return True

            return True

        # ------------------------------------------------------
        # CASE 3:
        # TEAM IN TITLE
        # ------------------------------------------------------

        if team_in_title:

            if other_teams_in_title:

                title_and_description = (
                    f"{title} {description}"
                )

                if self.has_match_signal(
                    title_and_description
                ):
                    return True

                if self.has_club_news_signal(
                    title_and_description
                ):
                    return True

                return False

            return True

        # ------------------------------------------------------
        # CASE 4:
        # TEAM IN DESCRIPTION + PLAYER
        # ------------------------------------------------------

        if (
            team_in_description
            and (
                player_in_description
                or player_in_content
            )
        ):
            return True

        # ------------------------------------------------------
        # CASE 5:
        # TEAM IN DESCRIPTION + STRONG FOOTBALL CONTEXT
        # ------------------------------------------------------

        if team_in_description:

            if context_score >= 3:
                return True

        # ------------------------------------------------------
        # CASE 6:
        # PLAYER + TEAM IN CONTENT
        # ------------------------------------------------------

        if (
            player_in_content
            and team_in_content
        ):
            return True

        # ------------------------------------------------------
        # EVERYTHING ELSE
        # ------------------------------------------------------

        return False

    # ==========================================================
    # BUILD SEARCH QUERY
    # ==========================================================

    def build_search_query(
        self,
        team_name
    ):
        """
        Keep NewsAPI query compact.

        Player names are intentionally not included here.
        Player intelligence happens locally.
        """

        aliases = self.get_team_aliases(
            team_name
        )

        search_terms = []

        for alias in aliases:

            search_terms.append(
                f'"{alias}"'
            )

        return " OR ".join(
            search_terms
        )

    # ==========================================================
    # RELEVANCE SCORE
    # ==========================================================

    def get_relevance_score(
        self,
        article,
        team_name
    ):

        if not self.is_team_focused_article(
            article,
            team_name
        ):
            return 0

        title = article.get(
            "title"
        ) or ""

        description = article.get(
            "description"
        ) or ""

        content = article.get(
            "content"
        ) or ""

        aliases = self.get_team_aliases(
            team_name
        )

        team_strength = (
            self.get_team_match_strength(
                article,
                team_name
            )
        )

        player_strength = (
            self.get_player_match_strength(
                article,
                team_name
            )
        )

        context_score = (
            self.get_football_context_score(
                article
            )
        )

        score = 0

        # ------------------------------------------------------
        # TEAM RELEVANCE
        # ------------------------------------------------------

        if team_strength == 3:
            score += 12

        elif team_strength == 2:
            score += 8

        elif team_strength == 1:
            score += 3

        # ------------------------------------------------------
        # PLAYER RELEVANCE
        # ------------------------------------------------------

        if player_strength == 2:
            score += 10

        elif player_strength == 1:
            score += 5

        # ------------------------------------------------------
        # FOOTBALL CONTEXT
        # ------------------------------------------------------

        score += context_score

        # ------------------------------------------------------
        # TEAM IN TITLE
        # ------------------------------------------------------

        if self.contains_any(
            title,
            aliases
        ):
            score += 3

        # ------------------------------------------------------
        # PLAYER IN TITLE
        # ------------------------------------------------------

        if player_strength == 2:
            score += 3

        # ------------------------------------------------------
        # DESCRIPTION QUALITY
        # ------------------------------------------------------

        if self.contains_any(
            description,
            aliases
        ):
            score += 2

        # ------------------------------------------------------
        # WEAK CONTENT-ONLY MENTION
        # ------------------------------------------------------

        if (
            team_strength == 1
            and player_strength == 0
        ):
            return 0

        return score

    # ==========================================================
    # FILTER RELEVANT ARTICLES
    # ==========================================================

    def filter_relevant_articles(
        self,
        articles,
        team_name
    ):

        scored_articles = []

        for article in articles:

            if not isinstance(
                article,
                dict
            ):
                continue

            score = self.get_relevance_score(
                article,
                team_name
            )

            # --------------------------------------------------
            # TEMPORARY DIAGNOSTIC LOGGING
            # --------------------------------------------------

            print(
                f"[NEWS DEBUG] {team_name} | "
                f"score={score} | "
                f"title={article.get('title')}"
            )

            if score >= 10:

                article["_relevance_score"] = score

                scored_articles.append(
                    article
                )

        scored_articles.sort(
            key=lambda article: article.get(
                "_relevance_score",
                0
            ),
            reverse=True
        )

        return scored_articles[:5]

    # ==========================================================
    # SEARCH NEWS
    # ==========================================================

    def search_news(
        self,
        query,
        page_size=20
    ):

        search_query = self.build_search_query(
            query
        )

        print(
            f'News search query: "{search_query}"'
        )

        url = (
            f"{self.base_url}/everything"
        )

        params = {
            "q": search_query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "apiKey": self.api_key,
        }

        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        print(
            "News API HTTP Status:",
            response.status_code
        )

        response.raise_for_status()

        data = response.json()

        articles = data.get(
            "articles",
            []
        )

        print(
            "News API articles returned:",
            len(articles)
        )

        relevant_articles = (
            self.filter_relevant_articles(
                articles,
                query
            )
        )

        print(
            "Relevant articles after filtering:",
            len(relevant_articles)
        )

        # Remove internal scoring before returning
        # articles to the rest of the application.
        for article in relevant_articles:

            article.pop(
                "_relevance_score",
                None
            )

        data["articles"] = relevant_articles

        return data