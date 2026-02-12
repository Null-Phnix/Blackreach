#!/usr/bin/env python3
"""
Job Application Helper

Quick script to generate custom cover letters for job applications.
Run this while browsing job postings to generate tailored letters in seconds.
"""

import sys
from pathlib import Path

TEMPLATES = {
    "solutions": """Dear {hiring_manager},

I'm applying for the {job_title} position at {company}. I recently built Blackreach, an autonomous browser agent in Python that uses LLM APIs to navigate websites and extract data autonomously.

What caught my attention about {company} is {specific_interest}. My experience building Blackreach directly translates to this role:

- Browser automation expertise: I've solved the exact challenges your customers face - handling dynamic content, bypassing anti-bot systems, and building reliable extraction pipelines
- API integration: My agent integrates with OpenAI, Anthropic, and XAI APIs, similar to how I'd help {company}'s customers integrate your platform
- Testing rigor: I maintain 2,868 automated tests because I understand production reliability matters

I'm particularly excited about {specific_responsibility} - this aligns with my approach of building robust, well-tested automation systems.

I'd love to discuss how my experience building autonomous agents could help {company}'s customers succeed.

Best regards,
[Your Name]""",

    "python": """Dear {hiring_manager},

I'm a Python developer focused on AI automation, applying for {job_title} at {company}.

I recently built Blackreach, an autonomous browser agent that combines Playwright with LLM APIs to perform web research autonomously. Some highlights:

- 2,800+ test suite covering browser management, error recovery, and parallel operations
- Advanced stealth features to bypass Cloudflare and anti-bot systems
- RAG system for querying 500k+ word knowledge bases

What excites me about {company} is {specific_interest}. I see parallels between my work on Blackreach's {blackreach_feature} and your needs for {job_requirement}.

I'm confident I can contribute to {company_project} and would welcome the chance to discuss this role.

Best,
[Your Name]""",

    "qa": """Dear {hiring_manager},

I'm applying for the {job_title} role at {company}. As someone who just built a 2,868-test automation suite for a Python browser agent, I understand the value of comprehensive testing.

My Blackreach project required:
- Browser test automation: Playwright integration tests, mocking complex browser states
- Edge case coverage: Challenge pages, network errors, race conditions, resource leaks
- CI/CD integration: Tests run on every commit, catch regressions before merge
- Performance testing: Parallel operation verification, memory leak detection

I noticed {company} uses {tech_stack}. I have hands-on experience with Python testing frameworks and understand how to build test infrastructure that scales.

I'd be excited to discuss how my testing philosophy could strengthen {company}'s quality assurance.

Best regards,
[Your Name]""",
}


def generate_cover_letter(template_type: str):
    """Interactive cover letter generator."""
    if template_type not in TEMPLATES:
        print(f"Unknown template: {template_type}")
        print(f"Available: {', '.join(TEMPLATES.keys())}")
        sys.exit(1)

    print(f"\n🤖 Generating {template_type.upper()} cover letter\n")
    print("Answer these questions (be specific!):\n")

    # Collect inputs
    inputs = {}
    inputs['company'] = input("Company name: ").strip()
    inputs['job_title'] = input("Job title: ").strip()
    inputs['hiring_manager'] = input("Hiring manager name (or 'Hiring Team'): ").strip() or "Hiring Team"

    if template_type == "solutions":
        inputs['specific_interest'] = input("What caught your attention? (product/mission/tech): ").strip()
        inputs['specific_responsibility'] = input("Specific responsibility from posting: ").strip()

    elif template_type == "python":
        inputs['specific_interest'] = input("Why this company? (be specific): ").strip()
        inputs['blackreach_feature'] = input("Which Blackreach feature relates? (stealth/testing/parallel): ").strip()
        inputs['job_requirement'] = input("Job requirement this relates to: ").strip()
        inputs['company_project'] = input("Team/project mentioned in posting: ").strip()

    elif template_type == "qa":
        inputs['tech_stack'] = input("Testing tech they use (pytest/selenium/etc): ").strip()

    # Generate letter
    letter = TEMPLATES[template_type].format(**inputs)

    # Output
    print("\n" + "="*60)
    print("COVER LETTER:")
    print("="*60 + "\n")
    print(letter)
    print("\n" + "="*60)

    # Save option
    save = input("\nSave to file? (y/n): ").strip().lower()
    if save == 'y':
        filename = f"cover_letter_{inputs['company'].replace(' ', '_').lower()}.txt"
        Path(filename).write_text(letter)
        print(f"✅ Saved to {filename}")

    # Copy to clipboard option (if pyperclip available)
    try:
        import pyperclip
        copy = input("Copy to clipboard? (y/n): ").strip().lower()
        if copy == 'y':
            pyperclip.copy(letter)
            print("✅ Copied to clipboard - paste into application!")
    except ImportError:
        print("\n💡 Install pyperclip to enable clipboard copy: pip install pyperclip")


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════╗
║   Job Application Helper             ║
║   Generate custom cover letters fast ║
╚═══════════════════════════════════════╝
""")

    if len(sys.argv) > 1:
        template_type = sys.argv[1]
    else:
        print("Available templates:")
        print("  1. solutions  - Solutions Engineer / Implementation Engineer")
        print("  2. python     - Python Developer / AI Engineer")
        print("  3. qa         - QA / Test Automation Engineer")
        print()
        choice = input("Choose template (1-3): ").strip()
        template_map = {'1': 'solutions', '2': 'python', '3': 'qa'}
        template_type = template_map.get(choice, choice)

    generate_cover_letter(template_type)
