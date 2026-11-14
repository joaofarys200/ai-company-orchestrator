"""
Strict SSRF guard for remote URLs (IPv4, IPv6, IPv4-mapped IPv6, CGNAT, obfuscations, DNS fail-closed).
Zero external dependencies so both core services and minimal CI test runners import cleanly.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse
from typing import Any, Dict, List, Tuple

_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")
_THIS_NET = ipaddress.ip_network("0.0.0.0/8")
_BENCHMARK_NET = ipaddress.ip_network("198.18.0.0/15")


def is_forbidden_ip(addr_str: str) -> bool:
    """Returns True if `addr_str` resolves to any loopback, private, link-local, CGNAT, or reserved IP."""
    try:
        cleaned = addr_str.split("%")[0].strip().strip("[]")
        ip = ipaddress.ip_address(cleaned)
        if isinstance(ip, ipaddress.IPv6Address):
            mapped = ip.ipv4_mapped
            if mapped is not None:
                ip = mapped
        if isinstance(ip, ipaddress.IPv4Address):
            if ip in _CGNAT_NET or ip in _THIS_NET or ip in _BENCHMARK_NET:
                return True
        return bool(
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False


def validate_remote_url_syntax(url: str) -> Tuple[urllib.parse.ParseResult, str]:
    """Validates HTTP(S) scheme, absence of embedded credentials, hostname, and non-private literal IPs."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("SECURITY_VIOLATION: URL vazio ou invalido.")

    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("SECURITY_VIOLATION: Apenas URLs HTTP e HTTPS sao suportadas.")

    if parsed.username is not None or parsed.password is not None:
        raise ValueError("SECURITY_VIOLATION: URLs com credenciais embutidas bloqueados por SSRF guard.")

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise ValueError("SECURITY_VIOLATION: Hostname ausente no URL.")

    if (
        hostname in ("localhost", "localhost.localdomain")
        or hostname.endswith(".localhost")
        or hostname.endswith(".local")
        or hostname.endswith(".internal")
    ):
        raise ValueError("SECURITY_VIOLATION: Acesso a enderecos locais bloqueado por SSRF guard.")

    if hostname.startswith("0x") or hostname.isdigit() or is_forbidden_ip(hostname):
        raise ValueError("SECURITY_VIOLATION: Acesso a IP privado, reservado ou obfuscado bloqueado por SSRF guard.")

    try:
        packed = socket.inet_aton(hostname)
        normalized_ip = socket.inet_ntoa(packed)
        if is_forbidden_ip(normalized_ip):
            raise ValueError("SECURITY_VIOLATION: Endereco IP numerico privado bloqueado por SSRF guard.")
    except OSError:
        pass

    return parsed, hostname


def validate_remote_url(url: str, *, resolve_dns: bool = True) -> Dict[str, Any]:
    """
    Validates remote URL syntax and (when `resolve_dns=True`) performs fail-closed DNS
    resolution, rejecting unresolved hosts, empty address lists, or private/reserved targets.
    """
    parsed, hostname = validate_remote_url_syntax(url)
    resolved_ips: List[str] = []

    if resolve_dns:
        try:
            infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError(
                f"SECURITY_VIOLATION: Falha na resolucao DNS (fail-closed) para '{hostname}': {exc}"
            ) from exc

        for info in infos:
            resolved_ip = info[4][0]
            if is_forbidden_ip(resolved_ip):
                raise ValueError(
                    f"SECURITY_VIOLATION: Host '{hostname}' resolve para IP interno/reservado ({resolved_ip})."
                )
            if resolved_ip not in resolved_ips:
                resolved_ips.append(resolved_ip)

        if not resolved_ips:
            raise ValueError(
                f"SECURITY_VIOLATION: Host '{hostname}' nao retornou IPs publicos resolvidos (fail-closed)."
            )

    return {
        "parsed": parsed,
        "hostname": hostname,
        "resolved_ips": resolved_ips,
    }
