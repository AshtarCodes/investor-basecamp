# How well does vision extraction read your real screenshots?

Type: prototype
Status: open

## Question

Run the OpenAI vision model ("GPT-6 Luna") with a draft structured-output schema over your real thinkorswim Position Statement and schwab.com Positions screenshots, and look at the results together.

Decide from what you see:

- the extraction schema (which fields to ask for, and how option descriptions become contracts)
- the cross-check tolerances that flag a row for review
- whether multi-screenshot merging into one Simulated Portfolio is needed in practice
- the exact model id, and the cost per screenshot
