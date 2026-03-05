from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.event import EventRepository
from src.db.repositories.agent import AgentRepository
from src.schemas.event import EventQuery
from src.schemas.globe import (
    AttackArc,
    AttackSource,
    GlobeData,
    GlobeSummary,
    IPDayActivity,
    IPIntelligence,
    TargetServer,
)
from src.utils.geoip import geolocate_ip, is_public_ip

# Default coords for private IPs (Gijón, Asturias, Spain)
DEFAULT_LAT = 43.54
DEFAULT_LON = -5.66

# Caps
MAX_EVENTS = 5000
MAX_SOURCES = 500
MAX_ARCS = 200

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

# Priority for arc attack_type when an IP belongs to multiple categories.
# Specific service types first (rare, more informative), SSH last (most common default).
ATTACK_TYPE_PRIORITY = ["Nginx", "Firewall", "Sudo", "High Risk", "SSH"]


def _pick_primary_attack_type(types: set) -> str:
    for t in ATTACK_TYPE_PRIORITY:
        if t in types:
            return t
    return next(iter(types), "SSH")

# Maps extra_data keys to attack type labels
IP_EXTRACTION_KEYS = {
    "ssh_failures": "SSH",
    "firewall_blocked": "Firewall",
    "nginx_suspicious": "Nginx",
    "high_risk_ips": "High Risk",
    "sudo_failures": "Sudo",
}


def _higher_severity(a: str, b: str) -> str:
    return a if SEVERITY_ORDER.get(a, 0) >= SEVERITY_ORDER.get(b, 0) else b


def _infer_attack_type_from_ban(extra_data: dict) -> str:
    """Infer attack type from ban event extra_data."""
    ban_reason = extra_data.get("ban_reason", "").lower()
    ban_level = extra_data.get("ban_level", 1)
    if "ssh" in ban_reason:
        return "SSH"
    if "firewall" in ban_reason:
        return "Firewall"
    if "nginx" in ban_reason or "web" in ban_reason:
        return "Nginx"
    if "sudo" in ban_reason:
        return "Sudo"
    if ban_level >= 3:
        return "High Risk"
    return "SSH"


def _extract_ips_from_event(extra_data: dict | None) -> list[tuple[str, str]]:
    """Extract (ip, attack_type) pairs from event extra_data."""
    if not extra_data:
        return []

    results = []

    # Legacy format: keys with lists of IPs grouped by attack type
    for key, attack_type in IP_EXTRACTION_KEYS.items():
        data = extra_data.get(key)
        if not data:
            continue

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    ip = item.get("ip") or item.get("source_ip") or item.get("address")
                    if ip:
                        results.append((ip, attack_type))
                elif isinstance(item, str):
                    results.append((item, attack_type))

    # Ban event format: single banned_ip with ban_reason
    banned_ip = extra_data.get("banned_ip")
    if banned_ip:
        results.append((banned_ip, _infer_attack_type_from_ban(extra_data)))

    return results


class GlobeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.event_repo = EventRepository(db)
        self.agent_repo = AgentRepository(db)

    async def get_globe_data(self, hours: int = 24) -> GlobeData:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Query security events in time range
        query = EventQuery(
            category="security",
            start_time=since,
            sort_by="occurred_at",
            sort_order="desc",
            skip=0,
            limit=MAX_EVENTS,
        )
        events, _total = await self.event_repo.query(query)

        # Get active agents for target servers
        agents = await self.agent_repo.get_all(active_only=True)

        # Build agent lookup
        agent_map = {a.id: a for a in agents}

        # Aggregate IPs per source
        # key: ip -> {hits, max_severity, threat_score, attack_types, agent_ids}
        ip_agg: dict[str, dict] = defaultdict(lambda: {
            "hits": 0,
            "max_severity": "info",
            "threat_score": 0.0,
            "attack_types": set(),
            "agent_ids": set(),
        })

        # Arc aggregation: (source_ip, agent_id) -> {hits, attack_types, max_severity}
        arc_agg: dict[tuple[str, int], dict] = defaultdict(lambda: {
            "hits": 0,
            "attack_types": set(),
            "max_severity": "info",
        })

        for event in events:
            ip_pairs = _extract_ips_from_event(event.extra_data)
            event_severity = event.severity or "info"

            # Extract threat_score if present (also check total_score from ban events)
            threat_score = 0.0
            if event.extra_data:
                threat_score = float(
                    event.extra_data.get("threat_score")
                    or event.extra_data.get("total_score")
                    or 0
                )

            for ip, attack_type in ip_pairs:
                agg = ip_agg[ip]
                agg["hits"] += 1
                agg["max_severity"] = _higher_severity(agg["max_severity"], event_severity)
                agg["threat_score"] = max(agg["threat_score"], threat_score)
                agg["attack_types"].add(attack_type)
                agg["agent_ids"].add(event.agent_id)

                arc_key = (ip, event.agent_id)
                arc = arc_agg[arc_key]
                arc["hits"] += 1
                arc["attack_types"].add(attack_type)
                arc["max_severity"] = _higher_severity(arc["max_severity"], event_severity)

        # Geolocate unique IPs and build sources
        sources = []
        for ip, agg in ip_agg.items():
            geo = geolocate_ip(ip)
            if geo is None:
                continue
            sources.append(AttackSource(
                ip=ip,
                latitude=geo.latitude,
                longitude=geo.longitude,
                country_code=geo.country_code,
                country_name=geo.country_name,
                city=geo.city,
                total_hits=agg["hits"],
                max_severity=agg["max_severity"],
                threat_score=agg["threat_score"],
                attack_types=sorted(agg["attack_types"]),
                is_high_risk=agg["threat_score"] >= 70 or "High Risk" in agg["attack_types"],
            ))

        # Sort by hits descending, cap
        sources.sort(key=lambda s: s.total_hits, reverse=True)
        sources = sources[:MAX_SOURCES]
        source_ips = {s.ip for s in sources}

        # Build target servers
        targets = []
        agent_attack_count: dict[int, int] = defaultdict(int)
        for (ip, agent_id), arc in arc_agg.items():
            if ip in source_ips:
                agent_attack_count[agent_id] += arc["hits"]

        for agent in agents:
            count = agent_attack_count.get(agent.id, 0)
            if count == 0:
                continue
            # Geolocate agent IP, default to Asturias for private
            lat, lon = DEFAULT_LAT, DEFAULT_LON
            if agent.ip_address and is_public_ip(agent.ip_address):
                geo = geolocate_ip(agent.ip_address)
                if geo:
                    lat, lon = geo.latitude, geo.longitude

            targets.append(TargetServer(
                agent_id=agent.id,
                hostname=agent.hostname,
                ip_address=agent.ip_address or "",
                latitude=lat,
                longitude=lon,
                attack_count=count,
                os_type=agent.os_type,
            ))

        # Build arcs
        arcs = []
        for (ip, agent_id), arc in arc_agg.items():
            if ip not in source_ips:
                continue
            # Find source and target coords
            src = next((s for s in sources if s.ip == ip), None)
            tgt = next((t for t in targets if t.agent_id == agent_id), None)
            if not src or not tgt:
                continue
            arcs.append(AttackArc(
                source_ip=ip,
                target_agent_id=agent_id,
                source_lat=src.latitude,
                source_lon=src.longitude,
                target_lat=tgt.latitude,
                target_lon=tgt.longitude,
                hit_count=arc["hits"],
                attack_type=_pick_primary_attack_type(arc["attack_types"]),
                max_severity=arc["max_severity"],
            ))

        # Proportional arc selection: guarantee representation of every attack type
        type_arc_map: dict[str, list] = defaultdict(list)
        for arc in arcs:
            type_arc_map[arc.attack_type].append(arc)
        for grp in type_arc_map.values():
            grp.sort(key=lambda a: a.hit_count, reverse=True)

        num_types = len(type_arc_map)
        if num_types == 0:
            arcs = []
        else:
            per_type = max(1, MAX_ARCS // num_types)
            selected = []
            seen_ids: set[int] = set()
            for grp in type_arc_map.values():
                for arc in grp[:per_type]:
                    selected.append(arc)
                    seen_ids.add(id(arc))
            # Fill remaining budget with highest hit_count arcs not yet selected
            if len(selected) < MAX_ARCS:
                remaining = sorted(
                    (a for a in arcs if id(a) not in seen_ids),
                    key=lambda a: a.hit_count, reverse=True,
                )
                selected.extend(remaining[:MAX_ARCS - len(selected)])
            arcs = selected

        # Summary
        country_counts: dict[str, int] = defaultdict(int)
        type_counts: dict[str, int] = defaultdict(int)
        for s in sources:
            country_counts[s.country_name] += s.total_hits
            for t in s.attack_types:
                type_counts[t] += s.total_hits

        summary = GlobeSummary(
            total_attacks=sum(s.total_hits for s in sources),
            unique_ips=len(sources),
            unique_countries=len(country_counts),
            high_risk_count=sum(1 for s in sources if s.is_high_risk),
            top_country=max(country_counts, key=country_counts.get, default="N/A") if country_counts else "N/A",
            top_attack_type=max(type_counts, key=type_counts.get, default="N/A") if type_counts else "N/A",
        )

        return GlobeData(
            sources=sources,
            targets=targets,
            arcs=arcs,
            summary=summary,
            time_range_hours=hours,
        )

    async def get_ip_intelligence(self, ip: str) -> IPIntelligence:
        """Get intelligence about a specific IP from event history."""
        # Geolocate
        geo = geolocate_ip(ip)

        # Query all security events (last 30 days)
        since = datetime.now(timezone.utc) - timedelta(days=30)
        query = EventQuery(
            category="security",
            start_time=since,
            sort_by="occurred_at",
            sort_order="desc",
            skip=0,
            limit=MAX_EVENTS,
        )
        events, _ = await self.event_repo.query(query)

        # Filter events that mention this IP
        attack_types: dict[str, int] = defaultdict(int)
        first_seen = None
        last_seen = None
        daily: dict[str, int] = defaultdict(int)

        for event in events:
            ip_pairs = _extract_ips_from_event(event.extra_data)
            found = False
            for eip, attack_type in ip_pairs:
                if eip == ip:
                    attack_types[attack_type] += 1
                    found = True

            if found and event.occurred_at:
                ts = event.occurred_at.isoformat()
                if last_seen is None:
                    last_seen = ts
                first_seen = ts
                day = event.occurred_at.strftime("%Y-%m-%d")
                daily[day] += 1

        # Build 7-day activity
        today = datetime.now(timezone.utc).date()
        daily_activity = []
        for i in range(6, -1, -1):
            d = (today - timedelta(days=i)).isoformat()
            daily_activity.append(IPDayActivity(date=d, count=daily.get(d, 0)))

        return IPIntelligence(
            ip=ip,
            latitude=geo.latitude if geo else None,
            longitude=geo.longitude if geo else None,
            country_code=geo.country_code if geo else None,
            country_name=geo.country_name if geo else None,
            city=geo.city if geo else None,
            total_events=sum(attack_types.values()),
            attack_types=dict(attack_types),
            first_seen=first_seen,
            last_seen=last_seen,
            daily_activity=daily_activity,
        )
