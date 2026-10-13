"""Downloads the Eurojackpot results file from allwyn.gr and installs it in the app."""
from lottery.config import EUROJACKPOT
from lottery.pipeline import run

if __name__ == "__main__":
    raise SystemExit(run(EUROJACKPOT))
