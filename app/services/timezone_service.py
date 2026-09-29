import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


class TimezoneService:
    WINDOWS_TIMEZONE_MAP = {
        "Pakistan Standard Time": "Asia/Karachi",
        "India Standard Time": "Asia/Kolkata",
        "GMT Standard Time": "Europe/London",
        "W. Europe Standard Time": "Europe/Berlin",
        "Eastern Standard Time": "America/New_York",
        "Central Standard Time": "America/Chicago",
        "Mountain Standard Time": "America/Denver",
        "Pacific Standard Time": "America/Los_Angeles",
        "Tokyo Standard Time": "Asia/Tokyo",
        "China Standard Time": "Asia/Shanghai",
        "AUS Eastern Standard Time": "Australia/Sydney",
    }

    def __init__(self):
        self.timezone_name = self.get_local_timezone()
        self.timezone = ZoneInfo(self.timezone_name)

    def get_local_timezone(self):
        """
        Detect the machine's local timezone.

        Priority:
        1. TZ environment variable
        2. Windows timezone registry
        3. System datetime timezone information
        4. UTC fallback
        """

        # 1. Explicit TZ environment variable
        tz_env = os.getenv("TZ")

        if tz_env:
            try:
                ZoneInfo(tz_env)
                return tz_env
            except Exception:
                pass

        # 2. Windows timezone detection
        if os.name == "nt":
            try:
                import winreg

                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation",
                )

                standard_name, _ = winreg.QueryValueEx(
                    key,
                    "TimeZoneKeyName",
                )

                if standard_name in self.WINDOWS_TIMEZONE_MAP:
                    return self.WINDOWS_TIMEZONE_MAP[standard_name]

            except Exception:
                pass

        # 3. Try to obtain timezone from the system datetime
        try:
            local_datetime = datetime.now().astimezone()
            tz_name = local_datetime.tzinfo.tzname(local_datetime)

            if tz_name:
                try:
                    ZoneInfo(tz_name)
                    return tz_name
                except Exception:
                    pass

        except Exception:
            pass

        # 4. Safe fallback
        return "UTC"

    def get_timezone_name(self):
        return self.timezone_name

    def convert_utc_to_local(self, dt):
        """
        Convert a UTC datetime to the user's local timezone.
        """

        if dt is None:
            return None

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(self.timezone)

    def format_datetime(self, dt, format_string="%Y-%m-%d %I:%M %p"):
        """
        Convert a datetime to local time and format it for display.
        """

        if dt is None:
            return ""

        local_dt = self.convert_utc_to_local(dt)

        return local_dt.strftime(format_string)