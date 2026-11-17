from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

PARAGRAPHS = [
    "Distributed job processing separates accepting work from performing work. "
    "The API receives a request and immediately places a message on a queue.",
    "A message broker such as Redis stores queued messages until a worker is ready. "
    "Workers are independent processes that consume messages and execute the matching tasks.",
    "Because workers run separately from the API, long running tasks never block web requests. "
    "Additional workers can be started to increase processing capacity.",
    "Reliable systems must expect failure. Tasks should be idempotent, so that running a task "
    "twice produces the same result as running it once.",
    "Retries with exponential backoff prevent a struggling dependency from being overwhelmed. "
    "Failed tasks must be recorded so operators can inspect and reprocess them safely.",
    "Progress reporting keeps users informed. Workers publish progress events, and the API "
    "delivers them to clients through WebSocket connections in real time.",
]

styles = getSampleStyleSheet()
doc = SimpleDocTemplate("sample.pdf", pagesize=A4, title="Sample Queue Document", author="Kush")
story = []
for page in range(1, 6):
    story.append(Paragraph(f"Chapter {page}: Job Queues", styles["Heading1"]))
    story += [Paragraph(text, styles["BodyText"]) for text in PARAGRAPHS]
    if page < 5:
        story.append(PageBreak())
doc.build(story)
print("Created sample.pdf")