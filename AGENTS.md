# EK Product Intake Automation

- Keep all supplier and product data synthetic.
- Preserve the parser → provider → validator → decision separation.
- Default to the offline mock extraction provider; tests must never call a network API.
- Prefer explicit validation failures over silent coercion.
