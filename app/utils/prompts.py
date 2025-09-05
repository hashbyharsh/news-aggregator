ARTICLE_SUMMARY_PROMPT = """
Analyze the following article versions and provide a JSON response with exactly these fields:

1. "summary": A single, concise one-line news summary (max 200-300 characters)
2. "brand_name": The car brand mentioned (e.g., "Tata", "Maruti", "Hyundai") or null if not found
3. "model_name": The specific car model mentioned (e.g., "Nexon", "Swift", "Creta") or null if not found

Requirements for the summary:
- EXACTLY ONE LINE (no line breaks, periods only at the end)
- Maximum 300 characters
- Include key information: Company/Brand, Product/Action, Key Details (price/date/numbers if relevant)
- Professional news format like: "Company X launches Product Y in India at INR Z lakhs"
- Focus on the most newsworthy element
- Include specific numbers, prices, dates when available
- Use present tense for recent news

Examples of good format:
- "Citroen launches C3 Sport Edition in India at INR 6.44 lakhs ex-showroom"
- "Tata Motors reports 25% sales growth with 15,000 Nexon units sold in March 2025"
- "Mahindra XUV700 gets new variant priced at INR 18.5 lakhs in Indian market"

Article versions:
{combined_content}

Return ONLY a valid JSON object with the three fields mentioned above. Example:
{{"summary": "Tata Motors launches Nexon EV Max in India at INR 17.74 lakhs ex-showroom", "brand_name": "Tata", "model_name": "Nexon"}}
"""

FULL_ARTICLE_PROMPT = """
You are a professional journalist and automotive expert. Your task is to merge and rewrite the following multiple versions of an article into a single, polished, publication-ready article in the specified format.

### Requirements:
- **Headline**: One-line headline (max 300 characters) in this format: "Company X launches Product Y in India at INR Z lakhs" or similar, including key details (brand, action, price/date/numbers), using present tense, professional style (e.g., "Tata Motors launches Nexon EV Max in India at INR 17.74 lakhs ex-showroom").
- **Subheadline**: Optional, 1–2 sentences (max 500 characters). Include only if it adds unique, non-repetitive details (e.g., additional specs, context, or outcomes not in the headline) in the same professional style (e.g., "The Nexon EV Max offers a 400 km range and advanced safety features.").
- **Accuracy**: Verify facts across sources, resolve contradictions, ensure consistency.
- **Impartiality**: Maintain a neutral, balanced, nonpartisan tone — avoid bias or opinions.
- **Completeness**: Include full context, background, and key details in the article.
- **Originality**: Write in your own words; no plagiarism or copy-paste. Add clear explanations or analysis where helpful.
- **Professional Writing**: Use engaging, concise, clear language. Structure with introduction, body, conclusion.
- **Style**: Follow reputable news outlets (e.g., Reuters, BBC, AP). Avoid fluff, jargon, sensationalism.
- **Length**: Article body between 2,000 and 5,000 characters (roughly 300–800 words).
- **Metadata**: Extract car brand (e.g., "Tata", "Hyundai") and model name (e.g., "Nexon", "Creta") or null if not found.
- **Formatting**: Use the exact structure below, with section titles (Headline, Subheadline, Article, MetaData) and no '#' symbols in the output. Ensure proper spacing and newlines as shown.

### Output Format (Plain Text):
[Generated headline (max 300 chars)]

[Optional 1–2 sentence Subheadline (max 500 chars, non-repetitive, specific details if present, empty string if omitted)]

[Article (max 2,000 - 3,000 chars, well-structured with paragraphs)]

- Car Brand: [Car brand or null]
- Model Name: [Car model or null]

### Source Versions:
{combined_content}
"""
