import sys
import io
import contextlib
import pandas as pd
import matplotlib.pyplot as plt
from src.core.database import upsert_variable, load_all_variables
import numpy as np


class CodeExecutor:
    def __init__(self):
        self.globals = {}
        # Pre-import common libraries
        self.execute("import pandas as pd")
        self.execute("import numpy as np")
        self.execute("import matplotlib.pyplot as plt")
        self._restore_variables()

    def _restore_variables(self):
        saved = load_all_variables()
        # Put restored objects into the same runtime namespace
        self.globals.update(saved)

    def _persist_user_variables(self):
        """
        Save user-created variables from self.globals into database using pickle.
        """
        SKIP = {"pd", "np", "plt", "io", "sys", "contextlib"}

        for name, value in self.globals.items():
            # Skip internal names and libraries
            if name.startswith("_") or name in SKIP:
                continue

            # Skip functions/classes/modules
            if callable(value):
                continue

            metadata = {}

            # Optional metadata for debugging
            try:
                if isinstance(value, pd.DataFrame):
                    metadata = {
                        "shape": list(value.shape),
                        "columns": list(value.columns),
                    }
                elif isinstance(value, pd.Series):
                    metadata = {"shape": list(value.shape)}
                elif isinstance(value, (list, dict, set, tuple)):
                    metadata = {"len": len(value)}
            except Exception:
                metadata = {}

            try:
                upsert_variable(name, value, metadata)
            except Exception:
                # If something cannot be pickled, skip it
                pass

    def execute(self, code):
        """
        Executes the provided Python code and captures the output.
        Returns a dictionary containing the output and the current state of variables.
        """
        # Capture stdout and stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with (
            contextlib.redirect_stdout(stdout_capture),
            contextlib.redirect_stderr(stderr_capture),
        ):
            try:
                exec(code, self.globals)
                output = stdout_capture.getvalue()
                error = stderr_capture.getvalue()
            except Exception as e:
                output = stdout_capture.getvalue()
                error = str(e)

        # specific output logic
        pass
        if error:
            output += f"\nError: {error}"

        self._persist_user_variables()  ## v1.1 persistance after each execution
        # Extract variable summary
        variables = self._get_variable_summary()

        return {"output": output.strip(), "variables": variables}

    def _get_variable_summary(self):
        """
        Extracts a summary of the defined variables.
        """
        summary = {}
        for name, value in self.globals.items():
            if name.startswith("_") or name in [
                "pd",
                "np",
                "plt",
                "io",
                "sys",
                "contextlib",
            ]:
                continue

            type_name = type(value).__name__
            info = str(value)[:50]  # Truncate long values

            if isinstance(value, pd.DataFrame):
                info = f"DataFrame shape: {value.shape}, Columns: {list(value.columns)}"
            elif isinstance(value, pd.Series):
                info = f"Series shape: {value.shape}"

            summary[name] = {"type": type_name, "info": info}
        return summary


if __name__ == "__main__":
    executor = CodeExecutor()
    result = executor.execute(
        "print('Hello, World!')\nx = 10\ndf = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})"
    )
    print("Output:", result["output"])
    print("Variables:", result["variables"])
