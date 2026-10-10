#!/usr/bin/env python3
"""Validate the Compose storage and API binding invariants used by cutover."""

from __future__ import annotations

import json
import sys
from typing import Any


def validate(document: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(document, dict):
        return ["document"]

    volumes = document.get("volumes")
    services = document.get("services")
    networks = document.get("networks")
    if not isinstance(volumes, dict) or not isinstance(services, dict) or not isinstance(networks, dict):
        return ["compose_sections"]

    named_volume = volumes.get("cloud_postgres_data")
    if not isinstance(named_volume, dict) or named_volume.get("name") != "source_cloud_postgres_data":
        failures.append("postgres_volume_name")

    postgres = services.get("postgres")
    postgres_mounts = postgres.get("volumes", []) if isinstance(postgres, dict) else []
    data_mounts = [
        mount
        for mount in postgres_mounts
        if isinstance(mount, dict) and mount.get("target") == "/var/lib/postgresql/data"
    ]
    if len(data_mounts) != 1 or not (
        data_mounts[0].get("type") == "volume"
        and data_mounts[0].get("source") == "cloud_postgres_data"
    ):
        failures.append("postgres_volume_mount")

    database_network = networks.get("cloud_database")
    if (
        not isinstance(database_network, dict)
        or database_network.get("name") != "source_cloud_database"
        or database_network.get("internal") is not True
    ):
        failures.append("postgres_network_name")
    postgres_networks = postgres.get("networks", {}) if isinstance(postgres, dict) else {}
    if "cloud_database" not in postgres_networks:
        failures.append("postgres_network_membership")

    cloud = services.get("cloud")
    cloud_ports = cloud.get("ports", []) if isinstance(cloud, dict) else []
    if not any(
        isinstance(port, dict)
        and port.get("host_ip") == "127.0.0.1"
        and str(port.get("published")) == "8000"
        and str(port.get("target")) == "8000"
        for port in cloud_ports
    ):
        failures.append("cloud_loopback_port")
    if any(isinstance(port, dict) and port.get("host_ip") != "127.0.0.1" for port in cloud_ports):
        failures.append("cloud_public_port")

    identity = services.get("identity")
    identity_ports = identity.get("ports", []) if isinstance(identity, dict) else []
    if any(
        isinstance(port, dict) and port.get("host_ip") != "127.0.0.1"
        for port in identity_ports
    ):
        failures.append("identity_public_port")
    if not any(
        isinstance(port, dict)
        and port.get("host_ip") == "127.0.0.1"
        and str(port.get("published")) == "8001"
        and str(port.get("target")) == "8001"
        for port in identity_ports
    ):
        failures.append("identity_loopback_port")

    if isinstance(postgres, dict) and postgres.get("ports"):
        failures.append("postgres_public_port")

    return failures


def main() -> int:
    try:
        document = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("Compose storage invariant failed: invalid_json", file=sys.stderr)
        return 2

    failures = validate(document)
    if failures:
        print("Compose storage invariant failed: " + ",".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
