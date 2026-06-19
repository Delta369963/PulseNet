import asyncio
from app.db.session import session_scope
from app.services.ripple_service import _build_exposures, _generate_reroutes
from app.db import repo

def test():
    with session_scope() as s:
        # Get shock UKR conflict we modified
        shock = repo.shock_by_external_id(s, "c19edf36a38851d26594fbf65fca")
        if not shock:
            print("No shock")
            return
        print(shock)

if __name__ == "__main__":
    test()
