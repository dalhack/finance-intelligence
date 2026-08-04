"""Cloud SQL Admin API User Management Client."""

import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Any

import google.auth
import google.auth.transport.requests
from app.migration_execution.redaction import redact_text

logger = logging.getLogger("migration_runner")

SQLADMIN_API_BASE = "https://sqladmin.googleapis.com/v1"


class CloudSQLAdminError(Exception):
    """Raised when a Cloud SQL Admin API call fails or times out."""


def _get_authenticated_session() -> tuple[str, google.auth.credentials.Credentials]:
    """Obtains authorized OAuth2 access token via Application Default Credentials (ADC)."""
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials, _ = google.auth.default(scopes=scopes)
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    if not credentials.token:
        raise CloudSQLAdminError("Failed to obtain OAuth2 access token from ADC credentials.")
    return credentials.token, credentials


def _make_api_request(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Executes an HTTP request to the Cloud SQL Admin API using standard urllib."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body else None

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            res_body = response.read().decode("utf-8")
            return json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        error_content = e.read().decode("utf-8") if e.fp else str(e)
        redacted_msg = redact_text(f"Cloud SQL Admin API HTTP error {e.code}: {error_content}")
        logger.error(f"[CLOUD_SQL_ADMIN] API call failed: {redacted_msg}")
        raise CloudSQLAdminError(f"Cloud SQL Admin API call to {url} failed with status {e.code}") from None
    except Exception as e:
        logger.error(f"[CLOUD_SQL_ADMIN] Request error: {redact_text(str(e))}")
        raise CloudSQLAdminError("Failed to communicate with Cloud SQL Admin API") from e


def _poll_operation(project_id: str, operation_id: str, token: str, max_wait_seconds: int = 60) -> None:
    """Polls a Cloud SQL Admin operation until status is DONE or timeout is reached."""
    poll_url = f"{SQLADMIN_API_BASE}/projects/{project_id}/operations/{operation_id}"
    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        op_data = _make_api_request("GET", poll_url, token)
        status = op_data.get("status")
        if status == "DONE":
            error = op_data.get("error")
            if error:
                err_msg = json.dumps(error)
                raise CloudSQLAdminError(f"Cloud SQL operation failed: {redact_text(err_msg)}")
            logger.info(f"[CLOUD_SQL_ADMIN] Operation {operation_id} completed successfully (DONE).")
            return
        logger.info(f"[CLOUD_SQL_ADMIN] Waiting for operation {operation_id} (status: {status})...")
        time.sleep(2)

    raise CloudSQLAdminError(f"Cloud SQL Admin operation {operation_id} timed out after {max_wait_seconds} seconds.")


def update_user_password(
    project_id: str,
    instance_name: str,
    username: str,
    password: str,
    host: str = "%",
) -> None:
    """Updates the password for a user on the specified Cloud SQL instance using Admin API."""
    logger.info(f"[CLOUD_SQL_ADMIN] Updating password for user '{username}' on instance '{instance_name}'...")
    token, _ = _get_authenticated_session()

    url = (
        f"{SQLADMIN_API_BASE}/projects/{project_id}/instances/{instance_name}/users"
        f"?name={urllib.parse.quote(username)}&host={urllib.parse.quote(host)}"
    )

    body = {
        "name": username,
        "host": host,
        "password": password,
    }

    op_response = _make_api_request("PUT", url, token, body=body)
    op_name = op_response.get("name")
    if not op_name:
        raise CloudSQLAdminError(f"Cloud SQL Admin API users.update did not return operation ID: {op_response}")

    op_id = op_name.split("/")[-1]
    _poll_operation(project_id, op_id, token)
    logger.info(f"[CLOUD_SQL_ADMIN] SUCCESS: User '{username}' password updated on Cloud SQL.")


def list_instance_users(project_id: str, instance_name: str) -> list[dict[str, Any]]:
    """Lists all users on the specified Cloud SQL instance."""
    token, _ = _get_authenticated_session()
    url = f"{SQLADMIN_API_BASE}/projects/{project_id}/instances/{instance_name}/users"
    res = _make_api_request("GET", url, token)
    return res.get("items", [])


def create_user_if_missing(
    project_id: str,
    instance_name: str,
    username: str,
    password: str,
    host: str = "%",
) -> None:
    """Creates user if absent, or updates password if user already exists."""
    logger.info(f"[CLOUD_SQL_ADMIN] Ensuring user '{username}' exists on instance '{instance_name}'...")
    token, _ = _get_authenticated_session()

    users = list_instance_users(project_id, instance_name)
    existing = [u for u in users if u.get("name") == username]

    if existing:
        logger.info(f"[CLOUD_SQL_ADMIN] User '{username}' already exists. Updating password...")
        update_user_password(project_id, instance_name, username, password, host=host)
        return

    logger.info(f"[CLOUD_SQL_ADMIN] User '{username}' missing. Creating user...")
    url = f"{SQLADMIN_API_BASE}/projects/{project_id}/instances/{instance_name}/users"
    body = {
        "name": username,
        "host": host,
        "password": password,
        "instance": instance_name,
        "project": project_id,
    }

    op_response = _make_api_request("POST", url, token, body=body)
    op_name = op_response.get("name")
    if not op_name:
        raise CloudSQLAdminError(f"Cloud SQL Admin API users.insert did not return operation ID: {op_response}")

    op_id = op_name.split("/")[-1]
    _poll_operation(project_id, op_id, token)
    logger.info(f"[CLOUD_SQL_ADMIN] SUCCESS: User '{username}' created on Cloud SQL.")
