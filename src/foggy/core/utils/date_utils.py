"""Date utilities for Foggy Framework."""

from datetime import date, datetime, timedelta
from typing import Optional, Union


class DateUtils:
    """Date utility functions."""

    # Common date formats
    DATE_FORMAT = "%Y-%m-%d"
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    DATETIME_MS_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
    ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"
    COMPACT_FORMAT = "%Y%m%d"

    @staticmethod
    def now() -> datetime:
        """Get current datetime."""
        return datetime.now()

    @staticmethod
    def today() -> date:
        """Get current date."""
        return date.today()

    @staticmethod
    def format_date(d: Union[date, datetime], fmt: Optional[str] = None) -> str:
        """Format date to string.

        Args:
            d: Date or datetime object
            fmt: Format string (default: DATE_FORMAT)

        Returns:
            Formatted date string
        """
        fmt = fmt or DateUtils.DATE_FORMAT
        return d.strftime(fmt)

    @staticmethod
    def format_datetime(dt: datetime, fmt: Optional[str] = None) -> str:
        """Format datetime to string.

        Args:
            dt: Datetime object
            fmt: Format string (default: DATETIME_FORMAT)

        Returns:
            Formatted datetime string
        """
        fmt = fmt or DateUtils.DATETIME_FORMAT
        return dt.strftime(fmt)

    @staticmethod
    def parse_date(s: str, fmt: Optional[str] = None) -> date:
        """Parse string to date.

        Args:
            s: Date string
            fmt: Format string (default: DATE_FORMAT)

        Returns:
            Date object
        """
        fmt = fmt or DateUtils.DATE_FORMAT
        return datetime.strptime(s, fmt).date()

    @staticmethod
    def parse_datetime(s: str, fmt: Optional[str] = None) -> datetime:
        """Parse string to datetime.

        Args:
            s: Datetime string
            fmt: Format string (default: DATETIME_FORMAT)

        Returns:
            Datetime object
        """
        fmt = fmt or DateUtils.DATETIME_FORMAT
        return datetime.strptime(s, fmt)

    @staticmethod
    def add_days(d: Union[date, datetime], days: int) -> Union[date, datetime]:
        """Add days to date/datetime.

        Args:
            d: Date or datetime object
            days: Number of days to add (negative to subtract)

        Returns:
            New date or datetime object
        """
        return d + timedelta(days=days)

    @staticmethod
    def add_months(d: Union[date, datetime], months: int) -> Union[date, datetime]:
        """Add months to date/datetime.

        Args:
            d: Date or datetime object
            months: Number of months to add (negative to subtract)

        Returns:
            New date or datetime object
        """
        year = d.year + (d.month + months - 1) // 12
        month = (d.month + months - 1) % 12 + 1
        day = min(d.day, DateUtils._days_in_month(year, month))

        if isinstance(d, datetime):
            return datetime(year, month, day, d.hour, d.minute, d.second, d.microsecond)
        return date(year, month, day)

    @staticmethod
    def _days_in_month(year: int, month: int) -> int:
        """Get number of days in a month."""
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        return (next_month - timedelta(days=1)).day

    @staticmethod
    def days_between(start: Union[date, datetime], end: Union[date, datetime]) -> int:
        """Calculate days between two dates.

        Args:
            start: Start date
            end: End date

        Returns:
            Number of days (positive if end > start)
        """
        if isinstance(start, datetime):
            start = start.date()
        if isinstance(end, datetime):
            end = end.date()
        return (end - start).days

    @staticmethod
    def is_weekend(d: Union[date, datetime]) -> bool:
        """Check if date is weekend (Saturday or Sunday)."""
        return d.weekday() >= 5

    @staticmethod
    def start_of_month(d: Union[date, datetime]) -> Union[date, datetime]:
        """Get start of month for given date."""
        if isinstance(d, datetime):
            return datetime(d.year, d.month, 1)
        return date(d.year, d.month, 1)

    @staticmethod
    def end_of_month(d: Union[date, datetime]) -> Union[date, datetime]:
        """Get end of month for given date."""
        year = d.year
        month = d.month
        day = DateUtils._days_in_month(year, month)
        if isinstance(d, datetime):
            return datetime(year, month, day, 23, 59, 59)
        return date(year, month, day)

    @staticmethod
    def start_of_year(d: Union[date, datetime]) -> Union[date, datetime]:
        """Get start of year for given date."""
        if isinstance(d, datetime):
            return datetime(d.year, 1, 1)
        return date(d.year, 1, 1)

    @staticmethod
    def end_of_year(d: Union[date, datetime]) -> Union[date, datetime]:
        """Get end of year for given date."""
        if isinstance(d, datetime):
            return datetime(d.year, 12, 31, 23, 59, 59)
        return date(d.year, 12, 31)

    @staticmethod
    def to_iso_string(dt: Union[date, datetime]) -> str:
        """Convert to ISO format string."""
        if isinstance(dt, datetime):
            return dt.isoformat()
        return dt.isoformat()

    @staticmethod
    def from_iso_string(s: str) -> Union[date, datetime]:
        """Parse ISO format string."""
        # Try datetime first
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return date.fromisoformat(s)