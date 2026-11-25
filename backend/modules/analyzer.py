
import re
from datetime import datetime

DATE_PATTERNS = [
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b",
    r"\b(?:19|20)\d{2}\b"
]

def clean_sentence(s):
    return re.sub(r"\s+", " ", s).strip(" \t-•")


def infer_key(sentence):
    s = sentence.lower()

    categories = [
        (r"\b(start(?:ed)?|commenc(?:ed|ement)|launch(?:ed)?)\b", "start_date"),
        (r"\b(complet(?:ed|ion)|finish(?:ed)?|end date)\b", "completion_date"),
        (r"\b(establish(?:ed|ment)|founded|incorporat(?:ed|ion))\b", "established_date"),
        (r"\b(birth|born)\b", "birth_date"),
        (r"\b(death|died)\b", "death_date"),
        (r"\b(deadline|due date|submission)\b", "deadline"),
        (r"\b(enrol(?:led|ment)|admission)\b", "enrollment"),
        (r"\b(population|students?|employees?|people)\b", "count")
    ]

    for pattern, key in categories:
        if re.search(pattern, s):
            return key

    return "general_date"


def extract_facts(text, filename):
    facts = []

    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)

    for sentence in sentences:
        sentence = clean_sentence(sentence)

        if len(sentence) < 12:
            continue

        dates = []

        for pattern in DATE_PATTERNS:
            dates.extend(
                re.findall(pattern, sentence, flags=re.I)
            )

        if dates:
            facts.append({
                "type": "date_claim",
                "value": dates[0],
                "claim": sentence[:500],
                "source": filename,
                "key": infer_key(sentence),
                "evidence": sentence[:500]
            })

        else:
            numeric_pattern = (
                r"\b\d+(?:,\d{3})*(?:\.\d+)?\s*"
                r"(?:%|students?|employees?|people|"
                r"lakhs?|crores?|rupees?|INR|km|meters?)\b"
            )

            match = re.search(
                numeric_pattern, sentence, re.I
            )

            if match:
                facts.append({
                    "type": "numeric_claim",
                    "value": match.group(0),
                    "claim": sentence[:500],
                    "source": filename,
                    "key": infer_key(sentence),
                    "evidence": sentence[:500]
                })

    return facts


def detect_contradictions(facts):
    groups = {}

    for fact in facts:
        if fact["type"] == "date_claim":
            groups.setdefault(fact["key"], []).append(fact)

    conflicts = []

    for key, items in groups.items():
        distinct = {}

        for item in items:
            value = item["value"].lower()

            distinct.setdefault(value, []).append(item)

        if len(distinct) > 1 and key != "general_date":

            values = list(distinct.items())

            for i in range(len(values)):
                for j in range(i + 1, len(values)):

                    for a in values[i][1]:
                        for b in values[j][1]:

                            if a["source"] != b["source"]:

                                category = key.replace(
                                    "_", " "
                                ).title()

                                explanation = (
                                    f"Different values were found "
                                    f"for the same detected category "
                                    f"({key.replace('_', ' ')}). "
                                    "The system cannot determine which "
                                    "source is correct from this "
                                    "comparison alone."
                                )

                                conflicts.append({
                                    "category": category,
                                    "claim_a": a["claim"],
                                    "source_a": a["source"],
                                    "value_a": a["value"],
                                    "claim_b": b["claim"],
                                    "source_b": b["source"],
                                    "value_b": b["value"],
                                    "explanation": explanation
                                })

    return conflicts
