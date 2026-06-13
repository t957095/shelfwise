# Agents League Hackathon 2026 - Submission Checklist

## Deadline: June 14, 2026 11:59 PM PT

---

## Required Submissions

- [ ] **Public GitHub repository** with complete source code
  - Repo URL: _________________________________
- [ ] **Demo video** (max 5 minutes) uploaded to YouTube/Vimeo
  - Video URL: _________________________________
- [ ] **Project description** (max 500 words)
  - Paste into DevPost / hackathon portal
- [ ] **Architecture diagram** showing Foundry IQ integration
  - File: `architecture.html` (included in repo)
- [ ] **Team member info** including Microsoft Learn username
  - Your Microsoft Learn username: _________________________________

## Code Quality

- [ ] `README.md` is complete and polished
- [ ] `.gitignore` excludes `.env`, `*.db`, `__pycache__`
- [ ] `requirements.txt` has correct versions
- [ ] `Dockerfile` builds successfully
- [ ] Tests pass: `pytest tests/ -v`
- [ ] Linting passes: `ruff check backend/`
- [ ] No hardcoded secrets in source code
- [ ] `LICENSE.md` included

## Demo Video Script

Follow `DEMO_SCRIPT.md` for the 5-minute video.

Key shots to capture:
- [ ] Empty dashboard -> Load Demo -> Live SSE progress
- [ ] Product cards with images, confidence badges, citations
- [ ] Reasoning trace modal walkthrough
- [ ] Portfolio analytics dashboard
- [ ] Export to Shopify/Amazon
- [ ] Architecture diagram pan

## Microsoft Foundry IQ Integration

- [ ] Azure OpenAI resource provisioned (or ready to provision)
- [ ] `FOUNDRY_ENDPOINT` and `FOUNDRY_API_KEY` configured
- [ ] Foundry integration tested and working
- [ ] Citation generation working with source attribution
- [ ] Graceful degradation verified (works without API keys)

## Accessibility (Target: Accessibility Award)

- [ ] WCAG 2.1 AA color contrast
- [ ] Keyboard navigation works
- [ ] ARIA labels present
- [ ] Screen reader friendly
- [ ] `prefers-reduced-motion` support
- [ ] Skip link functional

## Before Submitting

- [ ] Clear the database: `curl -X POST http://localhost:8000/api/clear`
- [ ] Run a fresh demo and verify all 3 products load
- [ ] Test all 4 export formats
- [ ] Verify frontend works on mobile (Chrome DevTools)
- [ ] Test Docker build: `docker-compose up --build`
- [ ] Record demo video in 1920x1080
- [ ] Upload video to unlisted YouTube link
- [ ] Share project on Discord for community vote

## Post-Submission

- [ ] Join Discord vote thread: https://aka.ms/agentsleague/discord
- [ ] Respond to judge questions promptly
- [ ] Winners announced: June 30, 2026
