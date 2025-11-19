# Automation Toolkit Dashboard

This Streamlit application provides a suite of automation tools:

1.  **Gamma Watermark Remover**: Removes "Made with GAMMA" watermarks from PPTX and PDF files.
2.  **iimjobs Applied Jobs Export**: Exports your applied jobs history from iimjobs.com to a CSV file.

## Deployment on Streamlit Cloud

This repository is configured for easy deployment on [Streamlit Cloud](https://streamlit.io/cloud).

### Prerequisites

The following files are included to ensure smooth operation on Streamlit Cloud:

*   `requirements.txt`: Lists Python dependencies (`streamlit`, `selenium`, `requests`, `pypdf`).
*   `packages.txt`: Lists system dependencies (`chromium`, `chromium-driver`) required for Selenium.

### Setup Instructions

1.  **Connect to GitHub**: Push this repository to your GitHub account.
2.  **Deploy**:
    *   Go to Streamlit Cloud and create a new app.
    *   Select your repository, branch, and the main file path (`streamlit_app.py`).
    *   Click **Deploy**.

### Secrets Management

The **iimjobs Applied Jobs Export** tool requires your iimjobs credentials. For security, **DO NOT** hardcode them in the files.

You can enter them directly in the dashboard UI, or if you want to pre-fill them (optional), you can set them in Streamlit Secrets:

1.  In your Streamlit Cloud dashboard, go to the app's **Settings** -> **Secrets**.
2.  Add the following:

```toml
IIMJOBS_EMAIL = "your_email@example.com"
IIMJOBS_PASSWORD = "your_password"
```

*Note: The current application logic primarily accepts credentials via the UI for user flexibility.*

## Local Development

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Run the app:
    ```bash
    streamlit run streamlit_app.py
    ```
