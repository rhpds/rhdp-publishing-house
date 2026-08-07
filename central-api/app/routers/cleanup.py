"""Cleanup router — purge completed/aborted workflows older than N days."""
import json
import logging
import ssl
import urllib.request
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..config import get_settings
from ..services.litellm import LiteLLMService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cleanup", tags=["cleanup"])

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class CleanupResult(BaseModel):
    completed_found: int = 0
    aborted_found: int = 0
    workflows_cleaned: int = 0
    litellm_keys_deleted: int = 0
    errors: list[str] = []


def _query_instances(graphql_url: str, state: str) -> list[dict]:
    graphql_query = {
        "query": f"""
            query GetInstances {{
                ProcessInstances(where: {{ state: {{ equal: {state} }} }}) {{
                    id businessKey lastUpdate
                }}
            }}
        """,
    }
    req = urllib.request.Request(
        f"{graphql_url.rstrip('/')}/graphql",
        data=json.dumps(graphql_query).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as r:
        gql_result = json.loads(r.read().decode())
    return gql_result.get("data", {}).get("ProcessInstances", [])


def _filter_by_age(instances: list[dict], cutoff: datetime) -> list[dict]:
    eligible = []
    for inst in instances:
        last_update = inst.get("lastUpdate")
        if not last_update:
            continue
        try:
            ts = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
            if ts < cutoff:
                eligible.append(inst)
        except (ValueError, TypeError):
            continue
    return eligible


def _purge_db(settings, wf_id: str, bk: str) -> None:
    import psycopg2
    conn = psycopg2.connect(
        host=settings.sonataflow_db_host,
        port=settings.sonataflow_db_port,
        dbname=settings.sonataflow_db_name,
        user=settings.sonataflow_db_user,
        password=settings.sonataflow_db_password,
    )
    try:
        with conn.cursor() as cur:
            ids_tuple = (wf_id,)

            cur.execute('SET search_path TO "publishing-house-workflow"')
            cur.execute("DELETE FROM correlation_instances WHERE correlated_id IN %s", (ids_tuple,))
            cur.execute("DELETE FROM business_key_mapping WHERE business_key = %s", (bk,))
            cur.execute("DELETE FROM process_instances WHERE id IN %s", (ids_tuple,))

            cur.execute('SET search_path TO "sonataflow-platform-data-index-service"')
            cur.execute("DELETE FROM milestones WHERE process_instance_id IN %s", (ids_tuple,))
            cur.execute("DELETE FROM nodes WHERE process_instance_id IN %s", (ids_tuple,))
            cur.execute("DELETE FROM processes_addons WHERE process_id IN %s", (ids_tuple,))
            cur.execute("DELETE FROM processes_roles WHERE process_id IN %s", (ids_tuple,))
            cur.execute("DELETE FROM processes WHERE id IN %s", (ids_tuple,))
        conn.commit()
    finally:
        conn.close()


@router.post("/completed")
async def cleanup_completed_workflows(
    days: int = Query(default=7, ge=1, description="Delete workflows completed/aborted more than N days ago"),
) -> CleanupResult:
    settings = get_settings()
    result = CleanupResult()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        completed = _filter_by_age(_query_instances(settings.sonataflow_graphql_url, "COMPLETED"), cutoff)
        aborted = _filter_by_age(_query_instances(settings.sonataflow_graphql_url, "ABORTED"), cutoff)
    except Exception as e:
        result.errors.append(f"GraphQL query failed: {e}")
        logger.error("cleanup: GraphQL query failed: %s", e)
        return result

    result.completed_found = len(completed)
    result.aborted_found = len(aborted)
    all_eligible = completed + aborted

    if not all_eligible:
        logger.info("cleanup: no workflows older than %d days", days)
        return result

    logger.info(
        "cleanup: found %d completed + %d aborted older than %d days",
        len(completed), len(aborted), days,
    )

    litellm = LiteLLMService(settings.litellm_api_url, settings.litellm_master_key)

    for inst in all_eligible:
        wf_id = inst["id"]
        bk = inst.get("businessKey", "")

        try:
            key_hashes = await litellm.find_keys_for_project(bk)
            for kh in key_hashes:
                if await litellm.delete_key(kh):
                    result.litellm_keys_deleted += 1
        except Exception as e:
            result.errors.append(f"LiteLLM cleanup failed for {bk}: {e}")
            logger.warning("cleanup: LiteLLM failed for %s: %s", bk, e)

        if settings.sonataflow_db_password:
            try:
                _purge_db(settings, wf_id, bk)
                result.workflows_cleaned += 1
                logger.info("cleanup: purged workflow %s (%s)", wf_id, bk)
            except Exception as e:
                result.errors.append(f"DB cleanup failed for {bk}: {e}")
                logger.warning("cleanup: DB failed for %s: %s", bk, e)

    logger.info(
        "cleanup: done — %d/%d cleaned, %d keys deleted, %d errors",
        result.workflows_cleaned, len(all_eligible),
        result.litellm_keys_deleted, len(result.errors),
    )
    return result
