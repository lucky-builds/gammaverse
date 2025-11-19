#!/usr/bin/env python3
"""
Utility to export iimjobs.com applied jobs into a CSV file.

Requirements:
    - Selenium (with ChromeDriver available on PATH)
    - requests

Environment variables:
    IIMJOBS_EMAIL      -> user login email (required)
    IIMJOBS_PASSWORD   -> user password (required)
    IIMJOBS_HEADLESS   -> optional ("0" to disable headless Chrome, defaults to headless)
    IIMJOBS_CSV_PATH   -> optional output path; defaults to ./iimjobs_applied_jobs.csv
"""

from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

APPLIED_JOBS_URL = "https://www.iimjobs.com/applied-jobs"
APPLIED_JOBS_API = (
    "https://gladiator.iimjobs.com/job/applied-jobs?"
    "page={page}&status=&ref=menu&referenceText=menu&refPool=%7B%22ref%22:%22menu%22%7D"
)
DEFAULT_OUTPUT = "iimjobs_applied_jobs.csv"

STATUS_LABELS = {
    0: "APPLIED/SENT",
    1: "SHORTLISTED",
    2: "NOT SUITABLE",
    3: "SAVED FOR FUTURE",
    4: "VIEWED",
    5: "DOWNLOADED",
    101: "YOUR STATUS HAS BEEN CHANGED",
    9: "ROUND ZERO VIEWED",
}


@dataclass
class AppliedJob:
    application_id: int
    application_date: Optional[str]
    title: str
    company: str
    locations: str
    job_url: str
    app_status_code: Optional[int]
    app_status_label: str
    recruiter_name: str
    recruiter_email: str
    recruiter_org: str
    recruiter_last_login: str
    recruiter_last_active: str
    views: Optional[int]
    app_count: Optional[int]
    recruiter_actions: Optional[int]
    invite_status: Optional[int]


def require_env(name: str) -> str:
    """Fetch a required environment variable."""
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"{name} environment variable is required.")
    return value


def build_driver(headless: bool = True) -> webdriver.Chrome:
    """Create a Chrome WebDriver instance."""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)


def login(driver: webdriver.Chrome, email: str, password: str) -> None:
    """Perform login via Selenium."""
    wait = WebDriverWait(driver, 30)
    driver.get(APPLIED_JOBS_URL)

    email_input = wait.until(EC.element_to_be_clickable((By.ID, "email-input")))
    password_input = wait.until(EC.element_to_be_clickable((By.ID, "password-input")))

    email_input.clear()
    email_input.send_keys(email)

    password_input.clear()
    password_input.send_keys(password)
    password_input.submit()

    # Wait until login finishes (login form disappears)
    wait.until(EC.invisibility_of_element_located((By.ID, "password-input")))

    # Explicitly navigate to Applied Jobs after login since the site may redirect elsewhere
    driver.get(APPLIED_JOBS_URL)
    wait.until(EC.url_contains("applied-jobs"))


def build_session(driver: webdriver.Chrome) -> requests.Session:
    """Transfer cookies from Selenium to a requests session."""
    session = requests.Session()
    user_agent = driver.execute_script("return navigator.userAgent;")
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Referer": APPLIED_JOBS_URL,
        }
    )

    for cookie in driver.get_cookies():
        session.cookies.set(cookie["name"], cookie["value"])

    return session


def fetch_applied_jobs(session: requests.Session) -> List[Dict[str, Any]]:
    """Iterate over all paginated applied job API responses."""
    jobs: List[Dict[str, Any]] = []
    page = 0

    while True:
        url = APPLIED_JOBS_API.format(page=page)
        response = session.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json()

        data = payload.get("data") or {}
        batch = data.get("jobs") or []

        if not batch:
            break

        jobs.extend(batch)

        if len(batch) < 50:
            break

        page += 1

    return jobs


def to_iso_date(timestamp_ms: Optional[int]) -> Optional[str]:
    if not timestamp_ms:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def serialize_job(raw_job: Dict[str, Any]) -> AppliedJob:
    job_detail = raw_job.get("jobDetail") or {}
    recruiter = raw_job.get("recruiterDetail") or {}

    status_code = raw_job.get("app_status")
    status_label = STATUS_LABELS.get(status_code, "UNKNOWN")

    locations = ", ".join(
        loc.get("name", "").strip()
        for loc in job_detail.get("location") or []
        if loc.get("name")
    )

    recruiter_last_login = ""
    if isinstance(raw_job.get("recr_last_login"), dict):
        recruiter_last_login = raw_job["recr_last_login"].get("loginDate", "") or ""

    recruiter_last_active = ""
    if isinstance(raw_job.get("lastActive"), dict):
        recruiter_last_active = raw_job["lastActive"].get("lastActiveDate", "") or ""

    return AppliedJob(
        application_id=raw_job.get("applicationId"),
        application_date=to_iso_date(raw_job.get("applicationDate")),
        title=job_detail.get("title", ""),
        company=(
            recruiter.get("organisationName") or job_detail.get("company", "") or ""
        ),
        locations=locations,
        job_url=job_detail.get("jobUrl", ""),
        app_status_code=status_code,
        app_status_label=status_label,
        recruiter_name=recruiter.get("name", ""),
        recruiter_email=recruiter.get("email", ""),
        recruiter_org=recruiter.get("organisationName", ""),
        recruiter_last_login=recruiter_last_login,
        recruiter_last_active=recruiter_last_active,
        views=raw_job.get("views"),
        app_count=raw_job.get("app_count"),
        recruiter_actions=raw_job.get("recruiterActions"),
        invite_status=raw_job.get("inviteStatus"),
    )


def write_jobs_to_csv(jobs: Iterable[AppliedJob], output_path: Path) -> None:
    fieldnames = [
        "application_id",
        "application_date",
        "title",
        "company",
        "locations",
        "job_url",
        "app_status_code",
        "app_status_label",
        "recruiter_name",
        "recruiter_email",
        "recruiter_org",
        "recruiter_last_login",
        "recruiter_last_active",
        "views",
        "app_count",
        "recruiter_actions",
        "invite_status",
    ]

    output_path = Path(output_path)
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            writer.writerow(job.__dict__)


def export_applied_jobs(
    email: str,
    password: str,
    output_path: Optional[Path] = None,
    headless: bool = True,
) -> Tuple[Path, int]:
    if not email or not password:
        raise ValueError("Email and password are required.")
    output_path = Path(output_path or DEFAULT_OUTPUT)
    driver: Optional[webdriver.Chrome] = None
    try:
        driver = build_driver(headless=headless)
        login(driver, email, password)

        session = build_session(driver)
        raw_jobs = fetch_applied_jobs(session)

        serialized_jobs = [serialize_job(job) for job in raw_jobs]
        write_jobs_to_csv(serialized_jobs, output_path)

        return output_path, len(serialized_jobs)
    finally:
        if driver:
            driver.quit()


def main() -> None:
    email = require_env("IIMJOBS_EMAIL")
    password = require_env("IIMJOBS_PASSWORD")
    output_path = os.getenv("IIMJOBS_CSV_PATH", DEFAULT_OUTPUT)

    headless = os.getenv("IIMJOBS_HEADLESS", "1") != "0"

    path, count = export_applied_jobs(
        email=email,
        password=password,
        output_path=Path(output_path),
        headless=headless,
    )
    print(f"Exported {count} jobs to {path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

