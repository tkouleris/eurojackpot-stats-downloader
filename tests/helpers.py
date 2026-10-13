import zipfile
from pathlib import Path


def write_xlsx(path: Path) -> Path:
    """Writes a minimal zip file, which is all is_valid_xlsx checks."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    return path


def enter(test, context_manager):
    """TestCase.enterContext for Python 3.10."""
    result = context_manager.__enter__()
    test.addCleanup(context_manager.__exit__, None, None, None)
    return result
