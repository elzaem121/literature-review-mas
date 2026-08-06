from Orchestration.graph import app as workflow_app

# Mermaid source — paste directly into the README
print(workflow_app.get_graph().draw_mermaid())

# PNG image
png = workflow_app.get_graph().draw_mermaid_png()
with open("docs/graph.png", "wb") as f:
    f.write(png)