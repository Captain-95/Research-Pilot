import os
import re
import smtplib
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from email.message import EmailMessage

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
)


from langchain_ollama import ChatOllama
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

llm = ChatOllama(
    model="qwen3:4b",
    temperature=0.2,
)

search_tool = DuckDuckGoSearchResults(
    output_format="list",
    num_results=5,
)

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are ResearchPilot, an AI research assistant.
        Answer using the supplied search results.
        Explain important concepts clearly.
        Include source URLs when available.
        If the evidence is insufficient, say so.
        Do not invent facts or citations."""
    ),
    (
        "human",
        """Research question: {question}

        Search results:
        {context}

        Write a useful, structured research report."""
    )
])

research_chain = prompt | llm

@tool
def create_pdf_tool(
    topic: str,
    report_text: str,
    sources_text: str,
) -> str:
    """Create a formatted PDF containing a research report
    and its source URLs. Return the generated PDF path."""

    safe_topic = re.sub(
        r"[^a-zA-Z0-9_-]+", "_", topic
    ).strip("_")[:60] or "research"

    pdf_path = REPORT_DIR / f"{safe_topic}.pdf"

    document = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=18,
    )

    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#24527A"),
        spaceBefore=12,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        leading=15,
        spaceAfter=7,
    )

    story = [
        Paragraph("ResearchPilot Report", title_style),
        Paragraph(f"Topic: {escape(topic)}", styles["Heading2"]),
        Spacer(1, 12),
    ]

    # Convert basic Markdown headings and paragraphs
    # into PDF elements.
    for line in report_text.splitlines():
        line = line.strip()

        if not line or line == "---":
            story.append(Spacer(1, 5))
            continue

        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            story.append(
                Paragraph(escape(heading), heading_style)
            )

        elif line.startswith(("- ", "* ")):
            bullet = escape(line[2:])
            story.append(
                Paragraph(f"&bull; {bullet}", body_style)
            )

        else:
            story.append(
                Paragraph(escape(line), body_style)
            )

    # Add the real source records, not model-generated URLs.
    story.append(Spacer(1, 16))
    story.append(
        Paragraph("Sources", styles["Heading1"])
    )

    for source_line in sources_text.splitlines():
        if source_line.strip():
            story.append(
                Paragraph(
                    escape(source_line),
                    body_style,
                )
            )

    document.build(story)

    return str(pdf_path.resolve())

@tool
def send_email_tool(
    recipient: str,
    subject: str,
    body: str,
    attachment_path: str = "",
) -> str:
    """Send an email using configured Gmail SMTP credentials.
    Attach a PDF when attachment_path is provided."""

    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        raise ValueError(
            "SMTP_EMAIL or SMTP_APP_PASSWORD is missing in .env"
        )

    message = EmailMessage()
    message["From"] = SMTP_EMAIL
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    # Attach the PDF only when a file was provided.
    if attachment_path:
        pdf_path = Path(attachment_path)

        if not pdf_path.is_file():
            raise FileNotFoundError(
                f"PDF attachment not found: {pdf_path}"
            )

        with pdf_path.open("rb") as file:
            message.add_attachment(
                file.read(),
                maintype="application",
                subtype="pdf",
                filename=pdf_path.name,
            )

    # Send the email through Gmail SMTP with TLS.
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(message)

    return f"Email sent successfully to {recipient}"


def send_regret_email(topic: str, error: Exception) -> None:
    """Make a best-effort attempt to notify the recipient."""

    if not RECIPIENT_EMAIL:
        print("RECIPIENT_EMAIL is missing. Cannot send regret email.")
        return

    try:
        send_email_tool.invoke({
            "recipient": RECIPIENT_EMAIL,
            "subject": f"ResearchPilot: Report unavailable - {topic}",
            "body": (
                f"Hello,\n\n"
                f"Sorry, ResearchPilot could not complete your "
                f"research request about '{topic}'.\n\n"
                f"Reason: {type(error).__name__}: {error}\n\n"
                f"Please try again later.\n\n"
                f"Regards,\nResearchPilot"
            ),
            "attachment_path": "",
        })

        print("Regret email sent.")

    except Exception as email_error:
        print(
            "Could not send regret email either: "
            f"{email_error}"
        )



def research(question: str) -> None:
    """Search, generate, create PDF, and email the report."""

    try:
        if not RECIPIENT_EMAIL:
            raise ValueError(
                "RECIPIENT_EMAIL is missing in .env"
            )

        # STEP 1: SEARCH THE WEB
        print("\nSearching the web...")

        search_results = search_tool.invoke(question)

        if not search_results:
            raise RuntimeError("No search results were found.")

        # STEP 2: PREPARE CONTEXT AND SOURCES
        context_parts = []
        source_lines = []

        for index, result in enumerate(search_results, start=1):
            
            title = result.get("title", "Untitled")
            snippet = result.get("snippet", result.get("body", ""))
            url = result.get("link", result.get("href", ""))

            context_parts.append(
                f"Source [{index}]\n"
                f"Title: {title}\n"
                f"URL: {url}\n"
                f"Snippet: {snippet}"
            )

            if url:
                source_lines.append(
                    f"[{index}] {title}\n{url}"
                )

        context = "\n\n".join(context_parts)
        sources_text = "\n\n".join(source_lines)

        print(f"Found {len(search_results)} search results.")

        # STEP 3: GENERATE THE REPORT
        print("\nGenerating the research report...")

        response = research_chain.invoke({
            "question": question,
            "context": context,
        })

        report_text = response.content

        if isinstance(report_text, list):
            report_text = "\n".join(
                item if isinstance(item, str) else str(item)
                for item in report_text
                )

        if not report_text or not report_text.strip():
            raise RuntimeError(
                "The language model returned an empty report.")

        print("\nResearch report generated successfully.")

        print("\n" + "=" * 60)
        print("RESEARCHPILOT REPORT")
        print("=" * 60)
        print(report_text)

        print("\nSOURCES")
        print("=" * 60)
        print(sources_text or "No source URLs were returned.")

        # STEP 4: CREATE THE PDF USING OUR TOOL
        print("\nCreating PDF...")

        pdf_path = create_pdf_tool.invoke({
            "topic": question,
            "report_text": report_text,
            "sources_text": sources_text,
        })

        print(f"PDF created: {pdf_path}")

        # STEP 5: EMAIL THE PDF USING OUR TOOL
        print("\nSending the report by email...")

        email_result = send_email_tool.invoke({
            "recipient": RECIPIENT_EMAIL,
            "subject": f"Your ResearchPilot Report: {question}",
            "body": (
                f"Hello,\n\n"
                f"Your research report on '{question}' "
                f"has been generated successfully.\n\n"
                f"Please find the PDF report attached to this email.\n\n"
                f"Regards,\nResearchPilot"
            ),
            "attachment_path": pdf_path,
        })

        print(email_result)
        print("\nResearchPilot workflow completed successfully!")

    except Exception as error:
        print("\nResearchPilot encountered an error.")
        print(f"Error: {type(error).__name__}: {error}")

        # If any step fails, attempt to notify the recipient.
        send_regret_email(question, error)


if __name__ == "__main__":
    print("Welcome to ResearchPilot!")
    question = input("\nWhat do you want to research? ")

    if question.strip():
        research(question)
    else:
        print("Please enter a research question.")



