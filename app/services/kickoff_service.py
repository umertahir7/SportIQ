import os

from typing import Any, Dict, List, Optional

import requests

from dotenv import load_dotenv

from app.services.timezone_service import TimezoneService
from app.services.kickoff_service_events import KickoffEventsMixin


load_dotenv()


class KickoffService(KickoffEventsMixin):

    """
    Football data service.

    Primary source:

        BSD Sports API

    Secondary/fallback source:

        Kickoff API

    Event, fixture, result, standings, squad, broadcast and social
    functionality is provided by KickoffEventsMixin.
    """

    KICKOFF_BASE_URL = "https://api.kickoffapi.com/api/v1"

    BSD_BASE_URL = "https://sports.bzzoiro.com/api/v2"

    BSD_IMAGE_PROXY = "https://sports.bzzoiro.com/img"

    # Major league IDs used by BSD.
    MAJOR_LEAGUE_IDS = {
        "premier league": 1,
        "la liga": 3,
        "serie a": 4,
        "bundesliga": 5,
        "ligue 1": 6,
        "saudi pro league": 17,
    }

    # BSD-supported leaderboard statistics.
    BSD_LEADERBOARD_STATS = {
        "scorers",
        "assists",
        "yellowcards",
        "redcards",
        "fouls",
    }

    def __init__(self):

        self.kickoff_api_key = os.getenv("KICKOFF_API_KEY")

        self.bsd_api_key = os.getenv("BSD_API_KEY")

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": "AI-Sports-Agent/1.0",
                "Accept": "application/json",
            }
        )

        self._league_cache: Dict[str, Any] = {}

        self._season_cache: Dict[str, Any] = {}

        self._team_cache: Dict[str, Any] = {}

        self._venue_cache: Dict[str, Any] = {}

    # ============================================================
    # GENERIC REQUEST HELPERS
    # ============================================================

    def _bsd_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:

        """
        Make a GET request to BSD Sports API.

        Returns parsed JSON.

        Raises:

            requests.HTTPError on HTTP failure.
        """

        if not self.bsd_api_key:
            raise ValueError("BSD_API_KEY is not configured.")

        endpoint = endpoint.lstrip("/")

        url = f"{self.BSD_BASE_URL}/{endpoint}"

        headers = {
            "Authorization": f"Token {self.bsd_api_key}",
            "Accept": "application/json",
        }

        response = self.session.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    def _kickoff_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:

        """
        Make a GET request to Kickoff API.
        """

        if not self.kickoff_api_key:
            raise ValueError("KICKOFF_API_KEY is not configured.")

        endpoint = endpoint.lstrip("/")

        url = f"{self.KICKOFF_BASE_URL}/{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.kickoff_api_key}",
            "Accept": "application/json",
        }

        response = self.session.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    # ============================================================
    # IMAGE / LOGO HELPERS
    # ============================================================

    def _get_bsd_team_logo(
        self,
        team_id: Any,
    ) -> Optional[str]:

        if not team_id:
            return None

        return (
            f"{self.BSD_IMAGE_PROXY}/team/"
            f"{team_id}/?bg=transparent"
        )

    def _get_bsd_league_logo(
        self,
        league_id: Any,
    ) -> Optional[str]:

        if not league_id:
            return None

        return (
            f"{self.BSD_IMAGE_PROXY}/league/"
            f"{league_id}/?bg=transparent"
        )

    def _get_bsd_player_image(
        self,
        player_id: Any,
    ) -> Optional[str]:

        if not player_id:
            return None

        return (
            f"{self.BSD_IMAGE_PROXY}/player/"
            f"{player_id}/"
        )

    # Public image helpers used by SportsTools and Streamlit.

    def get_bsd_team_logo(
        self,
        team_id: Any,
    ) -> Optional[str]:

        return self._get_bsd_team_logo(team_id)

    def get_bsd_league_logo(
        self,
        league_id: Any,
    ) -> Optional[str]:

        return self._get_bsd_league_logo(league_id)

    def get_bsd_player_image(
        self,
        player_id: Any,
    ) -> Optional[str]:

        return self._get_bsd_player_image(player_id)

    def _enrich_bsd_squad_images(
        self,
        data: Any,
    ) -> Any:

        """
        Add BSD player image URLs recursively without changing
        the API shape.
        """

        player_keys = {
            "player_id",
            "player_name",
            "first_name",
            "last_name",
            "position",
            "nationality",
            "birth_date",
            "date_of_birth",
            "age",
            "number",
        }

        if isinstance(data, list):

            return [
                self._enrich_bsd_squad_images(item)
                for item in data
            ]

        if not isinstance(data, dict):

            return data

        enriched = {
            key: self._enrich_bsd_squad_images(value)
            for key, value in data.items()
        }

        player_id = self._first_present(
            enriched,
            "player_id",
            "id",
        )

        nested_player = enriched.get("player")

        if isinstance(nested_player, dict):

            nested_player_id = self._first_present(
                nested_player,
                "id",
                "player_id",
            )

            if nested_player_id is not None:

                nested_player = dict(nested_player)

                player_image = (
                    self._get_bsd_player_image(
                        nested_player_id
                    )
                )

                nested_player["image_url"] = player_image

                nested_player["photo"] = player_image

                nested_player["photo_url"] = player_image

                enriched["player"] = nested_player

        looks_like_player = (
            player_id is not None
            and any(
                key in enriched
                for key in player_keys
            )
        )

        if looks_like_player:

            player_image = (
                self._get_bsd_player_image(
                    player_id
                )
            )

            enriched["image_url"] = player_image

            enriched["photo"] = player_image

            enriched["photo_url"] = player_image

        return enriched

    # ============================================================
    # GENERAL HELPERS
    # ============================================================

    @staticmethod
    def _first_present(
        data: Dict[str, Any],
        *keys: str,
        default: Any = None,
    ) -> Any:

        """
        Return the first non-None value from a dictionary.
        """

        for key in keys:

            if (
                key in data
                and data[key] is not None
            ):

                return data[key]

        return default

    @staticmethod
    def _extract_event_collection(
        data: Any,
    ) -> List[Any]:

        """
        Extract a list from common BSD API response wrappers.

        Supports responses such as:

            [...]
            {"data": [...]}
            {"results": [...]}
            {"events": [...]}
            {"incidents": [...]}
            {"items": [...]}
            {"matches": [...]}
            {"seasons": [...]}
        """

        if isinstance(data, list):

            return data

        if not isinstance(data, dict):

            return []

        for key in (
            "data",
            "results",
            "events",
            "incidents",
            "items",
            "matches",
            "seasons",
        ):

            value = data.get(key)

            if isinstance(value, list):

                return value

        return []

    @staticmethod
    def _extract_single_event(
        data: Any,
    ) -> Dict[str, Any]:

        """
        Extract a single event from common BSD API
        response wrappers.
        """

        if isinstance(data, dict):

            for key in (
                "event",
                "data",
                "result",
            ):

                value = data.get(key)

                if isinstance(value, dict):

                    return value

            return data

        return {}

    @staticmethod
    def _normalize_team_name(
        name: Optional[str],
    ) -> str:

        if not name:

            return ""

        name = name.lower().strip()

        replacements = {
            "real madrid cf": "real madrid",
            "real madrid club de fútbol": "real madrid",
            "fc barcelona": "barcelona",
            "barcelona fc": "barcelona",
            "chelsea fc": "chelsea",
            "chelsea football club": "chelsea",
            "atletico madrid": "atlético madrid",
            "club atlético de madrid": "atlético madrid",
            "al nassr fc": "al nassr",
            "al-nassr fc": "al nassr",
            "al-nassr": "al nassr",
        }

        return replacements.get(
            name,
            name,
        )

    @staticmethod
    def _team_search_names(
        team_name: str,
    ) -> List[str]:

        """
        Return BSD-friendly search variants for common
        team-name formatting.
        """

        raw = (team_name or "").strip()

        if not raw:

            return []

        variants = [raw]

        normalized = raw.lower().strip()

        if (
            normalized == "al nassr"
            or normalized == "al nassr fc"
        ):

            variants.insert(
                0,
                "Al-Nassr",
            )

        elif (
            normalized == "al-nassr"
            or normalized == "al-nassr fc"
        ):

            variants.insert(
                0,
                "Al-Nassr",
            )

        return list(
            dict.fromkeys(variants)
        )

    # ============================================================
    # LEAGUES
    # ============================================================

    def get_bsd_leagues(
        self,
    ) -> List[Dict[str, Any]]:

        """
        Fetch available leagues from BSD.
        """

        if "all" in self._league_cache:

            return self._league_cache["all"]

        data = self._bsd_request(
            "leagues/"
        )

        leagues = (
            self._extract_event_collection(data)
        )

        self._league_cache["all"] = leagues

        return leagues

    def _resolve_bsd_league_name(
        self,
        league_id: Any,
    ) -> Optional[str]:

        """
        Resolve a BSD league ID to a readable league name.
        """

        if league_id is None:

            return None

        for name, known_id in (
            self.MAJOR_LEAGUE_IDS.items()
        ):

            try:

                if int(known_id) == int(
                    league_id
                ):

                    return name.title()

            except (
                TypeError,
                ValueError,
            ):

                pass

        try:

            leagues = self.get_bsd_leagues()

        except (
            requests.RequestException,
            ValueError,
        ):

            return None

        for league in leagues:

            if not isinstance(
                league,
                dict,
            ):

                continue

            candidate_id = (
                self._first_present(
                    league,
                    "id",
                    "league_id",
                )
            )

            try:

                if (
                    candidate_id is not None
                    and int(candidate_id)
                    == int(league_id)
                ):

                    return self._first_present(
                        league,
                        "name",
                        "league_name",
                        "title",
                    )

            except (
                TypeError,
                ValueError,
            ):

                continue

        return None

    def resolve_bsd_league_id(
        self,
        league_name: str,
    ) -> Optional[int]:

        """
        Resolve league name to BSD league ID.
        """

        normalized = (
            league_name.lower().strip()
        )

        if normalized in (
            self.MAJOR_LEAGUE_IDS
        ):

            return self.MAJOR_LEAGUE_IDS[
                normalized
            ]

        leagues = self.get_bsd_leagues()

        for league in leagues:

            if not isinstance(
                league,
                dict,
            ):

                continue

            name = self._first_present(
                league,
                "name",
                "league_name",
                "title",
            )

            if not name:

                continue

            normalized_name = (
                self._normalize_team_name(
                    name
                )
            )

            if normalized_name == normalized:

                league_id = (
                    self._first_present(
                        league,
                        "id",
                        "league_id",
                    )
                )

                if league_id is not None:

                    return int(league_id)

        return None

    # ============================================================
    # SEASONS
    # ============================================================

    def get_bsd_seasons(
        self,
        league_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:

        """
        Fetch seasons from BSD.

        When league_id is supplied, BSD expects the league-scoped
        endpoint:

            /leagues/{league_id}/seasons/

        Without a league_id, the generic seasons endpoint is used.

        BSD returns league-scoped seasons in this shape:

            {
                "league_id": 1,
                "count": 35,
                "seasons": [...]
            }

        Therefore the "seasons" field is handled explicitly here.
        """

        cache_key = (
            f"league:{league_id}"
        )

        if cache_key in (
            self._season_cache
        ):

            return self._season_cache[
                cache_key
            ]

        if league_id is not None:

            data = self._bsd_request(
                f"leagues/{league_id}/seasons/"
            )

        else:

            data = self._bsd_request(
                "seasons/"
            )

        # BSD's league-scoped seasons endpoint returns:
        #
        # {
        #     "league_id": ...,
        #     "count": ...,
        #     "seasons": [...]
        # }
        #
        # Read the seasons field directly rather than treating this
        # as a generic event collection.

        seasons: List[Dict[str, Any]] = []

        if isinstance(data, dict):

            raw_seasons = data.get(
                "seasons"
            )

            if isinstance(
                raw_seasons,
                list,
            ):

                seasons = [
                    season
                    for season in raw_seasons
                    if isinstance(
                        season,
                        dict,
                    )
                ]

            else:

                # Keep compatibility with any generic wrapper
                # BSD may return from another seasons endpoint.
                extracted = (
                    self._extract_event_collection(
                        data
                    )
                )

                seasons = [
                    season
                    for season in extracted
                    if isinstance(
                        season,
                        dict,
                    )
                ]

        elif isinstance(data, list):

            seasons = [
                season
                for season in data
                if isinstance(
                    season,
                    dict,
                )
            ]

        self._season_cache[
            cache_key
        ] = seasons

        return seasons

    def resolve_current_bsd_season_id(
        self,
        league_id: int,
    ) -> Optional[int]:

        """
        Resolve the current/latest season for a BSD league.
        """

        seasons = self.get_bsd_seasons(
            league_id
        )

        if not seasons:

            return None

        for season in seasons:

            if not isinstance(
                season,
                dict,
            ):

                continue

            if season.get(
                "current"
            ) is True:

                season_id = (
                    self._first_present(
                        season,
                        "id",
                        "season_id",
                    )
                )

                if season_id is not None:

                    return int(
                        season_id
                    )

            if season.get(
                "is_current"
            ) is True:

                season_id = (
                    self._first_present(
                        season,
                        "id",
                        "season_id",
                    )
                )

                if season_id is not None:

                    return int(
                        season_id
                    )

            if season.get(
                "active"
            ) is True:

                season_id = (
                    self._first_present(
                        season,
                        "id",
                        "season_id",
                    )
                )

                if season_id is not None:

                    return int(
                        season_id
                    )

        valid = []

        for season in seasons:

            if not isinstance(
                season,
                dict,
            ):

                continue

            season_id = (
                self._first_present(
                    season,
                    "id",
                    "season_id",
                )
            )

            if season_id is None:

                continue

            try:

                valid.append(
                    (
                        int(season_id),
                        season,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

        if not valid:

            return None

        valid.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return valid[0][0]

    # ============================================================
    # LEADERBOARDS
    # ============================================================

    def get_bsd_leaderboard(
        self,
        stat: str,
        league_id: int,
        season_id: Optional[int] = None,
        team_id: Optional[int] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:

        """
        Fetch a BSD league leaderboard.

        Supported statistics:

            scorers
            assists
            yellowcards
            redcards
            fouls

        Optional team_id filters the leaderboard to one team.

        If season_id is omitted, BSD uses the current season.
        """

        if not isinstance(
            stat,
            str,
        ):

            raise TypeError(
                "stat must be a string."
            )

        stat = stat.strip().lower()

        if stat not in self.BSD_LEADERBOARD_STATS:

            supported = ", ".join(
                sorted(
                    self.BSD_LEADERBOARD_STATS
                )
            )

            raise ValueError(
                f"Unsupported BSD leaderboard stat "
                f"'{stat}'. Supported stats: {supported}."
            )

        try:

            league_id = int(
                league_id
            )

        except (
            TypeError,
            ValueError,
        ):

            raise ValueError(
                "league_id must be an integer."
            )

        try:

            limit = int(
                limit
            )

        except (
            TypeError,
            ValueError,
        ):

            raise ValueError(
                "limit must be an integer."
            )

        if limit < 1:

            raise ValueError(
                "limit must be at least 1."
            )

        if limit > 50:

            limit = 50

        params: Dict[str, Any] = {
            "limit": limit,
        }

        if season_id is not None:

            try:

                params["season_id"] = int(
                    season_id
                )

            except (
                TypeError,
                ValueError,
            ):

                raise ValueError(
                    "season_id must be an integer."
                )

        if team_id is not None:

            try:

                params["team_id"] = int(
                    team_id
                )

            except (
                TypeError,
                ValueError,
            ):

                raise ValueError(
                    "team_id must be an integer."
                )

        return self._bsd_request(
            f"leagues/{league_id}/top/{stat}/",
            params=params,
        )

    # ============================================================
    # TEAMS
    # ============================================================

    def resolve_bsd_team(
        self,
        team_name: str,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:

        """
        Resolve a men's team using BSD.

        League/season filters are preferred because generic
        team-name searches can sometimes return women's/reserve
        teams.
        """

        normalized_name = (
            self._normalize_team_name(
                team_name
            )
        )

        cache_key = (
            f"{normalized_name}|"
            f"{league_id}|"
            f"{season_id}"
        )

        if cache_key in (
            self._team_cache
        ):

            return self._team_cache[
                cache_key
            ]

        try:

            teams: List[
                Dict[str, Any]
            ] = []

            for search_name in (
                self._team_search_names(
                    team_name
                )
            ):

                params: Dict[
                    str,
                    Any
                ] = {
                    "name": search_name,
                    "is_women": False,
                }

                if league_id is not None:

                    params[
                        "league_id"
                    ] = league_id

                if season_id is not None:

                    params[
                        "season_id"
                    ] = season_id

                data = self._bsd_request(
                    "teams/",
                    params=params,
                )

                teams = (
                    self._extract_event_collection(
                        data
                    )
                )

                if teams:

                    break

            candidates = []

            for team in teams:

                if not isinstance(
                    team,
                    dict,
                ):

                    continue

                name = self._first_present(
                    team,
                    "name",
                    "team_name",
                    "short_name",
                )

                if not name:

                    continue

                team_normalized = (
                    self._normalize_team_name(
                        name
                    )
                )

                if (
                    team_normalized
                    == normalized_name
                ):

                    candidates.append(
                        team
                    )

            if candidates:

                if league_id is not None:

                    for candidate in (
                        candidates
                    ):

                        candidate_league = (
                            self._first_present(
                                candidate,
                                "league_id",
                                "current_league_id",
                            )
                        )

                        if (
                            candidate_league
                            is not None
                        ):

                            try:

                                if (
                                    int(
                                        candidate_league
                                    )
                                    == int(
                                        league_id
                                    )
                                ):

                                    self._team_cache[
                                        cache_key
                                    ] = candidate

                                    return candidate

                            except (
                                TypeError,
                                ValueError,
                            ):

                                pass

                self._team_cache[
                    cache_key
                ] = candidates[0]

                return candidates[0]

            if teams:

                first = teams[0]

                if isinstance(
                    first,
                    dict,
                ):

                    self._team_cache[
                        cache_key
                    ] = first

                    return first

        except requests.RequestException:

            pass

        return None

    def get_bsd_team(
        self,
        team_name: str,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:

        """
        Public team resolver.
        """

        return self.resolve_bsd_team(
            team_name=team_name,
            league_id=league_id,
            season_id=season_id,
        )

    def get_bsd_team_enrichment(
        self,
        team_name: str,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:

        """
        Resolve and enrich a BSD team for UI/logo consumption.
        """

        team = self.resolve_bsd_team(
            team_name=team_name,
            league_id=league_id,
            season_id=season_id,
        )

        if not team:

            return None

        return self.enrich_team(
            team
        )

    # ============================================================
    # VENUES
    # ============================================================

    def get_bsd_venue(
        self,
        venue_id: Any,
    ) -> Optional[Dict[str, Any]]:

        """
        Fetch a venue by ID.
        """

        if not venue_id:

            return None

        cache_key = str(
            venue_id
        )

        if cache_key in (
            self._venue_cache
        ):

            return self._venue_cache[
                cache_key
            ]

        try:

            data = self._bsd_request(
                f"venues/{venue_id}/"
            )

            venue = (
                self._extract_single_event(
                    data
                )
            )

            if venue:

                self._venue_cache[
                    cache_key
                ] = venue

            return venue or None

        except requests.RequestException:

            return None

    # ============================================================
    # EVENT NORMALIZATION
    # ============================================================

    def _normalize_bsd_event(
        self,
        event: Dict[str, Any],
        requested_team_id: Optional[int] = None,
    ) -> Dict[str, Any]:

        """
        Normalize a BSD event into the internal Sports Agent format.

        This intentionally preserves richer BSD fields rather
        than throwing them away.
        """

        if not isinstance(
            event,
            dict,
        ):

            return {}

        home_team = self._first_present(
            event,
            "home_team",
            "home",
            default={},
        )

        away_team = self._first_present(
            event,
            "away_team",
            "away",
            default={},
        )

        if not isinstance(
            home_team,
            dict,
        ):

            home_team = (
                {
                    "name": home_team
                }
                if home_team
                else {}
            )

        if not isinstance(
            away_team,
            dict,
        ):

            away_team = (
                {
                    "name": away_team
                }
                if away_team
                else {}
            )

        home_team_id = (
            self._first_present(
                home_team,
                "id",
                "team_id",
            )
        )

        away_team_id = (
            self._first_present(
                away_team,
                "id",
                "team_id",
            )
        )

        if home_team_id is None:

            home_team_id = (
                self._first_present(
                    event,
                    "home_team_id",
                    "home_id",
                )
            )

        if away_team_id is None:

            away_team_id = (
                self._first_present(
                    event,
                    "away_team_id",
                    "away_id",
                )
            )

        home_name = (
            self._first_present(
                home_team,
                "name",
                "team_name",
                "short_name",
            )
        )

        away_name = (
            self._first_present(
                away_team,
                "name",
                "team_name",
                "short_name",
            )
        )

        raw_league = (
            self._first_present(
                event,
                "league",
                "competition",
                "tournament",
                default={},
            )
        )

        league = (
            raw_league
            if isinstance(
                raw_league,
                dict,
            )
            else {}
        )

        league_id = (
            self._first_present(
                league,
                "id",
                "league_id",
                "competition_id",
                "tournament_id",
            )
        )

        if league_id is None:

            league_id = (
                self._first_present(
                    event,
                    "league_id",
                    "competition_id",
                    "tournament_id",
                )
            )

        competition_name = (
            self._first_present(
                league,
                "name",
                "league_name",
                "competition_name",
                "title",
            )
        )

        if (
            competition_name is None
            and isinstance(
                raw_league,
                str,
            )
        ):

            competition_name = (
                raw_league
            )

        if competition_name is None:

            competition_name = (
                self._first_present(
                    event,
                    "competition_name",
                    "league_name",
                    "tournament_name",
                )
            )

        if (
            league_id is not None
            and competition_name is None
        ):

            competition_name = (
                self._resolve_bsd_league_name(
                    league_id
                )
            )

        season = (
            self._first_present(
                event,
                "season",
                default={},
            )
        )

        if not isinstance(
            season,
            dict,
        ):

            season = {}

        season_id = (
            self._first_present(
                season,
                "id",
                "season_id",
            )
        )

        if season_id is None:

            season_id = (
                self._first_present(
                    event,
                    "season_id",
                )
            )

        season_name = (
            self._first_present(
                season,
                "name",
                "season_name",
            )
        )

        if season_name is None:

            season_name = (
                self._first_present(
                    event,
                    "season_name",
                )
            )

        # --------------------------------------------------------
        # SCORE EXTRACTION
        # --------------------------------------------------------

        scores = (
            self._first_present(
                event,
                "scores",
                "score",
                default={},
            )
        )

        if not isinstance(
            scores,
            dict,
        ):

            scores = {}

        home_score = (
            self._first_present(
                event,
                "home_score",
                "home_goals",
                default=None,
            )
        )

        away_score = (
            self._first_present(
                event,
                "away_score",
                "away_goals",
                default=None,
            )
        )

        if home_score is None:

            home_score = (
                self._first_present(
                    scores,
                    "home",
                    "home_score",
                )
            )

        if away_score is None:

            away_score = (
                self._first_present(
                    scores,
                    "away",
                    "away_score",
                )
            )

        if isinstance(
            home_score,
            dict,
        ):

            home_score = (
                self._first_present(
                    home_score,
                    "goals",
                    "score",
                    "value",
                )
            )

        if isinstance(
            away_score,
            dict,
        ):

            away_score = (
                self._first_present(
                    away_score,
                    "goals",
                    "score",
                    "value",
                )
            )

        halftime = (
            self._first_present(
                event,
                "halftime",
                "half_time",
                "ht",
                default=None,
            )
        )

        if halftime is None:

            halftime = (
                self._first_present(
                    scores,
                    "halftime",
                    "half_time",
                    "ht",
                    default=None,
                )
            )

        fulltime = (
            self._first_present(
                event,
                "fulltime",
                "full_time",
                "ft",
                default=None,
            )
        )

        if fulltime is None:

            fulltime = (
                self._first_present(
                    scores,
                    "fulltime",
                    "full_time",
                    "ft",
                    default=None,
                )
            )

        extra_time = (
            self._first_present(
                event,
                "extra_time",
                "et",
            )
        )

        penalties = (
            self._first_present(
                event,
                "penalties",
                "pens",
            )
        )

        # --------------------------------------------------------
        # DATE / STATUS
        # --------------------------------------------------------

        event_date = (
            self._first_present(
                event,
                "event_date",
                "date",
                "start_time",
                "kickoff",
                "kickoff_time",
            )
        )

        status = (
            self._first_present(
                event,
                "status",
                "match_status",
                "state",
            )
        )

        # --------------------------------------------------------
        # ROUND / STAGE
        # --------------------------------------------------------

        round_info = (
            self._first_present(
                event,
                "round",
                "matchday",
                "round_name",
            )
        )

        stage = (
            self._first_present(
                event,
                "stage",
                "stage_name",
            )
        )

        # --------------------------------------------------------
        # VENUE
        # --------------------------------------------------------

        venue = (
            self._first_present(
                event,
                "venue",
                default={},
            )
        )

        if not isinstance(
            venue,
            dict,
        ):

            venue = {}

        venue_id = (
            self._first_present(
                venue,
                "id",
                "venue_id",
            )
        )

        if venue_id is None:

            venue_id = (
                self._first_present(
                    event,
                    "venue_id",
                )
            )

        if (
            venue_id is not None
            and not venue
        ):

            resolved_venue = (
                self.get_bsd_venue(
                    venue_id
                )
            )

            if resolved_venue:

                venue = resolved_venue

        # --------------------------------------------------------
        # RICH EVENT DATA
        # --------------------------------------------------------

        incidents = (
            self._first_present(
                event,
                "incidents",
                "events",
                "match_events",
                default=None,
            )
        )

        stats = (
            self._first_present(
                event,
                "stats",
                "statistics",
                "team_stats",
                default=None,
            )
        )

        lineups = (
            self._first_present(
                event,
                "lineups",
                default=None,
            )
        )

        cards = (
            self._first_present(
                event,
                "cards",
                default=None,
            )
        )

        substitutions = (
            self._first_present(
                event,
                "substitutions",
                default=None,
            )
        )

        highlights = (
            self._first_present(
                event,
                "highlights",
                default=None,
            )
        )

        weather = (
            self._first_present(
                event,
                "weather",
                default=None,
            )
        )

        h2h = (
            self._first_present(
                event,
                "h2h",
                "head_to_head",
                default=None,
            )
        )

        referee = (
            self._first_present(
                event,
                "referee",
                default=None,
            )
        )

        attendance = (
            self._first_present(
                event,
                "attendance",
                default=None,
            )
        )

        # --------------------------------------------------------
        # TEAM RESULT
        # --------------------------------------------------------

        result = None

        try:

            if (
                requested_team_id is not None
                and home_team_id is not None
                and away_team_id is not None
                and home_score is not None
                and away_score is not None
            ):

                requested_team_id = int(
                    requested_team_id
                )

                home_team_id = int(
                    home_team_id
                )

                away_team_id = int(
                    away_team_id
                )

                home_score_int = int(
                    home_score
                )

                away_score_int = int(
                    away_score
                )

                if (
                    requested_team_id
                    == home_team_id
                ):

                    if (
                        home_score_int
                        > away_score_int
                    ):

                        result = "win"

                    elif (
                        home_score_int
                        < away_score_int
                    ):

                        result = "loss"

                    else:

                        result = "draw"

                elif (
                    requested_team_id
                    == away_team_id
                ):

                    if (
                        away_score_int
                        > home_score_int
                    ):

                        result = "win"

                    elif (
                        away_score_int
                        < home_score_int
                    ):

                        result = "loss"

                    else:

                        result = "draw"

        except (
            TypeError,
            ValueError,
        ):

            result = None

        return {
            "id": self._first_present(
                event,
                "id",
                "event_id",
                "match_id",
            ),

            "date": event_date,

            "status": status,

            "home_team": {
                "id": home_team_id,
                "name": home_name,
                "logo": self._get_bsd_team_logo(
                    home_team_id
                ),
                "raw": home_team,
            },

            "away_team": {
                "id": away_team_id,
                "name": away_name,
                "logo": self._get_bsd_team_logo(
                    away_team_id
                ),
                "raw": away_team,
            },

            "home_score": home_score,

            "away_score": away_score,

            "halftime": halftime,

            "fulltime": fulltime,

            "extra_time": extra_time,

            "penalties": penalties,

            "league_id": league_id,

            "competition_name": competition_name,

            "competition_logo": (
                self._get_bsd_league_logo(
                    league_id
                )
            ),

            "competition_logo_url": (
                self._get_bsd_league_logo(
                    league_id
                )
            ),

            "season_id": season_id,

            "season_name": season_name,

            "round": round_info,

            "stage": stage,

            "venue": venue,

            "venue_id": venue_id,

            "result": result,

            "incidents": incidents,

            "statistics": stats,

            "lineups": lineups,

            "cards": cards,

            "substitutions": substitutions,

            "highlights": highlights,

            "weather": weather,

            "h2h": h2h,

            "referee": referee,

            "attendance": attendance,

            # Flat aliases for higher-level consumers.
            "fixture_id": self._first_present(
                event,
                "id",
                "event_id",
                "match_id",
            ),

            "home_team_name": home_name,

            "away_team_name": away_name,

            "competition_id": league_id,

            "venue_name": self._first_present(
                venue,
                "name",
                "venue_name",
            ),

            "venue_city": self._first_present(
                venue,
                "city",
                "location",
            ),

            "raw": event,
        }

    # ============================================================
    # TIMEZONE / BROADCAST COUNTRY
    # ============================================================

    def _get_broadcast_country_code(
        self,
    ) -> Optional[str]:

        """
        Determine the broadcast country from the machine timezone.

        This avoids hardcoding Pakistan or another country.

        Note:
            A timezone does not always uniquely identify a country,
            so only commonly-used mappings are included.
        """

        try:

            timezone_name = (
                TimezoneService()
                .get_timezone_name()
            )

        except Exception:

            return None

        timezone_to_country = {
            "Asia/Karachi": "PK",

            "Asia/Kolkata": "IN",
            "Asia/Calcutta": "IN",

            "Asia/Dubai": "AE",
            "Asia/Riyadh": "SA",
            "Asia/Qatar": "QA",
            "Asia/Muscat": "OM",

            "Asia/Singapore": "SG",
            "Asia/Tokyo": "JP",
            "Asia/Seoul": "KR",
            "Asia/Shanghai": "CN",
            "Asia/Hong_Kong": "HK",
            "Asia/Bangkok": "TH",
            "Asia/Jakarta": "ID",
            "Asia/Manila": "PH",

            "Europe/London": "GB",
            "Europe/Dublin": "IE",
            "Europe/Lisbon": "PT",

            "Europe/Madrid": "ES",
            "Europe/Paris": "FR",
            "Europe/Berlin": "DE",
            "Europe/Rome": "IT",

            "Europe/Amsterdam": "NL",
            "Europe/Brussels": "BE",
            "Europe/Zurich": "CH",
            "Europe/Vienna": "AT",
            "Europe/Stockholm": "SE",
            "Europe/Oslo": "NO",
            "Europe/Copenhagen": "DK",
            "Europe/Helsinki": "FI",
            "Europe/Athens": "GR",
            "Europe/Warsaw": "PL",
            "Europe/Istanbul": "TR",

            "America/New_York": "US",
            "America/Chicago": "US",
            "America/Denver": "US",
            "America/Los_Angeles": "US",

            "America/Toronto": "CA",
            "America/Vancouver": "CA",
            "America/Mexico_City": "MX",

            "America/Sao_Paulo": "BR",
            "America/Argentina/Buenos_Aires": "AR",

            "Australia/Sydney": "AU",
            "Australia/Melbourne": "AU",
            "Australia/Brisbane": "AU",

            "Pacific/Auckland": "NZ",
        }

        return timezone_to_country.get(
            timezone_name
        )
