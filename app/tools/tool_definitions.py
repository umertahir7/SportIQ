TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_watchlist",
            "description": (
                "Get the football teams currently followed "
                "by the user."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_matches",
            "description": (
                "Get upcoming football fixtures for a team "
                "currently followed by the user. "
                "Provide the team name, such as Real Madrid, "
                "Chelsea, or Al Nassr."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": (
                            "Name of the team whose upcoming "
                            "fixtures should be retrieved."
                        ),
                    },
                    "league_id": {
                        "type": "integer",
                        "description": (
                            "Optional KickoffAPI league ID."
                        ),
                    },
                },
                "required": ["team_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_live_matches",
            "description": (
                "Get currently live football matches."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_team_news",
            "description": (
                "Get relevant football news for a specific team."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": (
                            "The football team to search news for."
                        ),
                    },
                },
                "required": ["team_name"],
            },
        },
    },
]