"""Built-in Console global for FSScript.

Provides console output functions for debugging and logging.
"""

from typing import Any, Dict, Optional
import sys
from datetime import datetime


class ConsoleGlobal:
    """Built-in console utilities for FSScript.

    Provides functions for output and logging similar to JavaScript console.
    """

    def __init__(self, output: Optional[Any] = None, prefix: str = ""):
        """Initialize console.

        Args:
            output: Output stream (default: sys.stdout)
            prefix: Optional prefix for all messages
        """
        self._output = output or sys.stdout
        self._prefix = prefix
        self._history: list = []

    def _format_value(self, value: Any) -> str:
        """Format a value for output.

        Args:
            value: Value to format

        Returns:
            Formatted string
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, str):
            return value
        elif isinstance(value, (list, dict)):
            import json
            try:
                return json.dumps(value, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                return str(value)
        else:
            return str(value)

    def _write(self, level: str, *args: Any) -> None:
        """Write to output with level.

        Args:
            level: Log level
            *args: Values to log
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_args = " ".join(self._format_value(arg) for arg in args)
        message = f"[{timestamp}] [{level}] {self._prefix}{formatted_args}\n"

        self._history.append({
            "timestamp": timestamp,
            "level": level,
            "message": formatted_args,
        })

        self._output.write(message)
        self._output.flush()

    def log(self, *args: Any) -> None:
        """Log a message.

        Args:
            *args: Values to log
        """
        self._write("LOG", *args)

    def info(self, *args: Any) -> None:
        """Log an info message.

        Args:
            *args: Values to log
        """
        self._write("INFO", *args)

    def warn(self, *args: Any) -> None:
        """Log a warning message.

        Args:
            *args: Values to log
        """
        self._write("WARN", *args)

    def error(self, *args: Any) -> None:
        """Log an error message.

        Args:
            *args: Values to log
        """
        # Write to stderr for errors
        import sys
        original_output = self._output
        self._output = sys.stderr
        self._write("ERROR", *args)
        self._output = original_output

    def debug(self, *args: Any) -> None:
        """Log a debug message.

        Args:
            *args: Values to log
        """
        self._write("DEBUG", *args)

    def trace(self, *args: Any) -> None:
        """Log with stack trace.

        Args:
            *args: Values to log
        """
        import traceback
        self._write("TRACE", *args)
        self._output.write(traceback.format_stack()[-2])
        self._output.flush()

    def table(self, data: Any) -> None:
        """Log data as a table.

        Args:
            data: Data to display (list of dicts or dict of dicts)
        """
        if isinstance(data, list):
            if not data:
                self.log("[]")
                return
            if isinstance(data[0], dict):
                # Table from list of dicts
                headers = list(data[0].keys())
                header_str = " | ".join(headers)
                separator = "-+-".join("-" * len(h) for h in headers)

                self.log(header_str)
                self.log(separator)
                for row in data:
                    row_str = " | ".join(str(row.get(h, "")) for h in headers)
                    self.log(row_str)
            else:
                # Simple list
                for i, item in enumerate(data):
                    self.log(f"{i}: {item}")
        elif isinstance(data, dict):
            for key, value in data.items():
                self.log(f"{key}: {self._format_value(value)}")
        else:
            self.log(data)

    def time(self, label: str = "default") -> None:
        """Start a timer.

        Args:
            label: Timer label
        """
        if not hasattr(self, "_timers"):
            self._timers = {}
        self._timers[label] = datetime.now()

    def time_end(self, label: str = "default") -> Optional[float]:
        """End a timer and log elapsed time.

        Args:
            label: Timer label

        Returns:
            Elapsed time in milliseconds
        """
        if not hasattr(self, "_timers"):
            self._timers = {}

        if label not in self._timers:
            self.warn(f"Timer '{label}' does not exist")
            return None

        elapsed = (datetime.now() - self._timers[label]).total_seconds() * 1000
        del self._timers[label]
        self.log(f"{label}: {elapsed:.2f}ms")
        return elapsed

    def count(self, label: str = "default") -> int:
        """Increment and log a counter.

        Args:
            label: Counter label

        Returns:
            Counter value
        """
        if not hasattr(self, "_counters"):
            self._counters = {}

        self._counters[label] = self._counters.get(label, 0) + 1
        self.log(f"{label}: {self._counters[label]}")
        return self._counters[label]

    def count_reset(self, label: str = "default") -> None:
        """Reset a counter.

        Args:
            label: Counter label
        """
        if not hasattr(self, "_counters"):
            self._counters = {}

        self._counters[label] = 0
        self.log(f"{label}: 0")

    def clear(self) -> None:
        """Clear the console (if supported)."""
        self._history.clear()
        # Try to clear terminal
        try:
            import os
            os.system("clear" if os.name == "posix" else "cls")
        except Exception:
            pass

    def dir(self, obj: Any) -> None:
        """Log object properties.

        Args:
            obj: Object to inspect
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                self.log(f"  {key}: {self._format_value(value)}")
        elif hasattr(obj, "__dict__"):
            for key, value in obj.__dict__.items():
                if not key.startswith("_"):
                    self.log(f"  {key}: {self._format_value(value)}")
        else:
            self.log(obj)

    def assert_(self, condition: bool, *args: Any) -> None:
        """Assert a condition and log if false.

        Args:
            condition: Condition to check
            *args: Message if assertion fails
        """
        if not condition:
            self.error("Assertion failed:", *args)

    def get_history(self) -> list:
        """Get console history.

        Returns:
            List of logged messages
        """
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear console history."""
        self._history.clear()

    def get_functions(self) -> Dict[str, Any]:
        """Get all console functions as dictionary.

        Returns:
            Dictionary of function name to function
        """
        return {
            "log": self.log,
            "info": self.info,
            "warn": self.warn,
            "error": self.error,
            "debug": self.debug,
            "trace": self.trace,
            "table": self.table,
            "time": self.time,
            "timeEnd": self.time_end,
            "count": self.count,
            "countReset": self.count_reset,
            "clear": self.clear,
            "dir": self.dir,
            "assert": self.assert_,
        }


__all__ = ["ConsoleGlobal"]