
from __future__ import annotations

from datetime import date
from pathlib import Path
import re

from app.access_control import Role, User
from app.rag_assistant import KnowledgeDocument, RAGKnowledgeAssistant


PROJECT_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = PROJECT_DIR / "data" / "documents"


def get_document_family(filename: str) -> tuple[str, int]:
    """Return a document's family and version number."""
    stem = Path(filename).stem
    match = re.search(r"_v(\d+)$", stem, re.IGNORECASE)

    if match:
        version_number = int(match.group(1))
        family = stem[:match.start()]
    else:
        version_number = 1
        family = stem

    return family.lower(), version_number


def get_document_type(family: str) -> str:
    """Infer a supported document type from its filename."""
    name = family.lower()

    if "faq" in name:
        return "faq"
    if "troubleshoot" in name:
        return "troubleshooting"
    if "product" in name:
        return "product"
    if "policy" in name:
        return "policy"

    return "general"


def load_knowledge_documents() -> list[KnowledgeDocument]:
    """Load the newest text-file version in each document family."""
    if not DOCUMENTS_DIR.is_dir():
        raise FileNotFoundError(
            f"Knowledge-base folder not found: {DOCUMENTS_DIR}"
        )

    files = list(DOCUMENTS_DIR.glob("*.txt"))

    if not files:
        raise FileNotFoundError(
            f"No .txt knowledge-base documents found in {DOCUMENTS_DIR}"
        )

    latest_files: dict[str, tuple[int, Path]] = {}

    for path in files:
        family, version_number = get_document_family(path.name)
        existing = latest_files.get(family)

        if existing is None or version_number > existing[0]:
            latest_files[family] = (version_number, path)

    documents: list[KnowledgeDocument] = []

    for family, (version_number, path) in sorted(latest_files.items()):
        content = path.read_text(encoding="utf-8").strip()

        if not content:
            print(f"Warning: Skipping empty document: {path.name}")
            continue

        documents.append(
            KnowledgeDocument(
                document_id=family,
                title=family.replace("_", " ").title(),
                content=content,
                product="General",
                region="IN",
                access_level="public",
                effective_date=date(2026, 1, 1),
                version=f"{version_number}.0",
                document_type=get_document_type(family),
                source=path.name,
            )
        )

    if not documents:
        raise ValueError("No usable knowledge-base documents were loaded.")

    return documents


def main() -> None:
    print("=" * 58)
    print("       GENAI CUSTOMER SUPPORT CHATBOT")
    print("       Terminal-based RAG Assistant")
    print("=" * 58)

    try:
        documents = load_knowledge_documents()
        assistant = RAGKnowledgeAssistant(documents=documents)
    except Exception as exc:
        print(f"\nCould not initialize the chatbot: {exc}")
        return

    user = User(username="terminal-user", role=Role.VIEWER)

    print(f"\nLoaded {len(documents)} latest document version(s).")
    print("Type your question and press Enter.")
    print("Commands: /help and /exit\n")

    while True:
        try:
            query = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nChatbot closed.")
            break

        if not query:
            continue

        if query.lower() in {"/exit", "exit", "quit"}:
            print("Chatbot closed. Goodbye!")
            break

        if query.lower() == "/help":
            print(
                "\nAsk questions about the loaded knowledge-base "
                "documents.\n"
                "Use /exit to close the chatbot.\n"
                "Answers are limited to available authorized evidence.\n"
            )
            continue

        try:
            response = assistant.answer(
                query=query,
                user=user,
                requested_date=date.today(),
                product="General",
                region="IN",
            )

            print(f"\nBot: {response.answer}")

            if response.citations:
                print("\nSources:")
                for citation in response.citations:
                    print(f"  - {citation}")

            if response.needs_clarification:
                print(
                    "\nNote: The available evidence may be insufficient "
                    "or ambiguous."
                )

            print()

        except Exception as exc:
            print(f"\nCould not answer this question: {exc}\n")


if __name__ == "__main__":
    main()
