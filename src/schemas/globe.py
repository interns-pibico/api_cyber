from pydantic import BaseModel


class AttackSource(BaseModel):
    ip: str
    latitude: float
    longitude: float
    country_code: str
    country_name: str
    city: str
    total_hits: int
    max_severity: str
    threat_score: float
    attack_types: list[str]
    is_high_risk: bool


class TargetServer(BaseModel):
    agent_id: int
    hostname: str
    ip_address: str
    latitude: float
    longitude: float
    attack_count: int
    os_type: str


class AttackArc(BaseModel):
    source_ip: str
    target_agent_id: int
    source_lat: float
    source_lon: float
    target_lat: float
    target_lon: float
    hit_count: int
    attack_type: str
    max_severity: str


class GlobeSummary(BaseModel):
    total_attacks: int
    unique_ips: int
    unique_countries: int
    high_risk_count: int
    top_country: str
    top_attack_type: str


class GlobeData(BaseModel):
    sources: list[AttackSource]
    targets: list[TargetServer]
    arcs: list[AttackArc]
    summary: GlobeSummary
    time_range_hours: int


class IPDayActivity(BaseModel):
    date: str
    count: int


class IPIntelligence(BaseModel):
    ip: str
    latitude: float | None = None
    longitude: float | None = None
    country_code: str | None = None
    country_name: str | None = None
    city: str | None = None
    total_events: int
    attack_types: dict[str, int]
    first_seen: str | None = None
    last_seen: str | None = None
    daily_activity: list[IPDayActivity]
