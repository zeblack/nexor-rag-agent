import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_current_status = "unknown"


def get_status() -> str:
    return _current_status


async def run_healthcheck_loop():
    global _current_status
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                response = await client.get(settings.vpn_ip_check_url)
                current_ip = response.text.strip()
                if settings.vpn_expected_ip and current_ip != settings.vpn_expected_ip:
                    _current_status = "degraded"
                    logger.warning("VPN degradada: IP atual %s != esperado %s", current_ip, settings.vpn_expected_ip)
                else:
                    _current_status = "ok"
            except Exception as exc:  # noqa: BLE001 - healthcheck não pode derrubar a aplicação
                _current_status = "degraded"
                logger.warning("Falha ao checar IP externo para kill switch: %s", exc)

            await asyncio.sleep(settings.vpn_check_interval_seconds)
