
from backend.modules.analyzer import extract_facts, detect_contradictions

doc1 = """
Project Helios started on January 15, 2025.
"""

doc2 = """
Project Helios started on March 10, 2025.
"""

facts = extract_facts(doc1, "document_A.txt")
facts += extract_facts(doc2, "document_B.txt")

print("EXTRACTED FACTS:")
for fact in facts:
    print(fact)

print("\nDETECTED CONTRADICTIONS:")
conflicts = detect_contradictions(facts)

for conflict in conflicts:
    print(conflict)
