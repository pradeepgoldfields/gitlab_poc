"""
Enterprise GitLab Access Model PoC - GitLab API client.

Thin wrapper over requests with idempotent helpers for the PoC operations.
All methods are intended to be safe to re-run.
"""
import sys
import time
import json
from urllib.parse import quote
import requests

import config
import api_call_log


class GitLabError(Exception):
    pass


class GitLabClient:
    def __init__(self, url=None, token=None, verify=None, timeout=None):
        self.url = (url or config.GITLAB_URL).rstrip("/")
        self.token = token or config.GITLAB_ADMIN_TOKEN
        self.verify = config.VERIFY_SSL if verify is None else verify
        self.timeout = timeout or config.REQUEST_TIMEOUT
        if not self.token:
            raise GitLabError(
                "No GitLab token set. Export GITLAB_ADMIN_TOKEN before running."
            )
        self.headers = {
            "PRIVATE-TOKEN": self.token,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Low-level request helpers
    # ------------------------------------------------------------------
    def _request(self, method, path, **kwargs):
        url = f"{self.url}/api/v4{path}"
        kwargs.setdefault("headers", self.headers)
        kwargs.setdefault("verify", self.verify)
        kwargs.setdefault("timeout", self.timeout)

        # Capture request body for the call log (without the headers, which
        # contain the token).
        req_body = None
        if "data" in kwargs:
            try:
                req_body = json.loads(kwargs["data"])
            except (TypeError, ValueError):
                req_body = kwargs["data"]
        elif "json" in kwargs:
            req_body = kwargs["json"]
        elif "params" in kwargs and kwargs["params"]:
            req_body = {"_query": dict(kwargs["params"])}

        started = time.monotonic()
        try:
            resp = requests.request(method, url, **kwargs)
        except requests.RequestException as e:
            api_call_log.record_call(
                method=method, url=url, request_body=req_body,
                status=None, response_body=None,
                duration_ms=(time.monotonic() - started) * 1000.0,
                error=str(e),
            )
            raise

        duration_ms = (time.monotonic() - started) * 1000.0

        # Parse response body for both success and error paths
        try:
            parsed = resp.json() if resp.content else None
        except Exception:
            parsed = resp.text

        if resp.status_code >= 400:
            api_call_log.record_call(
                method=method, url=url, request_body=req_body,
                status=resp.status_code, response_body=parsed,
                duration_ms=duration_ms,
                error=f"HTTP {resp.status_code}",
            )
            raise GitLabError(
                f"{method} {path} -> HTTP {resp.status_code}: {parsed}"
            )

        api_call_log.record_call(
            method=method, url=url, request_body=req_body,
            status=resp.status_code, response_body=parsed,
            duration_ms=duration_ms,
        )

        if resp.status_code == 204 or not resp.content:
            return None
        return parsed

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, json_body=None):
        return self._request("POST", path, data=json.dumps(json_body or {}))

    def put(self, path, json_body=None):
        return self._request("PUT", path, data=json.dumps(json_body or {}))

    def delete(self, path):
        return self._request("DELETE", path)

    def get_paginated(self, path, params=None):
        """Fetch all pages of a list endpoint."""
        results = []
        page = 1
        params = dict(params or {})
        while True:
            params.update({"page": page, "per_page": 100})
            batch = self.get(path, params=params)
            if not batch:
                break
            results.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return results

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------
    def find_group(self, full_path):
        """Return group dict or None. full_path is like 'acme-poc/iam-sim/sscam'."""
        encoded = quote(full_path, safe="")
        try:
            return self.get(f"/groups/{encoded}")
        except GitLabError as e:
            if "404" in str(e):
                return None
            raise

    def ensure_group(self, full_path, visibility="internal", description=""):
        """Create a group (or subgroup) if it doesn't exist. Returns the group."""
        existing = self.find_group(full_path)
        if existing:
            return existing
        parts = full_path.split("/")
        name = parts[-1]
        if len(parts) == 1:
            # Top-level group
            payload = {"name": name, "path": name, "visibility": visibility, "description": description}
        else:
            parent_path = "/".join(parts[:-1])
            parent = self.find_group(parent_path)
            if not parent:
                raise GitLabError(f"Parent group not found: {parent_path}")
            payload = {
                "name": name,
                "path": name,
                "parent_id": parent["id"],
                "visibility": visibility,
                "description": description,
            }
        return self.post("/groups", json_body=payload)

    def list_group_members(self, full_path, include_inherited=False):
        encoded = quote(full_path, safe="")
        endpoint = f"/groups/{encoded}/members/all" if include_inherited else f"/groups/{encoded}/members"
        return self.get_paginated(endpoint)

    def add_group_member(self, full_path, user_id, access_level):
        """Idempotent: skip if user is already a direct member."""
        members = self.list_group_members(full_path)
        if any(m["id"] == user_id for m in members):
            return None
        encoded = quote(full_path, safe="")
        return self.post(
            f"/groups/{encoded}/members",
            json_body={"user_id": user_id, "access_level": access_level},
        )

    def share_group_with_group(self, target_group_path, shared_group_path, access_level):
        """Share one group with another (the 'group link' feature). Idempotent."""
        target = self.find_group(target_group_path)
        shared = self.find_group(shared_group_path)
        if not target or not shared:
            raise GitLabError(f"Cannot share: target={target_group_path} shared={shared_group_path}")
        # Check existing links
        encoded = quote(target_group_path, safe="")
        existing = self.get(f"/groups/{encoded}") or {}
        for link in existing.get("shared_with_groups", []) or []:
            if link.get("group_id") == shared["id"]:
                return None  # already shared
        return self.post(
            f"/groups/{encoded}/share",
            json_body={
                "group_id": shared["id"],
                "group_access": access_level,
            },
        )

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------
    def find_project(self, full_path):
        encoded = quote(full_path, safe="")
        try:
            return self.get(f"/projects/{encoded}")
        except GitLabError as e:
            if "404" in str(e):
                return None
            raise

    def ensure_project(self, full_path, initialize_readme=True, visibility=None):
        existing = self.find_project(full_path)
        if existing:
            return existing
        parts = full_path.split("/")
        name = parts[-1]
        namespace_path = "/".join(parts[:-1])
        namespace = self.find_group(namespace_path)
        if not namespace:
            raise GitLabError(f"Namespace group not found: {namespace_path}")
        payload = {
            "name": name,
            "path": name,
            "namespace_id": namespace["id"],
            "initialize_with_readme": initialize_readme,
        }
        if visibility:
            payload["visibility"] = visibility
        return self.post("/projects", json_body=payload)

    def list_project_members(self, full_path, include_inherited=False):
        encoded = quote(full_path, safe="")
        endpoint = f"/projects/{encoded}/members/all" if include_inherited else f"/projects/{encoded}/members"
        return self.get_paginated(endpoint)

    def share_project_with_group(self, project_path, shared_group_path, access_level):
        project = self.find_project(project_path)
        shared = self.find_group(shared_group_path)
        if not project or not shared:
            raise GitLabError(f"Cannot share: project={project_path} group={shared_group_path}")
        # Check existing shares
        encoded = quote(project_path, safe="")
        project_detail = self.get(f"/projects/{encoded}")
        for link in project_detail.get("shared_with_groups", []) or []:
            if link.get("group_id") == shared["id"]:
                return None  # already shared
        return self.post(
            f"/projects/{encoded}/share",
            json_body={
                "group_id": shared["id"],
                "group_access": access_level,
            },
        )

    def unshare_project_from_group(self, project_path, shared_group_path):
        project = self.find_project(project_path)
        shared = self.find_group(shared_group_path)
        if not project or not shared:
            return None
        encoded = quote(project_path, safe="")
        try:
            return self.delete(f"/projects/{encoded}/share/{shared['id']}")
        except GitLabError as e:
            if "404" in str(e):
                return None
            raise

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------
    def find_user_by_username(self, username):
        results = self.get("/users", params={"username": username})
        return results[0] if results else None

    def find_user_by_email(self, email):
        # Requires admin for non-public email search
        results = self.get("/users", params={"search": email})
        for u in results or []:
            if u.get("email") == email or u.get("public_email") == email:
                return u
        return None

    def ensure_user(self, username, email, name, password):
        """Create the user if possible; return existing if already present."""
        existing = self.find_user_by_username(username)
        if existing:
            return existing
        payload = {
            "username": username,
            "email": email,
            "name": name,
            "password": password,
            "skip_confirmation": True,
        }
        try:
            return self.post("/users", json_body=payload)
        except GitLabError as e:
            raise GitLabError(
                f"Could not create user {username}. "
                f"Admin token required, or pre-provision the user manually. Error: {e}"
            )

    # ------------------------------------------------------------------
    # Custom (member) roles
    # ------------------------------------------------------------------
    def list_member_roles(self):
        try:
            return self.get("/member_roles")
        except GitLabError as e:
            # On GitLab.com, member_roles is only at the group level
            if "404" in str(e):
                return []
            raise

    def create_member_role(self, name, description, base_role, abilities):
        """Create an instance-level custom role (self-managed Ultimate)."""
        # Base access levels are integers for member_roles endpoint
        base_levels = {"guest": 10, "reporter": 20, "developer": 30, "maintainer": 40, "owner": 50}
        payload = {
            "name": name,
            "description": description,
            "base_access_level": base_levels.get(base_role, 20),
        }
        # Each ability becomes a boolean flag on the role
        for ability in abilities:
            payload[ability] = True
        return self.post("/member_roles", json_body=payload)

    def ensure_member_role(self, name, description, base_role, abilities):
        existing = self.list_member_roles()
        for role in existing:
            if role.get("name") == name:
                return role
        return self.create_member_role(name, description, base_role, abilities)

    # ------------------------------------------------------------------
    # Protected branches, tags, environments
    # ------------------------------------------------------------------
    def protect_branch(self, project_path, name, push_access_level, merge_access_level,
                       code_owner_approval_required=False):
        encoded = quote(project_path, safe="")
        # Unprotect first (idempotent)
        try:
            self.delete(f"/projects/{encoded}/protected_branches/{quote(name, safe='')}")
        except GitLabError:
            pass
        return self.post(
            f"/projects/{encoded}/protected_branches",
            json_body={
                "name": name,
                "push_access_level": push_access_level,
                "merge_access_level": merge_access_level,
                "code_owner_approval_required": code_owner_approval_required,
            },
        )

    def protect_tag(self, project_path, name, create_access_level):
        encoded = quote(project_path, safe="")
        try:
            self.delete(f"/projects/{encoded}/protected_tags/{quote(name, safe='')}")
        except GitLabError:
            pass
        return self.post(
            f"/projects/{encoded}/protected_tags",
            json_body={"name": name, "create_access_level": create_access_level},
        )

    def ensure_environment(self, project_path, env_name):
        encoded = quote(project_path, safe="")
        envs = self.get_paginated(f"/projects/{encoded}/environments")
        for e in envs:
            if e["name"] == env_name:
                return e
        return self.post(
            f"/projects/{encoded}/environments",
            json_body={"name": env_name},
        )

    def protect_environment(self, project_path, env_name,
                            deploy_access_levels=None,
                            deploy_access_users=None,
                            approval_rules=None):
        """Create a protected environment. deploy_access_users = list of usernames."""
        self.ensure_environment(project_path, env_name)
        encoded = quote(project_path, safe="")
        # Unprotect first (idempotent)
        try:
            self.delete(f"/projects/{encoded}/protected_environments/{quote(env_name, safe='')}")
        except GitLabError:
            pass

        access_entries = list(deploy_access_levels or [])
        for username in deploy_access_users or []:
            user = self.find_user_by_username(username)
            if not user:
                raise GitLabError(f"User {username} not found for protected env {env_name}")
            access_entries.append({"user_id": user["id"]})

        payload = {"name": env_name, "deploy_access_levels": access_entries}
        if approval_rules:
            rules = []
            for r in approval_rules:
                rule = {"required_approvals": r.get("required_approvals", 1)}
                if r.get("username"):
                    user = self.find_user_by_username(r["username"])
                    if user:
                        rule["user_id"] = user["id"]
                if r.get("group_path"):
                    g = self.find_group(r["group_path"])
                    if g:
                        rule["group_id"] = g["id"]
                rules.append(rule)
            payload["approval_rules"] = rules
        return self.post(f"/projects/{encoded}/protected_environments", json_body=payload)

    # ------------------------------------------------------------------
    # CI/CD variables
    # ------------------------------------------------------------------
    def set_group_variable(self, group_path, key, value, protected=False,
                           masked=False, environment_scope="*"):
        encoded = quote(group_path, safe="")
        # Upsert
        try:
            return self.put(
                f"/groups/{encoded}/variables/{key}",
                json_body={
                    "value": value,
                    "protected": protected,
                    "masked": masked,
                    "environment_scope": environment_scope,
                },
            )
        except GitLabError as e:
            if "404" in str(e):
                return self.post(
                    f"/groups/{encoded}/variables",
                    json_body={
                        "key": key,
                        "value": value,
                        "protected": protected,
                        "masked": masked,
                        "environment_scope": environment_scope,
                    },
                )
            raise

    def set_project_variable(self, project_path, key, value, protected=False,
                             masked=False, environment_scope="*"):
        encoded = quote(project_path, safe="")
        try:
            return self.put(
                f"/projects/{encoded}/variables/{key}",
                json_body={
                    "value": value,
                    "protected": protected,
                    "masked": masked,
                    "environment_scope": environment_scope,
                },
            )
        except GitLabError as e:
            if "404" in str(e):
                return self.post(
                    f"/projects/{encoded}/variables",
                    json_body={
                        "key": key,
                        "value": value,
                        "protected": protected,
                        "masked": masked,
                        "environment_scope": environment_scope,
                    },
                )
            raise

    # ------------------------------------------------------------------
    # Files (for committing CI yaml, CODEOWNERS)
    # ------------------------------------------------------------------
    def upsert_file(self, project_path, branch, file_path, content, commit_message):
        encoded = quote(project_path, safe="")
        file_encoded = quote(file_path, safe="")
        endpoint = f"/projects/{encoded}/repository/files/{file_encoded}"
        # Try to get the file first
        try:
            self.get(endpoint, params={"ref": branch})
            # Exists — update
            return self.put(endpoint, json_body={
                "branch": branch,
                "content": content,
                "commit_message": commit_message,
            })
        except GitLabError as e:
            if "404" in str(e):
                return self.post(endpoint, json_body={
                    "branch": branch,
                    "content": content,
                    "commit_message": commit_message,
                })
            raise

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    @staticmethod
    def full_path(*parts):
        from config import TOP_GROUP
        return "/".join([TOP_GROUP] + list(parts))


# ---------------------------------------------------------------------------
# Banner helpers for phase scripts
# ---------------------------------------------------------------------------
def banner(text, char="="):
    line = char * 72
    print(f"\n{line}\n  {text}\n{line}")


def step(text):
    print(f"  • {text}")
    api_call_log.step(text, level="info")


def done(text):
    print(f"  ✓ {text}")
    api_call_log.step(text, level="ok")


def warn(text):
    print(f"  ! {text}")
    api_call_log.step(text, level="warn")


def fail(text):
    print(f"  ✗ {text}", file=sys.stderr)
    api_call_log.step(text, level="error")


def require_admin_token():
    if not config.GITLAB_ADMIN_TOKEN:
        fail("GITLAB_ADMIN_TOKEN is not set. Export it and retry.")
        sys.exit(1)
