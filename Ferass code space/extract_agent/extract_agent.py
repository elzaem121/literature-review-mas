import json


# JSON-Datei laden
with open("test_input.json", "r", encoding="utf-8") as file:
    paper = json.load(file)


# Daten auslesen
title = paper.get("title", "")
abstract = paper.get("abstract", "")
results = paper.get("results", "")
limitations = paper.get("limitations", "")


# Einfache Extraktion
method = "Unknown"
dataset = "Unknown"

# Methode erkennen
abstract_lower = abstract.lower()
results_lower = results.lower()

methods = []

if "theoretical review" in abstract_lower or "theoretical framework" in abstract_lower:
    methods.append("Theoretical Review")

if "framework" in abstract_lower:
    methods.append("Framework-based Analysis")

if "qualitative" in abstract_lower or "interview" in abstract_lower or "interviews" in abstract_lower:
    methods.append("Qualitative Study / Interviews")

if "survey" in abstract_lower or "questionnaire" in abstract_lower:
    methods.append("Survey / Questionnaire")

if "systematic review" in abstract_lower or "literature review" in abstract_lower:
    methods.append("Systematic Literature Review")

if "machine learning" in abstract_lower:
    methods.append("Machine Learning")

if "support vector machines" in abstract_lower:
    methods.append("Support Vector Machines")

if "random forest" in abstract_lower:
    methods.append("Random Forest")

if "content analysis" in abstract_lower:
    methods.append("Content Analysis")

if len(methods) > 0:
    method = methods
else:
    method = ["Unknown"]


# Datensatz erkennen
if "social media" in abstract.lower():
    dataset = "Social Media Posts"


# Output-Struktur
output = {
    "title": title,
    "method": method,
    "dataset": dataset,
    "abstract_summary": abstract,
    "results_summary": results,
    "limitations": limitations
}


# JSON speichern
with open("test_output.json", "w", encoding="utf-8") as file:
    json.dump(output, file, indent=4)


print("Extraction completed successfully.")