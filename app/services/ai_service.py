import asyncio
import copy
import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from app.mcp.client import create_mcp_client
from app.services.user_context import set_current_user_id


load_dotenv()


class AIService:
    """
    AI service for SportsIQ.

    Responsibilities:
    - Load MCP tools dynamically.
    - Select only relevant MCP tools for specialized queries.
    - Execute MCP tool calls.
    - Retrieve targeted match details when a question requires them.
    - Preserve match scores from both result and detail responses.
    - Compact large MCP responses before sending them to the LLM.
    - Repair missing team_name arguments when possible.
    - Keep agent loops bounded.
    - Handle Groq rate limits gracefully.
    - Keep final answers grounded in retrieved sports data.
    """

    MAX_AGENT_ITERATIONS = 3

    TEAM_SPECIFIC_TOOLS = {
        "get_upcoming_matches",
        "get_team_results",
        "get_league_standings",
        "get_team_squad",
        "get_team_manager",
        "get_team_transfers",
        "get_top_scorers",
        "get_team_news",
    }

    SEASON_SUMMARY_TOOLS = {
        "get_team_results",
        "get_league_standings",
    }

    TEAM_OVERVIEW_TOOLS = (
        "get_team_results",
        "get_upcoming_matches",
        "get_league_standings",
        "get_team_squad",
        "get_team_manager",
        "get_team_transfers",
        "get_top_scorers",
        "get_team_news",
    )

    # ------------------------------------------------------------------
    # TEAM NAMES
    # ------------------------------------------------------------------

    COMMON_TEAM_NAMES = [
        # Clubs
        "Real Madrid",
        "Al Nassr",
        "Al-Nassr",
        "Chelsea",
        "Manchester United",
        "Barcelona",
        "Arsenal",
        "Liverpool",
        "Manchester City",
        "Bayern Munich",
        "Paris Saint-Germain",
        "PSG",
        "Inter Milan",
        "AC Milan",
        "Juventus",
        "Atletico Madrid",
        "Atlético Madrid",
        "Tottenham Hotspur",
        "Newcastle United",

        # National teams
        "Portugal",
        "Spain",
        "France",
        "Germany",
        "England",
        "Brazil",
        "Argentina",
        "Italy",
        "Netherlands",
        "Belgium",
        "Croatia",
        "Morocco",
        "Uruguay",
        "Colombia",
        "Turkey",
        "Türkiye",
        "Switzerland",
        "Denmark",
        "Serbia",
        "Scotland",
        "Wales",
        "Poland",
        "Norway",
    ]

    TEAM_ALIASES = {
        # Clubs
        "real madrid": "Real Madrid",
        "real": "Real Madrid",

        "al nassr": "Al Nassr",
        "al-nassr": "Al Nassr",
        "al nassr fc": "Al Nassr",

        "chelsea": "Chelsea",

        "manchester united": "Manchester United",
        "man united": "Manchester United",
        "man utd": "Manchester United",

        "barcelona": "Barcelona",
        "barca": "Barcelona",
        "barça": "Barcelona",

        "arsenal": "Arsenal",
        "liverpool": "Liverpool",

        "manchester city": "Manchester City",
        "man city": "Manchester City",

        "bayern munich": "Bayern Munich",
        "bayern": "Bayern Munich",

        "paris saint-germain": "Paris Saint-Germain",
        "paris saint germain": "Paris Saint-Germain",
        "psg": "Paris Saint-Germain",

        "inter milan": "Inter Milan",
        "inter": "Inter Milan",

        "ac milan": "AC Milan",
        "milan": "AC Milan",

        "juventus": "Juventus",
        "juve": "Juventus",

        "atletico madrid": "Atletico Madrid",
        "atlético madrid": "Atletico Madrid",
        "atletico": "Atletico Madrid",
        "atlético": "Atletico Madrid",

        "tottenham hotspur": "Tottenham Hotspur",
        "tottenham": "Tottenham Hotspur",
        "spurs": "Tottenham Hotspur",

        "newcastle united": "Newcastle United",
        "newcastle": "Newcastle United",

        # National teams
        "portugal": "Portugal",
        "portugal national team": "Portugal",
        "portuguese national team": "Portugal",

        "spain": "Spain",
        "spanish national team": "Spain",

        "france": "France",
        "french national team": "France",

        "germany": "Germany",
        "german national team": "Germany",

        "england": "England",
        "english national team": "England",

        "brazil": "Brazil",
        "brazil national team": "Brazil",
        "brasil": "Brazil",

        "argentina": "Argentina",
        "argentina national team": "Argentina",

        "italy": "Italy",
        "italian national team": "Italy",

        "netherlands": "Netherlands",
        "dutch national team": "Netherlands",
        "holland": "Netherlands",

        "belgium": "Belgium",
        "belgian national team": "Belgium",

        "croatia": "Croatia",
        "croatian national team": "Croatia",

        "morocco": "Morocco",
        "moroccan national team": "Morocco",

        "uruguay": "Uruguay",
        "uruguayan national team": "Uruguay",

        "colombia": "Colombia",
        "colombian national team": "Colombia",

        "turkey": "Turkey",
        "türkiye": "Turkey",
        "turkish national team": "Turkey",

        "switzerland": "Switzerland",
        "swiss national team": "Switzerland",

        "denmark": "Denmark",
        "danish national team": "Denmark",

        "serbia": "Serbia",
        "serbian national team": "Serbia",

        "scotland": "Scotland",
        "scottish national team": "Scotland",

        "wales": "Wales",
        "welsh national team": "Wales",

        "poland": "Poland",
        "polish national team": "Poland",

        "norway": "Norway",
        "norwegian national team": "Norway",
    }

    MANAGER_ALIASES = {
        "xabi alonso": "Xabi Alonso",
        "xabi": "Xabi Alonso",
    }

    PLAYER_ALIASES = {
        "cristiano ronaldo": "Cristiano Ronaldo",
        "ronaldo": "Cristiano Ronaldo",
    }

    LEAGUE_ALIASES = {
        "premier league": (1, "Premier League"),
        "epl": (1, "Premier League"),
        "la liga": (3, "La Liga"),
        "serie a": (4, "Serie A"),
        "bundesliga": (5, "Bundesliga"),
        "ligue 1": (6, "Ligue 1"),
        "saudi pro league": (17, "Saudi Pro League"),
    }

    QUERY_TOOL_KEYWORDS = {
        "get_upcoming_matches": [
            "next game",
            "next match",
            "upcoming",
            "upcoming game",
            "upcoming match",
            "fixture",
            "fixtures",
            "schedule",
            "when do they play",
            "when does",
            "who do they play next",
        ],

        "get_live_matches": [
            "live",
            "live game",
            "live match",
            "currently playing",
            "playing now",
            "right now",
            "score right now",
            "live scores",
        ],

        "get_team_news": [
            "news",
            "latest news",
            "recent news",
            "football news",
            "team news",
            "updates",
        ],

        "get_team_squad": [
            "squad",
            "players",
            "player list",
            "team players",
            "roster",
            "number 7",
            "no. 7",
            "no 7",
            "shirt number",
            "jersey number",
            "wearing number",
            "wearing no",
            "who wears",
            "who has number",
            "who has no",
            "who wears number",
        ],

        "get_team_manager": [
            "manager",
            "coach",
            "head coach",
            "who is the manager",
            "who manages",
            "manager of",
            "coach of",
        ],

        "get_team_transfers": [
            "transfer",
            "transfers",
            "new signing",
            "signings",
            "signed",
            "left the club",
            "joined the club",
            "incoming transfer",
            "outgoing transfer",
        ],

        "search_managers": [
            "which team xabi",
            "what team does xabi",
            "where does xabi",
            "coaches",
            "manages",
        ],

        "get_player_stats": [
            "current goals",
            "goals this season",
            "how many goals",
            "goal total",
            "goals total",
            "scored this season",
        ],

        "get_league_table": [
            "who is leading",
            "who leads",
            "leader of",
            "top of the",
            "first place",
            "league leader",
        ],

        "get_top_scorers": [
            "top scorer",
            "top scorers",
            "leading scorer",
            "leading scorers",
            "most goals",
            "goal leader",
            "goals leader",
            "who has scored the most",
        ],

        "get_league_standings": [
            "standings",
            "table",
            "league table",
            "league position",
            "current position",
            "current rank",
            "rank in",
            "rank",
            "position in",
            "where are they in the league",
            "where do they stand",
            "points table",
            "points",
        ],

        "get_team_results": [
            "result",
            "results",
            "last game",
            "last match",
            "latest game",
            "latest match",
            "previous game",
            "previous match",
            "recent game",
            "recent match",
            "recent results",
            "past game",
            "past match",
            "last played",
            "most recent game",
            "most recent match",
            "yesterday",
            "last night",
            "score",
            "scored",
            "who scored",
            "goal scorer",
            "goal scorers",
            "goalscorer",
            "goalscorers",
            "lost to",
            "beat",
            "won against",
            "draw against",
            "vs",
            "versus",
        ],
    }

    # ------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------

    def __init__(self, user_id=None):
        self.user_id = user_id

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not configured in the environment."
            )

        self.client = Groq(
            api_key=api_key,
            max_retries=0,
        )

        self.model = "openai/gpt-oss-120b"

        # AIService is cached per user by Streamlit, so this gives the
        # chat lightweight conversational context without sending the
        # entire chat history to Groq.
        self.last_team_name = None
        self.last_team_names = []

        self.tool_definitions = self._load_mcp_tools()

    # ------------------------------------------------------------------
    # MCP TOOL LOADING
    # ------------------------------------------------------------------

    def _load_mcp_tools(self):
        """
        Dynamically load MCP tools and convert them to the
        OpenAI/Groq function-tool format.

        Team-specific tools expose team_name as optional to Groq.
        Python repairs it before MCP execution when possible.
        """

        async def load_tools():
            async with create_mcp_client() as client:
                tools_result = await client.list_tools()

                tools = getattr(
                    tools_result,
                    "tools",
                    tools_result,
                )

                definitions = []

                for tool in tools:
                    name = getattr(
                        tool,
                        "name",
                        None,
                    )

                    if not name:
                        continue

                    description = getattr(
                        tool,
                        "description",
                        "",
                    ) or ""

                    input_schema = getattr(
                        tool,
                        "input_schema",
                        None,
                    )

                    if input_schema is None:
                        input_schema = getattr(
                            tool,
                            "inputSchema",
                            None,
                        )

                    if input_schema is None:
                        input_schema = {
                            "type": "object",
                            "properties": {},
                        }

                    parameters = copy.deepcopy(
                        input_schema
                    )

                    if name in self.TEAM_SPECIFIC_TOOLS:
                        required = parameters.get(
                            "required",
                            [],
                        )

                        if isinstance(
                            required,
                            list,
                        ):
                            parameters["required"] = [
                                field
                                for field in required
                                if field != "team_name"
                            ]

                    definitions.append(
                        {
                            "type": "function",
                            "function": {
                                "name": name,
                                "description": description,
                                "parameters": parameters,
                            },
                        }
                    )

                return definitions

        try:
            return asyncio.run(
                load_tools()
            )

        except Exception as exc:
            print(
                f"Failed to load MCP tools: {exc}"
            )
            return []

    # ------------------------------------------------------------------
    # TOOL LOOKUP
    # ------------------------------------------------------------------

    def _get_tool_definition(
        self,
        tool_name,
    ):
        for tool in self.tool_definitions:
            function = tool.get(
                "function",
                {},
            )

            if function.get(
                "name"
            ) == tool_name:
                return tool

        return None

    def _has_mcp_tool(
        self,
        tool_name,
    ):
        return (
            self._get_tool_definition(
                tool_name
            )
            is not None
        )

    # ------------------------------------------------------------------
    # MCP TOOL EXECUTION
    # ------------------------------------------------------------------

    def _execute_mcp_tool(
        self,
        tool_name,
        arguments,
    ):
        """
        Execute an MCP tool safely and return its structured result.
        """

        if self.user_id is not None:
            set_current_user_id(
                self.user_id
            )

        async def call_tool():
            async with create_mcp_client() as client:
                result = await client.call_tool(
                    tool_name,
                    arguments,
                )

                if getattr(
                    result,
                    "is_error",
                    False,
                ):
                    return {
                        "status": "error",
                        "error": (
                            "MCP tool returned an error."
                        ),
                    }

                structured_content = getattr(
                    result,
                    "structured_content",
                    None,
                )

                if structured_content is not None:
                    return structured_content

                content = getattr(
                    result,
                    "content",
                    None,
                )

                if content:
                    extracted = []

                    for item in content:
                        text_value = getattr(
                            item,
                            "text",
                            None,
                        )

                        if text_value is not None:
                            extracted.append(
                                text_value
                            )

                    if extracted:
                        return {
                            "status": "success",
                            "content": extracted,
                        }

                return {
                    "status": "success",
                    "content": [],
                }

        try:
            return asyncio.run(
                call_tool()
            )

        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # TEAM NAME HELPERS
    # ------------------------------------------------------------------

    def _normalize_team_name(
        self,
        team_name,
    ):
        if not isinstance(
            team_name,
            str,
        ):
            return team_name

        clean = team_name.strip()

        if not clean:
            return None

        lowered = clean.lower()

        if lowered in self.TEAM_ALIASES:
            return self.TEAM_ALIASES[
                lowered
            ]

        if lowered == "al-nassr":
            return "Al Nassr"

        if lowered in {
            "atletico madrid",
            "atlético madrid",
        }:
            return "Atletico Madrid"

        return clean

    def _infer_manager_name(self, user_message):
        text = (user_message or "").lower()
        for alias, canonical in sorted(self.MANAGER_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", text):
                return canonical
        return None

    def _infer_player_name(self, user_message):
        text = (user_message or "").lower()
        for alias, canonical in sorted(self.PLAYER_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", text):
                return canonical
        return None

    def _infer_league(self, user_message):
        text = (user_message or "").lower()
        for alias, value in sorted(self.LEAGUE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", text):
                return value
        return None

    def _remember_teams(self, user_message):
        """Remember explicitly mentioned teams for short follow-ups."""
        teams = self._extract_mentioned_teams(user_message)

        if teams:
            self.last_team_names = teams[:4]
            self.last_team_name = teams[0]

        return teams

    def _is_contextual_followup(self, user_message):
        text = (user_message or "").strip().lower()

        phrases = [
            "is this all",
            "is that all",
            "what else",
            "anything else",
            "what about the rest",
            "give me more",
            "more info",
            "more information",
            "can you provide standings",
            "show standings",
            "give standings",
            "what is their rank",
            "what is their position",
            "who has number",
            "who wears number",
            "who wears no",
            "who wears the number",
            "what about number",
        ]

        return any(phrase in text for phrase in phrases)

    def _is_team_overview_query(self, user_message):
        text = (user_message or "").strip().lower()

        phrases = [
            "all info",
            "all the info",
            "everything about",
            "tell me everything about",
            "full info",
            "full information",
            "complete info",
            "complete information",
            "give me all",
            "what do you have on",
            "what information do you have on",
            "is this all",
            "is that all",
            "what else do you have",
            "anything else about",
            "use each tool",
            "use all tools",
            "run each tool",
            "run all tools",
            "check each tool",
            "check all tools",
            "test each tool",
            "test all tools",
            "every tool",
            "all tools for",
        ]

        return any(phrase in text for phrase in phrases)

    def _infer_team_name(
        self,
        user_message,
        messages=None,
    ):
        """
        Infer a missing team_name from:
        1. The current user request.
        2. Previous tool results.
        3. Known club/national-team aliases.
        """

        user_text = (
            user_message or ""
        ).lower()

        messages = messages or []

        candidates = []

        for message in messages:
            if not isinstance(
                message,
                dict,
            ):
                continue

            if message.get(
                "role"
            ) != "tool":
                continue

            raw_content = message.get(
                "content"
            )

            if not raw_content:
                continue

            try:
                if isinstance(
                    raw_content,
                    str,
                ):
                    content = json.loads(
                        raw_content
                    )
                else:
                    content = raw_content

            except Exception:
                continue

            if not isinstance(
                content,
                dict,
            ):
                continue

            teams = content.get(
                "teams",
                [],
            )

            if isinstance(
                teams,
                list,
            ):
                for team in teams:
                    if not isinstance(
                        team,
                        dict,
                    ):
                        continue

                    name = team.get(
                        "name"
                    )

                    if name:
                        candidates.append(
                            name
                        )

            team = content.get(
                "team"
            )

            if isinstance(
                team,
                dict,
            ):
                name = team.get(
                    "name"
                )

                if name:
                    candidates.append(
                        name
                    )

            elif isinstance(
                team,
                str,
            ):
                candidates.append(
                    team
                )

        for alias, canonical in sorted(
            self.TEAM_ALIASES.items(),
            key=lambda item: len(
                item[0]
            ),
            reverse=True,
        ):
            if re.search(
                rf"\b{re.escape(alias)}\b",
                user_text,
            ):
                return canonical

        for team_name in candidates:
            if not team_name:
                continue

            if (
                str(team_name).lower()
                in user_text
            ):
                return self._normalize_team_name(
                    team_name
                )

        # Use the remembered team only for contextual follow-ups.
        # This prevents unrelated questions from accidentally inheriting
        # the previous team.
        if self._is_contextual_followup(user_message):
            if self.last_team_name:
                return self.last_team_name

        return None

    def _extract_mentioned_teams(
        self,
        user_message,
    ):
        """
        Return recognized club/national team names mentioned
        in the user's request.
        """

        text = (
            user_message or ""
        ).lower()

        found = []

        for alias, canonical in sorted(
            self.TEAM_ALIASES.items(),
            key=lambda item: len(
                item[0]
            ),
            reverse=True,
        ):
            if re.search(
                rf"\b{re.escape(alias)}\b",
                text,
            ):
                if canonical not in found:
                    found.append(
                        canonical
                    )

        return found

    def _repair_tool_arguments(
        self,
        tool_name,
        arguments,
        user_message,
        messages,
    ):
        """
        Repair team-specific tool arguments before MCP execution.
        """

        if not isinstance(
            arguments,
            dict,
        ):
            arguments = {}

        repaired = dict(
            arguments
        )

        if (
            tool_name
            not in self.TEAM_SPECIFIC_TOOLS
        ):
            return repaired

        team_name = repaired.get(
            "team_name"
        )

        if (
            isinstance(
                team_name,
                str,
            )
            and team_name.strip()
        ):
            repaired[
                "team_name"
            ] = self._normalize_team_name(
                team_name
            )
            return repaired

        inferred_team = (
            self._infer_team_name(
                user_message,
                messages,
            )
        )

        if inferred_team:
            repaired[
                "team_name"
            ] = inferred_team

        return repaired

    # ------------------------------------------------------------------
    # QUERY CLASSIFICATION
    # ------------------------------------------------------------------

    def _is_match_detail_query(
        self,
        user_message,
    ):
        text = (
            user_message or ""
        ).lower()

        detail_terms = [
            "who scored",
            "who score",
            "goal scorer",
            "goal scorers",
            "goalscorer",
            "goalscorers",
            "scorer",
            "scorers",
            "scored in",
            "scored that",
            "scored the",
            "scored for",
            "scoring",
            "goal",
            "goals",
            "red card",
            "yellow card",
            "cards",
            "substitution",
            "substitutions",
            "subbed",
            "came on",
            "came off",
            "starting xi",
            "starting eleven",
            "started",
            "start the game",
            "start the match",
            "played",
            "play in",
            "lineup",
            "line-up",
            "line up",
            "team sheet",
            "bench",
            "unused substitute",
            "substitute",
            "did ronaldo play",
            "did cristiano play",
        ]

        return any(
            term in text
            for term in detail_terms
        )

    def _is_player_participation_query(
        self,
        user_message,
    ):
        text = (
            user_message or ""
        ).lower()

        terms = [
            "did ronaldo play",
            "did cristiano ronaldo play",
            "did cristiano play",
            "did he play",
            "did he start",
            "did he start the game",
            "did he start the match",
            "was he playing",
            "was he in the lineup",
            "was he in the squad",
            "was ronaldo in the lineup",
            "was ronaldo in the squad",
            "ronaldo start",
            "ronaldo started",
            "ronaldo lineup",
            "ronaldo line-up",
            "ronaldo played",
        ]

        return any(
            term in text
            for term in terms
        )

    def _is_last_game_query(
        self,
        user_message,
    ):
        text = (
            user_message or ""
        ).lower()

        terms = [
            "last game",
            "last match",
            "latest game",
            "latest match",
            "previous game",
            "previous match",
            "last played",
            "most recent game",
            "most recent match",
            "last night",
            "yesterday",
            "yesterday's game",
            "yesterday's match",
        ]

        return any(
            term in text
            for term in terms
        )

    def _is_season_summary_query(
        self,
        user_message,
    ):
        text = (
            user_message or ""
        ).lower()

        season_terms = [
            "season so far",
            "season summary",
            "season performance",
            "how is",
            "how are",
            "doing this season",
            "doing this year",
            "season record",
            "season stats",
            "season statistics",
            "league position",
            "league position this season",
            "current league position",
            "current standings",
        ]

        return any(
            term in text
            for term in season_terms
        )

    def _get_tools_for_query(
        self,
        user_message,
    ):
        """
        Select only MCP tools relevant to the query.
        """

        if self._is_season_summary_query(
            user_message
        ):
            selected_names = (
                self.SEASON_SUMMARY_TOOLS
            )

        else:
            text = (
                user_message or ""
            ).lower()

            selected_names = []

            for tool_name, keywords in (
                self.QUERY_TOOL_KEYWORDS.items()
            ):
                if any(
                    keyword in text
                    for keyword in keywords
                ):
                    selected_names.append(
                        tool_name
                    )

            mentioned_teams = (
                self._extract_mentioned_teams(
                    user_message
                )
            )

            if len(
                mentioned_teams
            ) >= 2:
                if (
                    "get_team_results"
                    not in selected_names
                ):
                    selected_names.append(
                        "get_team_results"
                    )

            if not selected_names:
                return self.tool_definitions

            selected_names = set(
                selected_names
            )

        selected = []

        for tool in self.tool_definitions:
            name = tool.get(
                "function",
                {},
            ).get(
                "name"
            )

            if name in selected_names:
                selected.append(
                    tool
                )

        return selected

    # ------------------------------------------------------------------
    # MATCH DETAIL HELPERS
    # ------------------------------------------------------------------

    def _extract_fixture_id(
        self,
        match,
    ):
        """
        Extract the event/fixture ID from a result record.

        BSD naming can vary, so check common possibilities and nested
        match objects.
        """

        if not isinstance(
            match,
            dict,
        ):
            return None

        possible_keys = [
            "fixture_id",
            "event_id",
            "match_id",
            "id",
        ]

        for key in possible_keys:
            value = match.get(
                key
            )

            if value is not None:
                return value

        nested_match = match.get(
            "match"
        )

        if isinstance(
            nested_match,
            dict,
        ):
            for key in possible_keys:
                value = nested_match.get(
                    key
                )

                if value is not None:
                    return value

        return None

    def _extract_incidents(
        self,
        data,
    ):
        """
        Find incidents in either a normal match-detail response or
        nested/alternate response shapes.
        """

        if not isinstance(
            data,
            dict,
        ):
            return []

        possible = [
            data.get(
                "incidents"
            ),
            data.get(
                "events"
            ),
            data.get(
                "match_incidents"
            ),
        ]

        for value in possible:
            if isinstance(
                value,
                list,
            ):
                return value

        nested_match = data.get(
            "match"
        )

        if isinstance(
            nested_match,
            dict,
        ):
            for key in (
                "incidents",
                "events",
                "match_incidents",
            ):
                value = nested_match.get(
                    key
                )

                if isinstance(
                    value,
                    list,
                ):
                    return value

        return []

    def _extract_lineups(
        self,
        data,
    ):
        if not isinstance(
            data,
            dict,
        ):
            return []

        possible = [
            data.get(
                "lineups"
            ),
            data.get(
                "lineup"
            ),
        ]

        for value in possible:
            if isinstance(
                value,
                list,
            ):
                return value

            if isinstance(
                value,
                dict,
            ):
                return value

        nested_match = data.get(
            "match"
        )

        if isinstance(
            nested_match,
            dict,
        ):
            for key in (
                "lineups",
                "lineup",
            ):
                value = nested_match.get(
                    key
                )

                if isinstance(
                    value,
                    (list, dict),
                ):
                    return value

        return []

    def _extract_score_value(
        self,
        source,
        side,
    ):
        """
        Extract a home/away score from several possible BSD response
        shapes.

        Examples supported:

            {
                "home_score": 2,
                "away_score": 1
            }

            {
                "score": {
                    "home": 2,
                    "away": 1
                }
            }

            {
                "scores": {
                    "home": {"current": 2},
                    "away": {"current": 1}
                }
            }

        This prevents AIService from losing the actual match score when
        get_match_details returns a nested score object.
        """

        if not isinstance(
            source,
            dict,
        ):
            return None

        direct_keys = (
            [
                "home_score",
                "homeScore",
                "home",
            ]
            if side == "home"
            else [
                "away_score",
                "awayScore",
                "away",
            ]
        )

        for key in direct_keys:
            value = source.get(
                key
            )

            if isinstance(
                value,
                (int, float),
            ):
                return value

            if isinstance(
                value,
                str,
            ):
                if value.strip().isdigit():
                    return int(
                        value.strip()
                    )

        nested_score_keys = [
            "score",
            "scores",
            "result",
        ]

        for container_key in nested_score_keys:
            nested = source.get(
                container_key
            )

            if not isinstance(
                nested,
                dict,
            ):
                continue

            side_value = nested.get(
                side
            )

            if isinstance(
                side_value,
                (int, float),
            ):
                return side_value

            if isinstance(
                side_value,
                str,
            ):
                if side_value.strip().isdigit():
                    return int(
                        side_value.strip()
                    )

            if isinstance(
                side_value,
                dict,
            ):
                for value_key in (
                    "current",
                    "display",
                    "goals",
                    "score",
                    "value",
                    "total",
                ):
                    value = side_value.get(
                        value_key
                    )

                    if isinstance(
                        value,
                        (int, float),
                    ):
                        return value

                    if isinstance(
                        value,
                        str,
                    ):
                        if value.strip().isdigit():
                            return int(
                                value.strip()
                            )

        return None

    def _extract_team_value(
        self,
        source,
        side,
    ):
        """
        Extract home/away team names from direct or nested BSD shapes.
        """

        if not isinstance(
            source,
            dict,
        ):
            return None

        direct_key = (
            "home_team"
            if side == "home"
            else "away_team"
        )

        value = source.get(
            direct_key
        )

        if value is not None:
            return value

        side_value = source.get(
            side
        )

        if isinstance(
            side_value,
            str,
        ):
            return side_value

        if isinstance(
            side_value,
            dict,
        ):
            for key in (
                "name",
                "team_name",
                "short_name",
            ):
                value = side_value.get(
                    key
                )

                if value:
                    return value

        return None

    def _normalize_incident(
        self,
        incident,
    ):
        """
        Normalize a BSD incident while preserving the fields most
        useful for the final answer.
        """

        if not isinstance(
            incident,
            dict,
        ):
            return None

        normalized = {}

        useful_keys = [
            "incident_type",
            "type",
            "incident_class",
            "incidentType",
            "category",
            "player",
            "player_name",
            "player_id",
            "assist",
            "assist_player",
            "assist_player_name",
            "team",
            "team_name",
            "is_home",
            "minute",
            "added_time",
            "time",
            "reason",
            "result",
            "score",
            "card",
        ]

        for key in useful_keys:
            if key not in incident:
                continue

            value = incident.get(
                key
            )

            if value is None:
                continue

            if isinstance(
                value,
                dict,
            ):
                compact_value = {}

                for nested_key in (
                    "id",
                    "name",
                    "short_name",
                    "player_name",
                    "team_name",
                ):
                    nested_value = value.get(
                        nested_key
                    )

                    if nested_value is not None:
                        compact_value[
                            nested_key
                        ] = nested_value

                if compact_value:
                    normalized[
                        key
                    ] = compact_value

            else:
                normalized[
                    key
                ] = value

        if not normalized:
            return None

        return normalized

    @staticmethod
    def _normalize_entity_name(value):
        """Normalize team/entity names for reliable incident attribution."""
        if isinstance(value, dict):
            value = (
                value.get("name")
                or value.get("team_name")
                or value.get("short_name")
            )
        if value is None:
            return ""
        text = str(value).strip().lower()
        text = text.replace("–", "-").replace("—", "-")
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _incident_belongs_to_team(
        self,
        incident,
        target_team,
        home_team,
        away_team,
    ):
        """
        Determine whether a match incident belongs to the requested team.

        BSD can identify the incident team either by team/team_name or by
        is_home. We only accept a scorer when one of those signals can be
        matched to the requested team; this prevents the opponent's scorers
        from being reported as the requested team's scorers.
        """
        if not target_team:
            return False

        target_norm = self._normalize_entity_name(target_team)
        home_norm = self._normalize_entity_name(home_team)
        away_norm = self._normalize_entity_name(away_team)

        incident_team = incident.get("team_name") or incident.get("team")
        incident_team_norm = self._normalize_entity_name(incident_team)

        if incident_team_norm:
            if incident_team_norm == target_norm:
                return True

            # Allow a short/expanded BSD name to match the same team.
            if (
                target_norm in incident_team_norm
                or incident_team_norm in target_norm
            ):
                return True

            return False

        is_home = incident.get("is_home")
        if isinstance(is_home, str):
            lowered = is_home.strip().lower()
            if lowered in {"true", "1", "yes", "home"}:
                is_home = True
            elif lowered in {"false", "0", "no", "away"}:
                is_home = False
            else:
                is_home = None

        if is_home is True and home_norm:
            return home_norm == target_norm or target_norm in home_norm or home_norm in target_norm

        if is_home is False and away_norm:
            return away_norm == target_norm or target_norm in away_norm or away_norm in target_norm

        # No reliable team attribution: do not guess.
        return False

    def _extract_requested_result_count(self, user_message):
        """Return an explicit 'last N games/matches' count, if present."""
        text = (user_message or "").lower()
        match = re.search(
            r"\b(?:last|past|previous)\s+(\d+)\s+(?:games?|matches?|results?)\b",
            text,
        )
        if match:
            return max(1, min(int(match.group(1)), 5))

        word_counts = {
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
        }
        for word, count in word_counts.items():
            if re.search(
                rf"\b(?:last|past|previous)\s+{word}\s+(?:games?|matches?|results?)\b",
                text,
            ):
                return count

        return None

    def _compact_match_details(
        self,
        data,
        user_message=None,
    ):
        """
        Compact a single detailed match response.

        Important:
        Match score is explicitly extracted here so the AI layer can
        access it even when the MCP detail response stores the score
        inside nested score/scores objects.
        """

        if not isinstance(
            data,
            dict,
        ):
            return data

        if data.get(
            "status"
        ) == "error":
            return data

        source = data

        if isinstance(
            data.get("match"),
            dict,
        ):
            source = data.get(
                "match"
            )

        compact = {
            "status": data.get(
                "status"
            )
        }

        # --------------------------------------------------------------
        # Match ID
        # --------------------------------------------------------------

        # --------------------------------------------------------------
        # Teams
        # --------------------------------------------------------------

        home_team = (
            self._extract_team_value(
                source,
                "home",
            )
        )

        away_team = (
            self._extract_team_value(
                source,
                "away",
            )
        )

        if isinstance(home_team, dict):
            home_team = (
                home_team.get("name")
                or home_team.get("team_name")
                or home_team.get("short_name")
            )

        if isinstance(away_team, dict):
            away_team = (
                away_team.get("name")
                or away_team.get("team_name")
                or away_team.get("short_name")
            )

        if home_team is not None:
            compact[
                "home_team"
            ] = home_team

        if away_team is not None:
            compact[
                "away_team"
            ] = away_team

        # --------------------------------------------------------------
        # DATE / TIME
        # --------------------------------------------------------------

        for output_key, possible_keys in {
            "date": [
                "local_date",
                "date",
            ],
            "time": [
                "local_time",
                "time",
            ],
            "timezone": [
                "local_timezone",
                "timezone",
            ],
            "competition": [
                "competition_display_name",
                "competition_name",
            ],
            "round": [
                "round_label",
                "round",
            ],
            "status": [
                "status",
            ],
        }.items():
            for key in possible_keys:
                value = source.get(
                    key
                )

                if value is not None:
                    compact[
                        output_key
                    ] = value
                    break

        # --------------------------------------------------------------
        # MATCH SCORE
        # --------------------------------------------------------------

        home_score = (
            self._extract_score_value(
                source,
                "home",
            )
        )

        away_score = (
            self._extract_score_value(
                source,
                "away",
            )
        )

        if home_score is not None:
            compact[
                "home_score"
            ] = home_score

        if away_score is not None:
            compact[
                "away_score"
            ] = away_score

        # Preserve a human-readable score as well.
        if (
            home_score is not None
            and away_score is not None
        ):
            compact[
                "score"
            ] = (
                f"{home_score}-{away_score}"
            )

        # --------------------------------------------------------------
        # INCidents
        # --------------------------------------------------------------

        incidents = (
            self._extract_incidents(
                data
            )
        )

        compact_incidents = []

        for incident in incidents:
            normalized = (
                self._normalize_incident(
                    incident
                )
            )

            if normalized:
                compact_incidents.append(
                    normalized
                )

        if compact_incidents:
            compact[
                "incidents"
            ] = compact_incidents

            # Keep a dedicated scorer list so the final answer model does
            # not have to infer scorers from a large incident payload.
            # IMPORTANT: only keep scorers who belong to the team asked
            # about. BSD incident feeds can contain goals for both sides.
            goal_scorers = []
            target_team = self._infer_team_name(user_message or "", [])

            for incident in compact_incidents:
                incident_type = str(
                    incident.get("incident_type")
                    or incident.get("type")
                    or incident.get("incident_class")
                    or incident.get("incidentType")
                    or incident.get("category")
                    or ""
                ).lower()
                player = (
                    incident.get("player_name")
                    or incident.get("player")
                )

                is_goal = (
                    "goal" in incident_type
                    and "own" not in incident_type
                    and "miss" not in incident_type
                    and "penalty miss" not in incident_type
                )

                if not is_goal or not player:
                    continue

                if isinstance(player, dict):
                    player = (
                        player.get("name")
                        or player.get("short_name")
                        or player.get("player_name")
                    )

                if not player:
                    continue

                if not self._incident_belongs_to_team(
                    incident,
                    target_team,
                    home_team,
                    away_team,
                ):
                    continue

                scorer = {"player": player}
                for key in ("minute", "added_time"):
                    if incident.get(key) is not None:
                        scorer[key] = incident[key]
                goal_scorers.append(scorer)

            if goal_scorers:
                compact["goal_scorers"] = goal_scorers

        # --------------------------------------------------------------
        # Lineups
        # --------------------------------------------------------------

        if self._is_player_participation_query(
            user_message or ""
        ):
            lineups = (
                self._extract_lineups(
                    data
                )
            )

            if lineups:
                compact[
                    "lineups"
                ] = lineups

        return compact

    def _needs_match_details(
        self,
        user_message,
    ):
        return (
            self._is_match_detail_query(
                user_message
            )
        )

    def _get_match_detail_tool_name(
        self,
    ):
        candidates = [
            "get_match_details",
            "get_match_detail",
            "get_fixture_details",
            "get_fixture_detail",
        ]

        for name in candidates:
            if self._has_mcp_tool(
                name
            ):
                return name

        return None

    def _build_match_detail_arguments(
        self,
        tool_name,
        fixture_id,
        user_message,
    ):
        """
        Build arguments according to the loaded MCP schema rather than
        assuming a single parameter name.
        """

        definition = (
            self._get_tool_definition(
                tool_name
            )
        )

        if not definition:
            return {
                "fixture_id": fixture_id
            }

        parameters = (
            definition.get(
                "function",
                {},
            ).get(
                "parameters",
                {},
            )
        )

        properties = parameters.get(
            "properties",
            {},
        )

        arguments = {}

        possible_id_fields = [
            "fixture_id",
            "event_id",
            "match_id",
            "id",
        ]

        for field in possible_id_fields:
            if field in properties:
                arguments[
                    field
                ] = fixture_id
                break

        if self._is_player_participation_query(
            user_message
        ):
            if "include_lineups" in properties:
                arguments[
                    "include_lineups"
                ] = True

        return arguments

    def _select_relevant_match(
        self,
        results,
        user_message,
    ):
        """
        Select the exact relevant result.

        For two-team questions, prefer the match involving both teams.
        For last/latest questions, prefer the newest match.
        Otherwise use the first returned result.
        """

        if not isinstance(
            results,
            list,
        ) or not results:
            return None

        mentioned_teams = (
            self._extract_mentioned_teams(
                user_message
            )
        )

        # --------------------------------------------------------------
        # Exact head-to-head match
        # --------------------------------------------------------------

        if len(
            mentioned_teams
        ) >= 2:
            team_a = mentioned_teams[0].lower()
            team_b = mentioned_teams[1].lower()

            for match in results:
                if not isinstance(
                    match,
                    dict,
                ):
                    continue

                home = str(
                    match.get(
                        "home_team"
                    )
                    or ""
                ).lower()

                away = str(
                    match.get(
                        "away_team"
                    )
                    or ""
                ).lower()

                if (
                    (
                        team_a in home
                        and team_b in away
                    )
                    or (
                        team_b in home
                        and team_a in away
                    )
                ):
                    return match

        # --------------------------------------------------------------
        # Latest match
        # --------------------------------------------------------------

        if self._is_last_game_query(
            user_message
        ):
            sorted_results = sorted(
                results,
                key=lambda item: (
                    str(
                        item.get(
                            "date"
                        )
                        or ""
                    ),
                    str(
                        item.get(
                            "time"
                        )
                        or ""
                    ),
                ),
                reverse=True,
            )

            if sorted_results:
                return sorted_results[0]

        return results[0]

    def _retrieve_match_details_if_needed(
        self,
        user_message,
        compact_result,
    ):
        """
        After get_team_results identifies the relevant match, retrieve
        exactly one detailed match record if the user asks for
        scorers, incidents, lineup, or player participation.
        """

        if not self._needs_match_details(
            user_message
        ):
            return None

        if not isinstance(
            compact_result,
            dict,
        ):
            return None

        results = compact_result.get(
            "results",
            [],
        )

        if not isinstance(
            results,
            list,
        ) or not results:
            return None

        match = self._select_relevant_match(
            results,
            user_message,
        )

        if not match:
            return None

        fixture_id = (
            self._extract_fixture_id(
                match
            )
        )

        if fixture_id is None:
            if (
                match.get(
                    "incidents"
                )
                or match.get(
                    "events"
                )
                or match.get(
                    "lineups"
                )
            ):
                return self._compact_match_details(
                    match,
                    user_message,
                )

            return None

        tool_name = (
            self._get_match_detail_tool_name()
        )

        if not tool_name:
            return None

        arguments = (
            self._build_match_detail_arguments(
                tool_name,
                fixture_id,
                user_message,
            )
        )

        raw_detail = (
            self._execute_mcp_tool(
                tool_name,
                arguments,
            )
        )

        if not isinstance(
            raw_detail,
            dict,
        ):
            return None

        if raw_detail.get(
            "status"
        ) == "error":
            return None

        return self._compact_match_details(
            raw_detail,
            user_message,
        )

    def _retrieve_match_details_for_results(
        self,
        user_message,
        compact_result,
        max_matches=5,
    ):
        """
        Retrieve details for multiple recent matches when the user asks for
        scorers/events across a range such as "last 5 games and scorers".
        """
        if not self._needs_match_details(user_message):
            return []

        requested_count = self._extract_requested_result_count(user_message)
        if requested_count is None:
            return []

        results = compact_result.get("results", []) if isinstance(compact_result, dict) else []
        if not isinstance(results, list):
            return []

        tool_name = self._get_match_detail_tool_name()
        if not tool_name:
            return []

        details = []
        for match in results[: min(requested_count, max_matches)]:
            if not isinstance(match, dict):
                continue

            fixture_id = self._extract_fixture_id(match)
            if fixture_id is None:
                continue

            arguments = self._build_match_detail_arguments(
                tool_name,
                fixture_id,
                user_message,
            )
            raw_detail = self._execute_mcp_tool(tool_name, arguments)
            if not isinstance(raw_detail, dict) or raw_detail.get("status") == "error":
                continue

            compact_detail = self._compact_match_details(
                raw_detail,
                user_message,
            )
            if isinstance(compact_detail, dict):
                details.append((fixture_id, compact_detail))

        return details

    # ------------------------------------------------------------------
    # TOOL RESULT COMPACTION
    # ------------------------------------------------------------------

    def _compact_tool_result(
        self,
        tool_name,
        data,
        user_message=None,
    ):
        """
        Reduce MCP responses before sending them to the LLM.
        """

        if not isinstance(
            data,
            dict,
        ):
            return data

        if data.get(
            "status"
        ) == "error":
            return data

        # --------------------------------------------------------------
        # WATCHLIST
        # --------------------------------------------------------------

        if tool_name == "get_watchlist":
            teams = []

            for team in data.get(
                "teams",
                [],
            ):
                if not isinstance(
                    team,
                    dict,
                ):
                    continue

                teams.append(
                    {
                        "name": team.get(
                            "name"
                        ),
                        "country": team.get(
                            "country"
                        ),
                    }
                )

            return {
                "status": data.get(
                    "status"
                ),
                "teams": teams,
            }

        # --------------------------------------------------------------
        # UPCOMING MATCHES
        # --------------------------------------------------------------

        if tool_name == "get_upcoming_matches":
            fixtures = []

            for fixture in data.get(
                "fixtures",
                [],
            ):
                if not isinstance(
                    fixture,
                    dict,
                ):
                    continue

                fixtures.append(
                    {
                        "fixture_id": (
                            fixture.get(
                                "fixture_id"
                            )
                            or fixture.get(
                                "event_id"
                            )
                            or fixture.get(
                                "match_id"
                            )
                        ),
                        "date": (
                            fixture.get(
                                "local_date"
                            )
                            or fixture.get(
                                "date"
                            )
                        ),
                        "time": fixture.get(
                            "local_time"
                        ),
                        "timezone": fixture.get(
                            "local_timezone"
                        ),
                        "home_team": fixture.get(
                            "home_team"
                        ),
                        "away_team": fixture.get(
                            "away_team"
                        ),
                        "competition": (
                            fixture.get(
                                "competition_display_name"
                            )
                            or fixture.get(
                                "competition_name"
                            )
                        ),
                        "round": fixture.get(
                            "round_label"
                        ),
                    }
                )

            fixtures = fixtures[:8]

            return {
                "status": data.get(
                    "status"
                ),
                "team": data.get(
                    "team"
                ),
                "fixtures": fixtures,
            }

        # --------------------------------------------------------------
        # LIVE MATCHES
        # --------------------------------------------------------------

        if tool_name == "get_live_matches":
            matches = []

            for match in data.get(
                "matches",
                [],
            ):
                if not isinstance(
                    match,
                    dict,
                ):
                    continue

                matches.append(
                    {
                        "fixture_id": (
                            match.get(
                                "fixture_id"
                            )
                            or match.get(
                                "event_id"
                            )
                            or match.get(
                                "match_id"
                            )
                        ),
                        "home_team": match.get(
                            "home_team"
                        ),
                        "away_team": match.get(
                            "away_team"
                        ),
                        "home_score": match.get(
                            "home_score"
                        ),
                        "away_score": match.get(
                            "away_score"
                        ),
                        "status": match.get(
                            "status"
                        ),
                        "minute": match.get(
                            "minute"
                        ),
                        "competition": (
                            match.get(
                                "competition_display_name"
                            )
                            or match.get(
                                "competition_name"
                            )
                        ),
                    }
                )

            matches = matches[:12]

            return {
                "status": data.get(
                    "status"
                ),
                "matches": matches,
            }

        # --------------------------------------------------------------
        # NEWS
        # --------------------------------------------------------------

        if tool_name == "get_team_news":
            articles = []

            for article in data.get(
                "articles",
                [],
            ):
                if not isinstance(
                    article,
                    dict,
                ):
                    continue

                articles.append(
                    {
                        "title": article.get(
                            "title"
                        ),
                        "description": article.get(
                            "description"
                        ),
                        "source": article.get(
                            "source"
                        ),
                        "published_at": article.get(
                            "published_at"
                        ),
                    }
                )

            articles = articles[:6]

            return {
                "status": data.get(
                    "status"
                ),
                "team": data.get(
                    "team"
                ),
                "article_count": data.get(
                    "article_count",
                    len(articles),
                ),
                "articles": articles,
            }

        # --------------------------------------------------------------
        # MANAGER
        # --------------------------------------------------------------

        if tool_name == "get_team_manager":
            manager = (
                data.get("manager")
                or data.get("coach")
                or data.get("head_coach")
            )

            if isinstance(manager, dict):
                compact_manager = {
                    "id": manager.get("id"),
                    "name": (
                        manager.get("name")
                        or manager.get("manager_name")
                        or manager.get("coach_name")
                    ),
                    "image": (
                        manager.get("image")
                        or manager.get("photo")
                        or manager.get("image_url")
                        or manager.get("photo_url")
                    ),
                }
                return {
                    "status": data.get("status"),
                    "team": data.get("team"),
                    "manager": compact_manager,
                }

            return {
                "status": data.get("status"),
                "team": data.get("team"),
                "manager": manager,
            }

        # --------------------------------------------------------------
        # TRANSFERS
        # --------------------------------------------------------------

        if tool_name == "get_team_transfers":
            transfers = data.get("transfers", data.get("items", []))
            if not isinstance(transfers, list):
                transfers = []

            compact_transfers = []
            for transfer in transfers[:12]:
                if not isinstance(transfer, dict):
                    continue

                compact_transfers.append({
                    "player": (
                        transfer.get("player")
                        or transfer.get("player_name")
                    ),
                    "from": (
                        transfer.get("from")
                        or transfer.get("from_team")
                        or transfer.get("source_team")
                    ),
                    "to": (
                        transfer.get("to")
                        or transfer.get("to_team")
                        or transfer.get("destination_team")
                    ),
                    "date": transfer.get("date"),
                    "type": transfer.get("type"),
                })

            return {
                "status": data.get("status"),
                "team": data.get("team"),
                "transfers": compact_transfers,
            }

        # --------------------------------------------------------------
        # TOP SCORERS
        # --------------------------------------------------------------

        if tool_name == "get_top_scorers":
            scorers = data.get(
                "scorers",
                data.get("players", data.get("results", [])),
            )
            if not isinstance(scorers, list):
                scorers = []

            compact_scorers = []
            for scorer in scorers[:10]:
                if not isinstance(scorer, dict):
                    continue

                player = scorer.get("player")
                player_name = (
                    scorer.get("player_name")
                    or scorer.get("name")
                )
                if isinstance(player, dict):
                    player_name = (
                        player.get("name")
                        or player.get("short_name")
                        or player_name
                    )

                compact_scorers.append({
                    "player": player_name,
                    "goals": (
                        scorer.get("goals")
                        if scorer.get("goals") is not None
                        else scorer.get("total")
                    ),
                    "assists": scorer.get("assists"),
                })

            return {
                "status": data.get("status"),
                "team": data.get("team"),
                "scorers": compact_scorers,
            }

        # --------------------------------------------------------------
        # TEAM RESULTS
        # --------------------------------------------------------------

        if tool_name == "get_team_results":
            raw_results = []

            for match in data.get(
                "results",
                [],
            ):
                if not isinstance(
                    match,
                    dict,
                ):
                    continue

                compact_match = {
                    "fixture_id": (
                        match.get(
                            "fixture_id"
                        )
                        or match.get(
                            "event_id"
                        )
                        or match.get(
                            "match_id"
                        )
                    ),
                    "date": (
                        match.get(
                            "local_date"
                        )
                        or match.get(
                            "date"
                        )
                    ),
                    "time": match.get(
                        "local_time"
                    ),
                    "timezone": match.get(
                        "local_timezone"
                    ),
                    "home_team": match.get(
                        "home_team"
                    ),
                    "away_team": match.get(
                        "away_team"
                    ),
                    "home_score": match.get(
                        "home_score"
                    ),
                    "away_score": match.get(
                        "away_score"
                    ),
                    "result": match.get(
                        "result"
                    ),
                    "competition": (
                        match.get(
                            "competition_display_name"
                        )
                        or match.get(
                            "competition_name"
                        )
                    ),
                    "round_label": match.get(
                        "round_label"
                    ),
                }

                for key in (
                    "incidents",
                    "events",
                    "lineups",
                ):
                    value = match.get(
                        key
                    )

                    if value:
                        compact_match[
                            key
                        ] = value

                raw_results.append(
                    compact_match
                )

            results = raw_results

            mentioned_teams = (
                self._extract_mentioned_teams(
                    user_message
                )
                if user_message
                else []
            )

            # ----------------------------------------------------------
            # HEAD-TO-HEAD FILTER
            # ----------------------------------------------------------

            if len(
                mentioned_teams
            ) >= 2:

                team_a = mentioned_teams[0]
                team_b = mentioned_teams[1]

                h2h = []

                for match in results:
                    home = str(
                        match.get(
                            "home_team"
                        )
                        or ""
                    ).lower()

                    away = str(
                        match.get(
                            "away_team"
                        )
                        or ""
                    ).lower()

                    a = team_a.lower()
                    b = team_b.lower()

                    if (
                        (
                            a in home
                            and b in away
                        )
                        or (
                            b in home
                            and a in away
                        )
                    ):
                        h2h.append(
                            match
                        )

                if h2h:
                    results = h2h

            # ----------------------------------------------------------
            # LAST-GAME QUERY
            # ----------------------------------------------------------

            if (
                user_message
                and self._is_last_game_query(
                    user_message
                )
            ):
                results = sorted(
                    results,
                    key=lambda item: (
                        str(
                            item.get(
                                "date"
                            )
                            or ""
                        ),
                        str(
                            item.get(
                                "time"
                            )
                            or ""
                        ),
                    ),
                    reverse=True,
                )

                results = results[:1]

            else:
                results = results[:8]

            team_value = data.get("team")
            if isinstance(team_value, dict):
                # Team IDs are internal identifiers and should never be
                # surfaced to the final answer model/user.
                team_value = {
                    key: value
                    for key, value in team_value.items()
                    if key not in {"id", "team_id"}
                }

            response = {
                "status": data.get(
                    "status"
                ),
                "team": team_value,
                "league_id": data.get(
                    "league_id"
                ),
                "season_id": data.get(
                    "season_id"
                ),
                "count": data.get(
                    "count",
                    len(raw_results),
                ),
                "results": results,
            }

            # get_team_results may already return the exact latest-match
            # detail from BSD. Preserve it instead of dropping it during
            # compaction; this is what carries incidents/scorers forward.
            latest_details = data.get("latest_match_details")
            if isinstance(latest_details, dict):
                compact_latest_details = self._compact_match_details(
                    latest_details,
                    user_message,
                )
                if isinstance(compact_latest_details, dict):
                    response["latest_match_details"] = compact_latest_details

            return response

        # --------------------------------------------------------------
        # MATCH DETAILS
        # --------------------------------------------------------------

        if tool_name in {
            "get_match_details",
            "get_match_detail",
            "get_fixture_details",
            "get_fixture_detail",
        }:
            return self._compact_match_details(
                data,
                user_message,
            )

        # --------------------------------------------------------------
        # LEAGUE STANDINGS
        # --------------------------------------------------------------

        if tool_name == "search_managers":
            managers = []
            for row in data.get("managers", []):
                if isinstance(row, dict):
                    managers.append({"name": row.get("name"), "team": row.get("team_name"), "team_id": row.get("team_id")})
            return {"status": data.get("status"), "query": data.get("query"), "managers": managers}

        if tool_name == "get_player_stats":
            return {
                "status": data.get("status"),
                "player": data.get("player"),
                "team": data.get("team_name"),
                "season_id": data.get("season_id"),
                "stats": data.get("stats", {}),
            }

        if tool_name == "get_league_table":
            rows = []
            for row in data.get("standings", []):
                if not isinstance(row, dict):
                    continue
                rows.append({
                    "position": row.get("position"),
                    "team": row.get("team_name") or row.get("name") or (row.get("team") or {}).get("name") if isinstance(row.get("team"), dict) else row.get("team_name") or row.get("name"),
                    "team_id": row.get("team_id") or row.get("id"),
                    "played": row.get("played") or row.get("matches_played"),
                    "won": row.get("won"),
                    "drawn": row.get("drawn"),
                    "lost": row.get("lost"),
                    "goals_for": row.get("goals_for"),
                    "goals_against": row.get("goals_against"),
                    "points": row.get("points"),
                    "form": row.get("form"),
                })
            return {"status": data.get("status"), "league": data.get("league_name"), "season_id": data.get("season_id"), "standings": rows}

        if tool_name == "get_league_standings":
            team_standing = data.get(
                "team_standing"
            )

            compact_team_standing = None

            if isinstance(
                team_standing,
                dict,
            ):
                compact_team_standing = {
                    "position": team_standing.get(
                        "position"
                    ),
                    "team_name": team_standing.get(
                        "team_name"
                    ),
                    "played": team_standing.get(
                        "played"
                    ),
                    "wins": team_standing.get(
                        "wins"
                    ),
                    "draws": team_standing.get(
                        "draws"
                    ),
                    "losses": team_standing.get(
                        "losses"
                    ),
                    "goals_for": team_standing.get(
                        "goals_for"
                    ),
                    "goals_against": team_standing.get(
                        "goals_against"
                    ),
                    "goal_difference": team_standing.get(
                        "goal_difference"
                    ),
                    "points": team_standing.get(
                        "points"
                    ),
                    "form": team_standing.get(
                        "form"
                    ),
                }

            # A request such as "show standings" needs the table,
            # not only the selected team's row. Keep the table compact
            # enough for Groq while preserving the useful columns.
            compact_standings = []
            raw_standings = data.get(
                "standings",
                [],
            )

            if isinstance(raw_standings, list):
                for row in raw_standings[:30]:
                    if not isinstance(row, dict):
                        continue

                    team_value = (
                        row.get("team")
                        or row.get("club")
                        or row.get("participant")
                    )

                    if isinstance(team_value, dict):
                        team_name_value = (
                            team_value.get("name")
                            or team_value.get("team_name")
                        )
                        team_id_value = (
                            team_value.get("id")
                            or team_value.get("team_id")
                        )
                        logo_value = (
                            team_value.get("logo")
                            or team_value.get("logo_url")
                        )
                    else:
                        team_name_value = (
                            row.get("team_name")
                            or team_value
                            or row.get("name")
                        )
                        team_id_value = (
                            row.get("team_id")
                            or row.get("id")
                        )
                        logo_value = (
                            row.get("logo")
                            or row.get("logo_url")
                        )

                    compact_standings.append({
                        "position": row.get("position"),
                        "team_id": team_id_value,
                        "team_name": team_name_value,
                        "logo": logo_value,
                        "played": row.get("played"),
                        "wins": row.get("wins"),
                        "draws": row.get("draws"),
                        "losses": row.get("losses"),
                        "goals_for": row.get("goals_for"),
                        "goals_against": row.get("goals_against"),
                        "goal_difference": row.get("goal_difference"),
                        "points": row.get("points"),
                        "form": row.get("form"),
                        "zone": row.get("zone"),
                    })

            return {
                "status": data.get(
                    "status"
                ),
                "team": data.get(
                    "team"
                ),
                "league_id": data.get(
                    "league_id"
                ),
                "league_name": data.get(
                    "league_name"
                ),
                "season_id": data.get(
                    "season_id"
                ),
                "team_standing": (
                    compact_team_standing
                ),
                "standings": compact_standings,
                "count": data.get(
                    "count"
                ),
            }

        # --------------------------------------------------------------
        # SQUAD
        # --------------------------------------------------------------

        if tool_name == "get_team_squad":
            players = []

            for player in data.get(
                "players",
                [],
            ):
                if not isinstance(
                    player,
                    dict,
                ):
                    continue

                players.append(
                    {
                        "id": player.get(
                            "id"
                        ),
                        "name": player.get(
                            "name"
                        ),
                        "short_name": player.get(
                            "short_name"
                        ),
                        "position": player.get(
                            "position"
                        ),
                        "jersey_number": (
                            player.get(
                                "jersey_number"
                            )
                            or player.get(
                                "shirt_number"
                            )
                            or player.get(
                                "number"
                            )
                        ),
                        "nationality": player.get(
                            "nationality"
                        ),
                        "availability": player.get(
                            "availability"
                        ),
                        "injury_type": player.get(
                            "injury_type"
                        ),
                        "injury_expected_return": (
                            player.get(
                                "injury_expected_return"
                            )
                        ),
                    }
                )

            return {
                "status": data.get(
                    "status"
                ),
                "team": data.get(
                    "team"
                ),
                "team_id": data.get(
                    "team_id"
                ),
                "player_count": data.get(
                    "player_count",
                    len(players),
                ),
                "players": players,
            }

        return data

    # ------------------------------------------------------------------
    # TOOL CALL DEDUPLICATION
    # ------------------------------------------------------------------

    def _tool_call_signature(
        self,
        tool_name,
        arguments,
    ):
        try:
            encoded = json.dumps(
                arguments,
                sort_keys=True,
                separators=(
                    ",",
                    ":",
                ),
            )

        except Exception:
            encoded = str(
                arguments
            )

        return (
            f"{tool_name}:{encoded}"
        )

    # ------------------------------------------------------------------
    # GROQ RATE LIMIT DETECTION
    # ------------------------------------------------------------------

    def _is_rate_limit_error(
        self,
        exc,
    ):
        status_code = getattr(
            exc,
            "status_code",
            None,
        )

        if status_code in {
            429,
            413,
        }:
            return True

        text_value = str(
            exc
        ).lower()

        return (
            "429" in text_value
            or "413" in text_value
            or "rate limit" in text_value
            or "too many requests"
            in text_value
            or "request too large"
            in text_value
            or "tokens per minute"
            in text_value
        )

    # ------------------------------------------------------------------
    # GROUNDED ANSWER
    # ------------------------------------------------------------------

    def _generate_grounded_answer(
        self,
        user_message,
        tool_results,
    ):
        """
        Generate final answer from compact retrieved sports data.

        No MCP tools are supplied to this final request.
        """

        system_prompt = """
You are SportsIQ, a concise football information assistant.

Answer the user's question using ONLY the retrieved MCP data supplied
below.

Rules:
- Do not invent scores, dates, players, competitions, statistics,
  events, lineups, or facts.
- If the requested information is not present, say so clearly.
- The score fields from retrieved match/result data are valid match
  data and may be used directly in the answer.
- If a detailed match response contains home_team, away_team,
  home_score, away_score, or score, use those fields when answering
  match-result questions.
- For goal-scoring questions, use the retrieved `goal_scorers` list when
  present. Only identify a player as a scorer when the retrieved
  incident/event data explicitly identifies that player as the scorer.
- If `goal_scorers` is present, include the scorer names and minutes when
  available. Do not omit them when the user explicitly asks who scored.
- Do not infer a goal scorer merely from a player's name appearing
  elsewhere in the data.
- For player participation questions, only say that a player played,
  started, was substituted, or was an unused substitute when the
  retrieved lineup/incident data supports it.
- Never mention internal IDs such as fixture_id, event_id, match_id, team_id, league_id, or season_id unless the user explicitly asks for an ID.
- Keep the answer concise.
- For a match-summary question, mention teams, score, competition,
  date, and result when available.
- Do not add predictions unless explicitly requested.
- Do not add generic football commentary.
- If the user explicitly asks to use each/all tools for a team, report the
  retrieved information by tool/category rather than answering from only
  one tool. Do not claim a tool was used unless its result is present.
"""

        compact_payload = json.dumps(
            tool_results,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )

        user_prompt = f"""
User question:
{user_message}

Retrieved sports data:
{compact_payload}

Give the most direct factual answer to the user's question.
"""

        try:
            response = (
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    temperature=0.2,
                    max_tokens=800,
                    reasoning_effort="low",
                )
            )

            content = (
                response.choices[0]
                .message.content
            )

            if content:
                return content.strip()

            return ""

        except Exception as exc:
            if self._is_rate_limit_error(
                exc
            ):
                return None

            return (
                "Unable to generate the final "
                f"response: {exc}"
            )

    # ------------------------------------------------------------------
    # GROUNDED SEASON FALLBACK
    # ------------------------------------------------------------------

    def _build_grounded_season_summary(
        self,
        tool_results,
        user_message,
    ):
        results_data = (
            tool_results.get(
                "get_team_results"
            )
        )

        standings_data = (
            tool_results.get(
                "get_league_standings"
            )
        )

        if not isinstance(
            results_data,
            dict,
        ):
            results_data = {}

        if not isinstance(
            standings_data,
            dict,
        ):
            standings_data = {}

        team = (
            standings_data.get(
                "team"
            )
            or results_data.get(
                "team"
            )
            or {}
        )

        if isinstance(
            team,
            dict,
        ):
            team_name = team.get(
                "name"
            )

        elif isinstance(
            team,
            str,
        ):
            team_name = team

        else:
            team_name = None

        if not team_name:
            team_name = (
                self._infer_team_name(
                    user_message,
                    [],
                )
            )

        team_name = (
            team_name
            or "Team"
        )

        standing = (
            standings_data.get(
                "team_standing"
            )
        )

        results = (
            results_data.get(
                "results",
                [],
            )
        )

        if not isinstance(
            results,
            list,
        ):
            results = []

        wins = 0
        draws = 0
        losses = 0

        goals_for = 0
        goals_against = 0

        actual_form = []

        for match in results:
            if not isinstance(
                match,
                dict,
            ):
                continue

            result = match.get(
                "result"
            )

            if result == "W":
                wins += 1
                actual_form.append(
                    "W"
                )

            elif result == "D":
                draws += 1
                actual_form.append(
                    "D"
                )

            elif result == "L":
                losses += 1
                actual_form.append(
                    "L"
                )

            home_score = match.get(
                "home_score"
            )

            away_score = match.get(
                "away_score"
            )

            try:
                home_score = int(
                    home_score
                )
                away_score = int(
                    away_score
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            home_team = match.get(
                "home_team"
            )

            if home_team == team_name:
                goals_for += (
                    home_score
                )
                goals_against += (
                    away_score
                )

            else:
                goals_for += (
                    away_score
                )
                goals_against += (
                    home_score
                )

        matches_played = (
            wins
            + draws
            + losses
        )

        if isinstance(
            standing,
            dict,
        ):
            if standing.get(
                "played"
            ) is not None:
                matches_played = (
                    standing.get(
                        "played"
                    )
                )

            if standing.get(
                "wins"
            ) is not None:
                wins = standing.get(
                    "wins"
                )

            if standing.get(
                "draws"
            ) is not None:
                draws = standing.get(
                    "draws"
                )

            if standing.get(
                "losses"
            ) is not None:
                losses = standing.get(
                    "losses"
                )

            if standing.get(
                "goals_for"
            ) is not None:
                goals_for = (
                    standing.get(
                        "goals_for"
                    )
                )

            if standing.get(
                "goals_against"
            ) is not None:
                goals_against = (
                    standing.get(
                        "goals_against"
                    )
                )

        goal_difference = (
            goals_for
            - goals_against
        )

        points = None
        position = None

        if isinstance(
            standing,
            dict,
        ):
            points = standing.get(
                "points"
            )
            position = standing.get(
                "position"
            )

        competition_name = None

        for match in results:
            if not isinstance(
                match,
                dict,
            ):
                continue

            competition_name = match.get(
                "competition"
            )

            if competition_name:
                break

        lines = [
            (
                f"**{team_name} – "
                f"Season-to-date summary**"
            ),
            "",
        ]

        if competition_name:
            lines[0] = (
                f"**{team_name} – "
                f"{competition_name} "
                f"season-to-date summary**"
            )

        if matches_played:
            lines.append(
                f"- **Matches played:** "
                f"{matches_played}"
            )

        lines.append(
            f"- **Record:** {wins} wins · "
            f"{draws} draws · "
            f"{losses} losses"
        )

        lines.append(
            f"- **Goals:** {goals_for} scored · "
            f"{goals_against} conceded · "
            f"{goal_difference:+d} goal difference"
        )

        if points is not None:
            if position is not None:
                lines.append(
                    f"- **League position:** "
                    f"{position}th · "
                    f"**{points} points**"
                )
            else:
                lines.append(
                    f"- **Points:** {points}"
                )

        if actual_form:
            lines.append(
                f"- **Recent results:** "
                f"{' '.join(actual_form)}"
            )

        if results:
            lines.extend(
                [
                    "",
                    "**Results:**",
                ]
            )

            for match in reversed(
                results
            ):
                home_team = match.get(
                    "home_team"
                )
                away_team = match.get(
                    "away_team"
                )
                home_score = match.get(
                    "home_score"
                )
                away_score = match.get(
                    "away_score"
                )
                result = match.get(
                    "result"
                )
                date = match.get(
                    "date"
                )

                if (
                    home_team is None
                    or away_team is None
                    or home_score is None
                    or away_score is None
                ):
                    continue

                line = (
                    f"- {home_team} "
                    f"{home_score}–"
                    f"{away_score} "
                    f"{away_team} "
                    f"({result or 'N/A'})"
                )

                if date:
                    line += (
                        f" – {date}"
                    )

                lines.append(
                    line
                )

        return "\n".join(
            lines
        )

    # ------------------------------------------------------------------
    # SPECIALIZED RESULTS FLOW
    # ------------------------------------------------------------------

    def _run_team_results_query(
        self,
        user_message,
    ):
        """
        Dedicated low-token path for result/match-detail questions.

        Flow:

            team name
                 ↓
            get_team_results
                 ↓
            identify one relevant match
                 ↓
            get_match_details (if required)
                 ↓
            compact data
                 ↓
            final Groq answer
        """

        team_name = (
            self._infer_team_name(
                user_message,
                [],
            )
        )

        if not team_name:
            return (
                "Please specify which team "
                "you want the result for."
            )

        raw_result = (
            self._execute_mcp_tool(
                "get_team_results",
                {
                    "team_name": team_name
                },
            )
        )

        compact_result = (
            self._compact_tool_result(
                "get_team_results",
                raw_result,
                user_message,
            )
        )

        if (
            not isinstance(
                compact_result,
                dict,
            )
            or not compact_result.get(
                "results"
            )
        ):
            final_answer = (
                self._generate_grounded_answer(
                    user_message,
                    {
                        "get_team_results": (
                            compact_result
                        )
                    },
                )
            )

            if final_answer:
                return final_answer

            return (
                "I couldn't find a recorded result "
                f"for {team_name}."
            )

        # --------------------------------------------------------------
        # If this is a scorer/lineup/event question, retrieve detailed
        # match data. For "last N" queries, retrieve each requested
        # match instead of only the latest one.
        # --------------------------------------------------------------

        match_details = (
            self._retrieve_match_details_if_needed(
                user_message,
                compact_result,
            )
        )

        multi_match_details = self._retrieve_match_details_for_results(
            user_message,
            compact_result,
            max_matches=5,
        )

        if multi_match_details:
            details_by_fixture = {
                str(fixture_id): detail
                for fixture_id, detail in multi_match_details
            }
            enriched_results = []
            for match in compact_result.get("results", []):
                if not isinstance(match, dict):
                    enriched_results.append(match)
                    continue

                enriched = dict(match)
                fixture_id = self._extract_fixture_id(match)
                detail = details_by_fixture.get(str(fixture_id)) if fixture_id is not None else None
                if isinstance(detail, dict):
                    scorers = detail.get("goal_scorers")
                    if scorers:
                        enriched["goal_scorers"] = scorers
                enriched_results.append(enriched)

            compact_result = dict(compact_result)
            compact_result["results"] = enriched_results

        collected = {
            "get_team_results": compact_result
        }

        # get_team_results can already contain BSD's detailed latest-match
        # payload. Expose that compact detail directly to the final answer.
        latest_details = compact_result.get("latest_match_details")
        if isinstance(latest_details, dict):
            collected["get_match_details"] = latest_details

        if match_details:
            detail_tool_name = (
                self._get_match_detail_tool_name()
                or "get_match_details"
            )

            collected[
                detail_tool_name
            ] = match_details

        final_answer = (
            self._generate_grounded_answer(
                user_message,
                collected,
            )
        )

        if final_answer:
            return final_answer

        # --------------------------------------------------------------
        # Deterministic fallback if Groq is rate limited.
        # --------------------------------------------------------------

        results = compact_result.get(
            "results",
            [],
        )

        if results:
            match = self._select_relevant_match(
                results,
                user_message,
            )

            if match:
                home_team = match.get(
                    "home_team"
                )
                away_team = match.get(
                    "away_team"
                )
                home_score = match.get(
                    "home_score"
                )
                away_score = match.get(
                    "away_score"
                )

                basic_answer = (
                    f"{home_team} "
                    f"{home_score}–"
                    f"{away_score} "
                    f"{away_team}"
                )

                if match.get(
                    "competition"
                ):
                    basic_answer += (
                        f" in "
                        f"{match.get('competition')}"
                    )

                if match.get(
                    "date"
                ):
                    basic_answer += (
                        f" on "
                        f"{match.get('date')}"
                    )

                return (
                    basic_answer
                    + "."
                )

        return (
            "I couldn't generate a response from "
            "the available football data."
        )

    def _run_single_team_tool_query(
        self,
        user_message,
        tool_name,
    ):
        """Execute one deterministic team-specific tool query."""
        team_name = self._infer_team_name(
            user_message,
            [],
        )

        if not team_name:
            return (
                "Please specify which team you want "
                f"information about, or mention the team in "
                f"your question about {tool_name.replace('_', ' ')}."
            )

        raw_result = self._execute_mcp_tool(
            tool_name,
            {"team_name": team_name},
        )

        compact_result = self._compact_tool_result(
            tool_name,
            raw_result,
            user_message,
        )

        return self._generate_grounded_answer(
            user_message,
            {tool_name: compact_result},
        ) or self._format_tool_fallback(
            tool_name,
            compact_result,
            user_message,
        )

    def _format_tool_fallback(
        self,
        tool_name,
        data,
        user_message,
    ):
        """Small deterministic fallbacks when Groq cannot synthesize."""
        if not isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False)

        if data.get("status") == "error":
            return (
                f"I couldn't retrieve that information: "
                f"{data.get('error', 'unknown error')}"
            )

        if tool_name == "get_league_standings":
            standing = data.get("team_standing")
            if isinstance(standing, dict):
                team = standing.get("team_name") or data.get("team") or "Team"
                pos = standing.get("position")
                points = standing.get("points")
                if pos is not None:
                    answer = f"{team} are {pos} in the current {data.get('league_name') or 'league'} standings"
                    if points is not None:
                        answer += f" with {points} points"
                    return answer + "."

        if tool_name == "get_team_squad":
            players = data.get("players", [])
            if self._is_contextual_followup(user_message):
                import re as _re
                number_match = _re.search(
                    r"(?:number|no\.?|shirt|jersey)\s*(\d+)",
                    (user_message or "").lower(),
                )
                if number_match:
                    number = int(number_match.group(1))
                    for player in players:
                        if isinstance(player, dict):
                            value = (
                                player.get("jersey_number")
                                or player.get("shirt_number")
                                or player.get("number")
                            )
                            try:
                                if int(value) == number:
                                    return (
                                        f"{player.get('name') or 'Unknown player'} "
                                        f"wears number {number} for "
                                        f"{data.get('team') or 'the team'}."
                                    )
                            except (TypeError, ValueError):
                                pass

        return json.dumps(data, ensure_ascii=False, default=str)

    def _run_team_overview_query(self, user_message):
        """Build a compact, grounded team snapshot for 'all info' questions."""
        team_name = self._infer_team_name(user_message, [])

        if not team_name:
            return (
                "Tell me which team you want the full SportIQ "
                "overview for."
            )

        collected = {}

        for tool_name in self.TEAM_OVERVIEW_TOOLS:
            if not self._has_mcp_tool(tool_name):
                continue

            raw_result = self._execute_mcp_tool(
                tool_name,
                {"team_name": team_name},
            )

            collected[tool_name] = self._compact_tool_result(
                tool_name,
                raw_result,
                user_message,
            )

        final_answer = self._generate_grounded_answer(
            user_message,
            collected,
        )

        if final_answer:
            return final_answer

        # Avoid dumping raw API payloads to the user.
        available = [
            name for name, result in collected.items()
            if isinstance(result, dict)
            and result.get("status") == "success"
        ]

        if available:
            return (
                f"I retrieved the available SportIQ data for "
                f"{team_name}: " + ", ".join(
                    name.replace("get_team_", "").replace(
                        "get_league_", ""
                    ).replace("_", " ")
                    for name in available
                ) + "."
            )

        return (
            f"I couldn't retrieve the current SportIQ data for {team_name}."
        )

    # ------------------------------------------------------------------
    # MAIN AGENT
    # ------------------------------------------------------------------

    def run_agent(
        self,
        user_message,
    ):
        """
        Run the SportsIQ agent.

        Specialized queries use a lightweight architecture.
        """

        if self.user_id is not None:
            set_current_user_id(
                self.user_id
            )

        # Remember explicitly mentioned teams so natural follow-ups
        # such as "can you provide standings?" remain contextual.
        mentioned_teams = self._remember_teams(
            user_message
        )

        # --------------------------------------------------------------
        # TEAM OVERVIEW / CONTEXTUAL FOLLOW-UP
        # --------------------------------------------------------------

        if self._is_team_overview_query(user_message):
            return self._run_team_overview_query(
                user_message
            )

        # --------------------------------------------------------------
        # SEASON SUMMARY
        # --------------------------------------------------------------

        if self._is_season_summary_query(
            user_message
        ):
            team_name = (
                self._infer_team_name(
                    user_message,
                    [],
                )
            )

            if not team_name:
                return (
                    "Please specify which team "
                    "you want a season summary for."
                )

            collected_tool_results = {}

            for tool_name in (
                "get_team_results",
                "get_league_standings",
            ):
                arguments = {
                    "team_name": team_name
                }

                raw_result = (
                    self._execute_mcp_tool(
                        tool_name,
                        arguments,
                    )
                )

                compact_result = (
                    self._compact_tool_result(
                        tool_name,
                        raw_result,
                        user_message,
                    )
                )

                collected_tool_results[
                    tool_name
                ] = compact_result

            final_answer = (
                self._generate_grounded_answer(
                    user_message,
                    collected_tool_results,
                )
            )

            if final_answer:
                return final_answer

            return (
                self._build_grounded_season_summary(
                    collected_tool_results,
                    user_message,
                )
            )

        # --------------------------------------------------------------
        # RESULT / MATCH DETAIL SPECIALIZED PATH
        # --------------------------------------------------------------

        if (
            "get_team_results"
            in [
                tool.get(
                    "function",
                    {},
                ).get(
                    "name"
                )
                for tool in self._get_tools_for_query(
                    user_message
                )
            ]
            and self._extract_mentioned_teams(
                user_message
            )
        ):
            return self._run_team_results_query(
                user_message
            )

        # --------------------------------------------------------------
        # OTHER SPECIALIZED SINGLE-TOOL QUERY
        # --------------------------------------------------------------

        available_tools = (
            self._get_tools_for_query(
                user_message
            )
        )

        available_tool_names = [
            tool.get(
                "function",
                {},
            ).get(
                "name"
            )
            for tool in available_tools
        ]

        if (
            len(
                available_tool_names
            ) == 1
            and available_tool_names[0]
            in {
                "get_upcoming_matches",
                "get_live_matches",
                "get_team_news",
                "get_team_squad",
                "get_team_manager",
                "get_team_transfers",
                "get_top_scorers",
                "get_league_standings",
                "search_managers",
                "get_player_stats",
                "get_league_table",
            }
        ):
            tool_name = (
                available_tool_names[0]
            )

            arguments = {}

            if tool_name in (
                self.TEAM_SPECIFIC_TOOLS
            ):
                team_name = (
                    self._infer_team_name(
                        user_message,
                        [],
                    )
                )

                if team_name:
                    arguments[
                        "team_name"
                    ] = team_name

            raw_result = (
                self._execute_mcp_tool(
                    tool_name,
                    arguments,
                )
            )

            compact_result = (
                self._compact_tool_result(
                    tool_name,
                    raw_result,
                    user_message,
                )
            )

            collected_tool_results = {
                tool_name: compact_result
            }

            final_answer = (
                self._generate_grounded_answer(
                    user_message,
                    collected_tool_results,
                )
            )

            if final_answer:
                return final_answer

            return json.dumps(
                compact_result,
                ensure_ascii=False,
            )

        # --------------------------------------------------------------
        # MANAGER / PLAYER / LEAGUE SPECIALIZED PATHS
        # --------------------------------------------------------------

        tool_names = [
            tool.get("function", {}).get("name")
            for tool in self._get_tools_for_query(user_message)
        ]

        if len(tool_names) == 1 and tool_names[0] == "search_managers":
            manager_name = self._infer_manager_name(user_message)
            if manager_name:
                raw_result = self._execute_mcp_tool("search_managers", {"manager_name": manager_name})
                compact_result = self._compact_tool_result("search_managers", raw_result, user_message)
                answer = self._generate_grounded_answer(user_message, {"search_managers": compact_result})
                return answer or json.dumps(compact_result, ensure_ascii=False)

        if len(tool_names) == 1 and tool_names[0] == "get_player_stats":
            player_name = self._infer_player_name(user_message)
            if player_name:
                raw_result = self._execute_mcp_tool("get_player_stats", {"player_name": player_name})
                compact_result = self._compact_tool_result("get_player_stats", raw_result, user_message)
                answer = self._generate_grounded_answer(user_message, {"get_player_stats": compact_result})
                return answer or json.dumps(compact_result, ensure_ascii=False)

        if len(tool_names) == 1 and tool_names[0] == "get_league_table":
            league = self._infer_league(user_message)
            if league:
                league_id, league_name = league
                raw_result = self._execute_mcp_tool("get_league_table", {"league_id": league_id, "league_name": league_name})
                compact_result = self._compact_tool_result("get_league_table", raw_result, user_message)
                answer = self._generate_grounded_answer(user_message, {"get_league_table": compact_result})
                return answer or json.dumps(compact_result, ensure_ascii=False)

        # --------------------------------------------------------------
        # BROAD / AMBIGUOUS QUERY
        # --------------------------------------------------------------

        system_prompt = """
You are SportsIQ, a football information assistant.

Use MCP tools as the source of truth.

Rules:
- Do not invent football data.
- Do not invent scores, dates, fixtures, players, standings, news,
  or statistics.
- Use only retrieved MCP information.
- Stop once enough information is available.
- Do not repeatedly call the same tool with identical arguments.
- Keep the final answer concise and factual.
"""

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]

        executed_calls = set()
        collected_tool_results = {}

        for _ in range(
            self.MAX_AGENT_ITERATIONS
        ):
            try:
                response = (
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=available_tools,
                        tool_choice="auto",
                        temperature=0.2,
                        max_tokens=700,
                        reasoning_effort="low",
                    )
                )

            except Exception as exc:
                if self._is_rate_limit_error(
                    exc
                ):
                    if collected_tool_results:
                        final_answer = (
                            self._generate_grounded_answer(
                                user_message,
                                collected_tool_results,
                            )
                        )

                        if final_answer:
                            return final_answer

                    return (
                        "Groq rate limit reached while "
                        "processing the request. "
                        "Please try again shortly."
                    )

                return {
                    "status": "error",
                    "error": str(exc),
                }

            message = (
                response.choices[0].message
            )

            tool_calls = getattr(
                message,
                "tool_calls",
                None,
            )

            if not tool_calls:
                content = getattr(
                    message,
                    "content",
                    None,
                )

                if content:
                    return content.strip()

                break

            for tool_call in tool_calls:
                function = (
                    tool_call.function
                )

                tool_name = (
                    function.name
                )

                try:
                    arguments = json.loads(
                        function.arguments
                        or "{}"
                    )

                except json.JSONDecodeError:
                    arguments = {}

                arguments = (
                    self._repair_tool_arguments(
                        tool_name,
                        arguments,
                        user_message,
                        messages,
                    )
                )

                signature = (
                    self._tool_call_signature(
                        tool_name,
                        arguments,
                    )
                )

                if signature in executed_calls:
                    continue

                executed_calls.add(
                    signature
                )

                raw_result = (
                    self._execute_mcp_tool(
                        tool_name,
                        arguments,
                    )
                )

                compact_result = (
                    self._compact_tool_result(
                        tool_name,
                        raw_result,
                        user_message,
                    )
                )

                collected_tool_results[
                    tool_name
                ] = compact_result

            if collected_tool_results:
                final_answer = (
                    self._generate_grounded_answer(
                        user_message,
                        collected_tool_results,
                    )
                )

                if final_answer:
                    return final_answer

                break

        if collected_tool_results:
            return json.dumps(
                collected_tool_results,
                ensure_ascii=False,
            )

        return (
            "I couldn't generate a response from "
            "the available football data."
        )

    # ------------------------------------------------------------------
    # SIMPLE TEXT GENERATION
    # ------------------------------------------------------------------

    def _generate(
        self,
        system_prompt,
        user_prompt,
    ):
        try:
            response = (
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    temperature=0.3,
                    max_tokens=800,
                    reasoning_effort="low",
                )
            )

            content = (
                response.choices[0]
                .message.content
            )

            if not content:
                return ""

            return content.strip()

        except Exception as exc:
            if self._is_rate_limit_error(
                exc
            ):
                return (
                    "Groq rate limit reached while "
                    "generating the response. "
                    "Please try again shortly."
                )

            return (
                f"Unable to generate response: {exc}"
            )

    # ------------------------------------------------------------------
    # MATCH ANALYSIS
    # ------------------------------------------------------------------

    def analyze_match(
        self,
        match_data,
    ):
        system_prompt = """
You are a football match analyst.

Analyze only the match information supplied by the user.

Do not invent:
- statistics
- player performances
- injuries
- tactics
- events
- historical context
- predictions

If something is not present in the supplied data, do not claim it.

Keep the response concise and useful.
"""

        user_prompt = f"""
Analyze this football match:

{json.dumps(
    match_data,
    ensure_ascii=False,
    indent=2,
)}
"""

        return self._generate(
            system_prompt,
            user_prompt,
        )

    # ------------------------------------------------------------------
    # NEWS ANALYSIS
    # ------------------------------------------------------------------

    def analyze_news(
        self,
        articles,
    ):
        system_prompt = """
You are a football news analyst.

Use only the supplied articles.

Do not invent:
- facts
- quotes
- events
- transfer information
- injuries
- opinions attributed to people who are not quoted or described
  in the supplied articles.

Clearly distinguish reported information from interpretation.

Keep the response concise.
"""

        user_prompt = f"""
Analyze these football news articles:

{json.dumps(
    articles,
    ensure_ascii=False,
    indent=2,
)}
"""

        return self._generate(
            system_prompt,
            user_prompt,
        )

    # ------------------------------------------------------------------
    # BRIEFING GENERATION
    # ------------------------------------------------------------------

    def generate_briefing(
        self,
        team_name,
        upcoming_matches,
        news,
        recent_results=None,
    ):
        system_prompt = """
You are SportsIQ generating a concise football briefing.

Use ONLY the data supplied by the application.

Do not invent:
- fixtures
- scores
- news
- injuries
- transfers
- player information
- predictions
- standings
- statistics

If a section has no data, simply state that the information is
currently unavailable.

Avoid unsupported evaluative language.

Structure the briefing clearly.
"""

        payload = {
            "team": team_name,
            "upcoming_matches": upcoming_matches,
            "recent_results": (
                recent_results or []
            ),
            "news": news,
        }

        user_prompt = f"""
Generate a concise football briefing for {team_name}.

Data:

{json.dumps(
    payload,
    ensure_ascii=False,
    indent=2,
)}
"""

        return self._generate(
            system_prompt,
            user_prompt,
        )
