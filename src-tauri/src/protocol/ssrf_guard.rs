//! Strict SSRF validation with DNS resolution, private/reserved IP blocking,
//! IPv4-mapped IPv6 unwrapping, CGNAT blocking, and resolved IP pinning.

use std::net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr};

use url::Url;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidatedRemoteUrl {
    pub normalized_url: String,
    pub host: String,
    pub port: u16,
    pub resolved_addrs: Vec<SocketAddr>,
}

/// Checks whether an IP address belongs to loopback, private, link-local, CGNAT,
/// multicast, unspecified, ULA, or IPv4-mapped reserved ranges.
pub fn is_forbidden_ip(ip: IpAddr) -> bool {
    match ip {
        IpAddr::V4(v4) => is_forbidden_ipv4(v4),
        IpAddr::V6(v6) => {
            if let Some(mapped_v4) = v6.to_ipv4_mapped() {
                return is_forbidden_ipv4(mapped_v4);
            }
            if let Some(compat_v4) = v6.to_ipv4() {
                return is_forbidden_ipv4(compat_v4);
            }
            is_forbidden_ipv6(v6)
        }
    }
}

fn is_forbidden_ipv4(v4: Ipv4Addr) -> bool {
    let octets = v4.octets();
    let is_cgnat = octets[0] == 100 && (octets[1] & 0b1100_0000) == 64; // 100.64.0.0/10
    let is_benchmark = octets[0] == 198 && (octets[1] == 18 || octets[1] == 19); // 198.18.0.0/15
    let is_this_net = octets[0] == 0; // 0.0.0.0/8

    v4.is_private()
        || v4.is_loopback()
        || v4.is_link_local()
        || v4.is_multicast()
        || v4.is_broadcast()
        || v4.is_documentation()
        || v4.is_unspecified()
        || is_cgnat
        || is_benchmark
        || is_this_net
}

fn is_forbidden_ipv6(v6: Ipv6Addr) -> bool {
    let seg0 = v6.segments()[0];
    let is_unique_local = (seg0 & 0xfe00) == 0xfc00; // fc00::/7
    let is_unicast_link_local = (seg0 & 0xffc0) == 0xfe80; // fe80::/10

    v6.is_loopback()
        || v6.is_unspecified()
        || v6.is_multicast()
        || is_unique_local
        || is_unicast_link_local
}

/// Validates scheme, absence of embedded credentials, host safety, and rejects numeric/obfuscated
/// hosts prior to DNS resolution.
pub fn validate_url_syntax(raw_url: &str) -> Result<(Url, String, u16), String> {
    let parsed = Url::parse(raw_url.trim())
        .map_err(|e| format!("Invalid URL syntax: {e}"))?;

    let scheme = parsed.scheme();
    if scheme != "http" && scheme != "https" {
        return Err(format!(
            "SECURITY_VIOLATION: unsupported URL scheme `{scheme}`; only http/https allowed"
        ));
    }
    if !parsed.username().is_empty() || parsed.password().is_some() {
        return Err("SECURITY_VIOLATION: URLs with embedded credentials are blocked".to_string());
    }

    let raw_host = parsed
        .host_str()
        .ok_or_else(|| "SECURITY_VIOLATION: URL missing host".to_string())?;
    let host = raw_host
        .trim_start_matches('[')
        .trim_end_matches(']')
        .trim_end_matches('.')
        .to_ascii_lowercase();

    if host.is_empty()
        || host == "localhost"
        || host.ends_with(".localhost")
        || host.ends_with(".local")
        || host.ends_with(".internal")
    {
        return Err(format!(
            "SECURITY_VIOLATION: local/internal hostname `{host}` blocked by SSRF guard"
        ));
    }

    // Reject single-integer decimal or hex IP obfuscations (e.g. `2130706433`, `0x7f000001`).
    if host.starts_with("0x") || host.parse::<u32>().is_ok() {
        return Err(format!(
            "SECURITY_VIOLATION: obfuscated numeric host `{host}` blocked by SSRF guard"
        ));
    }

    if let Ok(ip) = host.parse::<IpAddr>() {
        if is_forbidden_ip(ip) {
            return Err(format!(
                "SECURITY_VIOLATION: internal/reserved IP `{ip}` blocked by SSRF guard"
            ));
        }
    }

    let port = parsed
        .port_or_known_default()
        .ok_or_else(|| "Unable to determine target port".to_string())?;

    Ok((parsed, host, port))
}

/// Resolves DNS asynchronously and fails closed unless at least one valid public IP is found and
/// ALL returned addresses are public/non-reserved.
pub async fn validate_and_resolve_remote_url(raw_url: &str) -> Result<ValidatedRemoteUrl, String> {
    let (parsed, host, port) = validate_url_syntax(raw_url)?;

    let addrs: Vec<SocketAddr> = tokio::net::lookup_host((host.as_str(), port))
        .await
        .map_err(|e| {
            format!("SECURITY_VIOLATION: SSRF DNS resolution failed (fail-closed) for `{host}`: {e}")
        })?
        .collect();

    if addrs.is_empty() {
        return Err(format!(
            "SECURITY_VIOLATION: SSRF DNS returned zero addresses (fail-closed) for `{host}`"
        ));
    }

    for addr in &addrs {
        if is_forbidden_ip(addr.ip()) {
            return Err(format!(
                "SECURITY_VIOLATION: hostname `{host}` resolved to forbidden IP {}",
                addr.ip()
            ));
        }
    }

    Ok(ValidatedRemoteUrl {
        normalized_url: parsed.to_string(),
        host,
        port,
        resolved_addrs: addrs,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ssrf_guard_blocks_private_cgnat_metadata_obfuscated_and_ipv4_mapped_ips() {
        for forbidden_ip in [
            "127.0.0.1",
            "10.0.0.5",
            "172.16.4.2",
            "192.168.1.10",
            "169.254.169.254",
            "100.64.12.34",
            "0.0.0.0",
            "::1",
            "fe80::1",
            "fc00::1",
            "::ffff:127.0.0.1",
            "::ffff:169.254.169.254",
        ] {
            let ip: IpAddr = forbidden_ip.parse().unwrap();
            assert!(
                is_forbidden_ip(ip),
                "expected is_forbidden_ip({forbidden_ip}) == true"
            );
        }

        let public_ip: IpAddr = "93.184.216.34".parse().unwrap();
        assert!(!is_forbidden_ip(public_ip));

        for bad_url in [
            "file:///C:/Windows/win.ini",
            "http://127.0.0.1:8000/secret",
            "http://localhost/healthz",
            "http://[::ffff:127.0.0.1]/admin",
            "http://100.64.0.1/internal",
            "http://2130706433/secret",
            "http://0x7f000001/secret",
            "https://user:pass@example.com/video.mp4",
            "http://nas.local/video.mp4",
        ] {
            assert!(
                validate_url_syntax(bad_url).is_err(),
                "expected validate_url_syntax to reject {bad_url:?}"
            );
        }
    }

    #[tokio::test]
    async fn ssrf_resolver_fails_closed_when_dns_cannot_resolve() {
        let err = validate_and_resolve_remote_url(
            "https://nonexistent.invalid.jarvis.test/video.mp4",
        )
        .await
        .expect_err("unresolved DNS must fail closed");
        assert!(err.contains("SECURITY_VIOLATION"));
    }
}
