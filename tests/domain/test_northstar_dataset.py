import json
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from zevidence.domain import (
    Claim,
    ClaimStatus,
    Document,
    DocumentStatus,
    Dossier,
    Evidence,
    Run,
    SourceLocator,
    validate_claim_traceability,
)

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "northstar"


def load_dataset() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((FIXTURE_ROOT / "dataset.json").read_text()),
    )


def test_northstar_dataset_builds_a_traceable_dossier() -> None:
    dataset = load_dataset()
    assert dataset["dataset_version"] == "1.0.0"
    assert dataset["schema_version"] == "1.0.0"
    dossier_data = dataset["dossier"]
    dossier = Dossier(
        title=dossier_data["title"],
        requirements=tuple(dossier_data["requirements"]),
    )

    documents: dict[str, Document] = {}
    contents: dict[str, str] = {}
    for path in sorted(FIXTURE_ROOT.glob("*.md")):
        content = path.read_text()
        contents[path.name] = content
        documents[path.name] = Document(
            dossier_id=dossier.id,
            filename=path.name,
            mime_type="text/markdown",
            content_hash=sha256(content.encode()).hexdigest(),
            status=DocumentStatus.READY,
        )

    run = Run(
        dossier_id=dossier.id,
        document_ids=tuple(document.id for document in documents.values()),
        idempotency_key="northstar-baseline-v1",
    )

    claims: list[Claim] = []
    evidence_by_id: dict[Any, Evidence] = {}
    for expected in dataset["expected_claims"]:
        evidence_items: list[Evidence] = []
        for expected_evidence in expected["evidence"]:
            filename = expected_evidence["document"]
            excerpt = expected_evidence["excerpt"]
            assert excerpt in contents[filename]
            start_offset = contents[filename].index(excerpt)
            evidence_items.append(
                Evidence(
                    document_id=documents[filename].id,
                    excerpt=excerpt,
                    source_locator=SourceLocator(
                        start_offset=start_offset,
                        end_offset=start_offset + len(excerpt),
                        section=expected_evidence["section"],
                    ),
                    content_hash=sha256(excerpt.encode()).hexdigest(),
                )
            )
        evidence_by_id.update({item.id: item for item in evidence_items})

        claims.append(
            Claim(
                run_id=run.id,
                text=expected["text"],
                status=ClaimStatus(expected["status"]),
                evidence_ids=tuple(item.id for item in evidence_items),
            )
        )

    assert len(documents) == 3
    assert len(claims) == 5
    assert [claim.status for claim in claims] == [
        ClaimStatus.SUPPORTED,
        ClaimStatus.CONFLICTING,
        ClaimStatus.SUPPORTED,
        ClaimStatus.CONFLICTING,
        ClaimStatus.UNSUPPORTED,
    ]

    document_by_id = {document.id: document for document in documents.values()}
    content_by_document_id = {
        documents[filename].id: content for filename, content in contents.items()
    }
    for claim in claims:
        validate_claim_traceability(
            claim,
            run=run,
            dossier=dossier,
            evidence_by_id=evidence_by_id,
            document_by_id=document_by_id,
            content_by_document_id=content_by_document_id,
        )
