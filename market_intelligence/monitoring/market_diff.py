"""Market Diff — сравнение снимков рынка и обнаружение изменений."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class MarketSnapshot:
    """Снимок рынка на конкретную дату."""

    def __init__(self, label: str = ""):
        self.label = label or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.entities: dict[str, dict] = {}
        self.evidence: list[dict] = []
        self.opportunities: list[dict] = []
        self.leads: list[dict] = []

    def load(self, path: Path):
        """Загрузить снимок из директории."""
        for fname, attr in [("entities.json","entities"),("evidence.json","evidence"),
                            ("opportunities.json","opportunities"),("leads.json","leads")]:
            fp = path / fname
            if fp.exists():
                with open(fp) as f:
                    data = json.load(f)
                if attr == "entities":
                    self.entities = {e["id"]: e for e in data}
                else:
                    setattr(self, attr, data)

    def save(self, path: Path):
        """Сохранить снимок в директорию."""
        path.mkdir(parents=True, exist_ok=True)
        with open(path / "entities.json","w") as f:
            json.dump(list(self.entities.values()), f, ensure_ascii=False, indent=2, default=str)
        for attr in ["evidence","opportunities","leads"]:
            with open(path / f"{attr}.json","w") as f:
                json.dump(getattr(self, attr), f, ensure_ascii=False, indent=2, default=str)


class MarketDiff:
    """Разница между двумя снимками рынка."""

    def __init__(self, v1: MarketSnapshot, v2: MarketSnapshot):
        self.v1 = v1
        self.v2 = v2

    def compute(self) -> dict:
        """Вычислить все изменения."""
        return {
            "new_entities": self._new_entities(),
            "disappeared_entities": self._disappeared_entities(),
            "changed_entities": self._changed_entities(),
            "new_evidence": len(self.v2.evidence) - len(self.v1.evidence),
            "new_opportunities": len(self.v2.opportunities) - len(self.v1.opportunities),
            "new_leads": len(self.v2.leads) - len(self.v1.leads),
        }

    def _new_entities(self) -> list[dict]:
        """Сущности, появившиеся в v2."""
        new = []
        for eid, e in self.v2.entities.items():
            if eid not in self.v1.entities:
                new.append({"id": eid, "name": e.get("name",""), "type": e.get("type",""),
                            "sources": e.get("sources",[])})
        return new

    def _disappeared_entities(self) -> list[dict]:
        """Сущности, исчезнувшие из v2."""
        gone = []
        for eid, e in self.v1.entities.items():
            if eid not in self.v2.entities:
                gone.append({"id": eid, "name": e.get("name","")})
        return gone

    def _changed_entities(self) -> list[dict]:
        """Сущности, у которых изменились данные."""
        changes = []
        for eid, e1 in self.v1.entities.items():
            e2 = self.v2.entities.get(eid)
            if not e2:
                continue
            diffs = self._entity_diff(e1, e2)
            if diffs:
                changes.append({"id": eid, "name": e1.get("name",""), "changes": diffs})
        return changes

    @staticmethod
    def _entity_diff(e1: dict, e2: dict) -> list[dict]:
        """Сравнить две сущности."""
        diffs = []
        for key in ["phone","website","status","evidence_count"]:
            v1 = e1.get(key)
            v2 = e2.get(key)
            if v1 != v2:
                diffs.append({"field": key, "old": v1, "new": v2})
        return diffs

    def report(self) -> str:
        """Сформировать читаемый отчёт об изменениях."""
        d = self.compute()
        lines = [
            "📡 MARKET CHANGE REPORT",
            "=" * 56,
            f"  Snapshot: {self.v1.label} → {self.v2.label}",
            "",
            f"📊 OVERVIEW",
            f"  New entities:      {d['new_entities']}",
            f"  Disappeared:       {d['disappeared_entities']}",
            f"  Changed:           {d['changed_entities']}",
            f"  New evidence:      {d['new_evidence']}",
            f"  New opportunities: {d['new_opportunities']}",
            f"  New leads:         {d['new_leads']}",
            "",
        ]
        # New entities detail
        if d["new_entities"]:
            lines.append("🆕 NEW SELLERS")
            lines.append("-" * 30)
            for e in d["new_entities"][:10]:
                lines.append(f"  + {e['name']} ({e.get('type','?')}) — {e.get('sources','?')}")
            if len(d["new_entities"]) > 10:
                lines.append(f"  … и ещё {len(d['new_entities']) - 10}")
            lines.append("")

        # Disappeared
        if d["disappeared_entities"]:
            lines.append("🚫 DISAPPEARED")
            lines.append("-" * 30)
            for e in d["disappeared_entities"][:5]:
                lines.append(f"  - {e['name']}")
            lines.append("")

        # Changed
        if d["changed_entities"]:
            lines.append("🔄 CHANGED")
            lines.append("-" * 30)
            for e in d["changed_entities"][:10]:
                lines.append(f"  ~ {e['name']}:")
                for c in e["changes"]:
                    lines.append(f"      {c['field']}: {c['old']} → {c['new']}")
            lines.append("")

        lines.append("=" * 56)
        return "\n".join(lines)
