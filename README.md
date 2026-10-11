# ResearchPilot

ResearchPilot is a command-line research assistant that searches the web for a topic, uses a local Ollama model to draft a structured report, saves the report as a PDF, and emails the PDF to a configured recipient.

## How It Works

1. Prompts you for a research question.
2. Searches the web and collects up to five results.
3. Sends the question and search snippets to the local `qwen3:4b` model to draft a report.
4. Prints the report and sources, then saves a PDF in `reports/`.
5. Emails the PDF using Gmail SMTP.

The model runs locally through Ollama. Web search requires an internet connection. Generated reports should be checked against their linked sources before relying on them.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/download) with the `qwen3:4b` model available
- A Gmail account with 2-Step Verification and a Gmail app password for sending email

## Setup

Clone the repository and enter its directory, then install the Python dependencies:

```powershell
uv sync
```

Download the model used by the application:

```powershell
ollama pull qwen3:4b
```

Make sure Ollama is running. Create a `.env` file in the project root with these settings:

```dotenv
SMTP_EMAIL=your-gmail-address@gmail.com
SMTP_APP_PASSWORD=your-16-character-app-password
RECIPIENT_EMAIL=recipient@example.com
```

Use a Gmail app password, not your regular account password. Keep `.env` private; it is excluded from Git by `.gitignore`.

## Run

From the project root, run:

```powershell
uv run python main.py
```

Enter a research question when prompted. The report is printed in the terminal, saved as a PDF under `reports/`, and emailed to `RECIPIENT_EMAIL`.

## Project Files

- `main.py` - search, report generation, PDF creation, and email workflow
- `pyproject.toml` and `uv.lock` - project metadata and locked Python dependencies
- `.env` - local email configuration (not committed)
- `reports/` - generated PDF reports (not committed)

## Troubleshooting

- **Ollama connection or model error:** Start Ollama and confirm `qwen3:4b` is installed with `ollama list`.
- **Missing email configuration:** Confirm all three variables are present in `.env`.
- **Gmail authentication error:** Verify that 2-Step Verification is enabled and that `SMTP_APP_PASSWORD` contains a valid Gmail app password.
- **Search or email failures:** Check your internet connection and try again. The application attempts to email a failure notice when a research run fails.

