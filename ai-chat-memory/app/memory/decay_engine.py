from datetime import datetime

from app.db.postgres import PostgresDB
from app.db.vector_store import vector_store


class DecayEngine:

    def __init__(self, db: PostgresDB):
        self.db = db

    async def run_cycle(self):
        all_facts = await self.db.get_all_facts_for_decay()
        for fact in all_facts:
            days_since_access = (datetime.now() - fact.last_accessed).days
            new_decay = fact.decay_score * (0.95 ** max(days_since_access, 0))
            if new_decay < 0.1:
                await self.db.archive_fact(fact.id)
                await vector_store.delete(str(fact.id))
            else:
                await self.db.update_decay_score(fact.id, new_decay)
