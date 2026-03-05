import ipaddress
import logging
from functools import lru_cache
from typing import NamedTuple

import geoip2.database
import geoip2.errors

from src.core.config import settings

logger = logging.getLogger(__name__)


class GeoLocation(NamedTuple):
    latitude: float
    longitude: float
    country_code: str
    country_name: str
    city: str


@lru_cache(maxsize=1)
def _get_reader() -> geoip2.database.Reader | None:
    try:
        return geoip2.database.Reader(settings.GEOIP_DB_PATH)
    except Exception as e:
        logger.error("Failed to open GeoIP database at %s: %s", settings.GEOIP_DB_PATH, e)
        return None


def is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_global
    except ValueError:
        return False


@lru_cache(maxsize=4096)
def geolocate_ip(ip: str) -> GeoLocation | None:
    if not is_public_ip(ip):
        return None

    reader = _get_reader()
    if reader is None:
        return None

    try:
        resp = reader.city(ip)
        lat = resp.location.latitude
        lon = resp.location.longitude
        if lat is None or lon is None:
            return None
        return GeoLocation(
            latitude=lat,
            longitude=lon,
            country_code=resp.country.iso_code or "??",
            country_name=resp.country.names.get("es") or resp.country.name or "Desconocido",
            city=resp.city.names.get("es") or resp.city.name or "",
        )
    except geoip2.errors.AddressNotFoundError:
        return None
    except Exception as e:
        logger.warning("GeoIP lookup failed for %s: %s", ip, e)
        return None
