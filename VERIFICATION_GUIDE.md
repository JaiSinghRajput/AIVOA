# End-to-End Verification Guide

## System Overview

The AIVOA application is a chat-focused AI healthcare professional (HCP) interaction logging system with:
- **Backend:** FastAPI + LangGraph LLM + SQLite
- **Frontend:** React + Redux Toolkit + Vite
- **LLM:** Groq API with automatic fallback strategy
- **Communication:** Single "Log" button orchestrates all actions via natural language processing

## Quick Start

### 1. **Start Backend (Terminal 1)**
```powershell
cd C:\Users\jaisi\OneDrive\Desktop\AIVOA\server
uv run python -m uvicorn main:app --port 8001 --reload
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
INFO:     Started server process [12345]
```

### 2. **Start Frontend (Terminal 2)**
```powershell
cd C:\Users\jaisi\OneDrive\Desktop\AIVOA\client
pnpm dev
```

**Expected Output:**
```
  VITE v8.0.10  ready in 123 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

### 3. **Access Application**
- Open http://localhost:5173 in browser
- Should see 3-column chat interface

## Test Scenarios

### Test 1: Basic Interaction Logging

**Step 1:** Type in chat textarea:
```
Met with Dr. Sarah Chen, endocrinologist, today at 2pm to discuss our new insulin delivery system. 
She was very interested in pricing. We shared brochures and she requested samples for her clinic. 
Very positive discussion, she committed to pilot program evaluation.
```

**Step 2:** Click "Log" button

**Expected Results:**
- ✅ Form fields auto-populate on left:
  - HCP Name: Dr. Sarah Chen
  - Interaction Type: Meeting (or similar)
  - Date: Current date
  - Sentiment: positive
  - Topics: insulin delivery, pricing
  - Materials: brochures
  - Samples: yes
  - Outcomes: pilot program evaluation

- ✅ Summary appears in right panel:
  - Includes all key details (type, date, topics, sentiment, materials, outcomes)

- ✅ Recommendations appear in right panel:
  - 🎯 Strong Interest: Send detailed pricing, ROI data, and clinical evidence.
  - 📅 Schedule a follow-up meeting to discuss implementation timeline.
  - 💼 Propose pilot program or volume discount for commitment.
  - ✅ Follow up specifically on: insulin delivery system, pricing
  - 📮 Send promised materials and track delivery confirmation.

### Test 2: Negative Sentiment Detection

**Step 1:** Type:
```
Called Dr. Michael Foster at St. Mary's Hospital. He was dismissive of our pitch. 
Main concerns were high cost compared to competitors and unknown effectiveness in their patient population. 
He said he'd get back to us but seemed uninterested. Definitely not positive.
```

**Step 2:** Click "Log"

**Expected Results:**
- ✅ Sentiment: negative
- ✅ Recommendations include:
  - ⚠️ Address Concerns: Prepare responses to objections raised.
  - 💡 Compile competitive analysis and cost-benefit comparison.
  - 🤝 Consider escalation to senior stakeholder or offering alternatives.
  - 💌 Follow up with personalized proposal addressing specific concerns.

### Test 3: Auto-Summary from Chat

**Step 1:** Type:
```
Dr. Emma Rodrigues meeting went well. Discussed our cardiology device. 
She asked about regulatory approvals and timeline to market. 
Provided FDA documentation. She wants to learn more.
```

**Step 2:** Click "Log"

**Step 3:** Type in chat:
```
Can you give me a summary of that meeting?
```

**Step 4:** Click "Log"

**Expected Results:**
- ✅ Frontend detects "summary" keyword
- ✅ Automatically calls `/interactions/{id}/summary` endpoint
- ✅ Comprehensive summary displays showing all captured fields

### Test 4: Auto-Follow-up Recommendations from Chat

**Step 1:** Log an interaction (see Test 1)

**Step 2:** Type in chat:
```
What should be the next steps and follow-up actions?
```

**Step 3:** Click "Log"

**Expected Results:**
- ✅ Frontend detects "follow", "next", "action", "recommend" keywords
- ✅ Automatically calls `/interactions/{id}/followups` endpoint
- ✅ Updated recommendations display

### Test 5: Previous Interactions List

**Step 1:** Create multiple interactions (run Test 1-4 scenarios)

**Step 2:** Look at bottom of right panel for past interactions list

**Expected Results:**
- ✅ Shows max 5 most recent interactions
- ✅ Each shows date and HCP name
- ✅ Clicking on interaction loads its details
- ✅ Form fields populate with interaction data
- ✅ Summary and recommendations auto-fetch

## API Endpoint Verification

### Test 1: POST /tools/log

**Request:**
```bash
curl -X POST http://127.0.0.1:8001/tools/log \
  -H "Content-Type: application/json" \
  -d '{"text":"Dr. Smith meeting went great. Discussed pricing and samples.", "hcp_id":null}'
```

**Expected Response:**
```json
{
  "interaction": {
    "id": 1,
    "hcp_id": 1,
    "interaction_type": "Meeting",
    "datetime": "2026-05-05T10:30:00",
    "attendees": "Dr. Smith",
    "topics": "pricing, samples",
    "materials_shared": "null",
    "samples_distributed": "yes",
    "sentiment": "positive",
    "outcomes": "null",
    "follow_up": "null",
    "notes": "Dr. Smith meeting went great..."
  },
  "extracted": {
    "hcp_name": "Dr. Smith",
    "interaction_type": "Meeting",
    "datetime": "2026-05-05T10:30:00",
    "sentiment": "positive",
    "topics": "pricing, samples",
    "samples_distributed": "yes"
  },
  "summary": "Type: Meeting | Date: 2026-05-05T10:30... | Sentiment: POSITIVE | Samples: yes | ...",
  "recommendations": [
    "🎯 Strong Interest: Send detailed pricing...",
    "💼 Propose pilot program...",
    "..."
  ]
}
```

### Test 2: GET /interactions/{id}/summary

**Request:**
```bash
curl http://127.0.0.1:8001/interactions/1/summary
```

**Expected Response:**
```json
{
  "summary": "Type: Meeting | Date: 2026-05-05T10:30... | Topics: pricing, samples | ...",
  "interaction": { /* full interaction object */ }
}
```

### Test 3: GET /interactions/{id}/followups

**Request:**
```bash
curl http://127.0.0.1:8001/interactions/1/followups
```

**Expected Response:**
```json
{
  "recommendations": [
    "🎯 Strong Interest: Send detailed pricing...",
    "💼 Propose pilot program...",
    "..."
  ],
  "interaction": { /* full interaction object */ }
}
```

### Test 4: GET /interactions

**Request:**
```bash
curl http://127.0.0.1:8001/interactions
```

**Expected Response:**
```json
[
  {
    "id": 1,
    "hcp_id": 1,
    "interaction_type": "Meeting",
    "datetime": "2026-05-05T10:30:00",
    ...
  },
  ...
]
```

## Database Verification

### Check if interactions are persisting:

```powershell
cd C:\Users\jaisi\OneDrive\Desktop\AIVOA\server
uv run python -c "
from db import get_session
from models import Interaction

with get_session() as session:
    interactions = session.query(Interaction).all()
    print(f'Total interactions: {len(interactions)}')
    for i in interactions:
        print(f'  - ID {i.id}: {i.hcp_id}, Type: {i.interaction_type}, Sentiment: {i.sentiment}')
"
```

**Expected Output:**
```
Total interactions: 5
  - ID 1: 1, Type: Meeting, Sentiment: positive
  - ID 2: 2, Type: Meeting, Sentiment: negative
  ...
```

## LLM Extraction Verification

### Verify Groq API is working:

```powershell
cd C:\Users\jaisi\OneDrive\Desktop\AIVOA\server
uv run python -c "
from llm import extract_entities

text = 'Met with Dr. John Smith from Boston Medical Center. Very positive meeting about our glucose monitor system. We showed him the data and he requested samples for evaluation.'

result = extract_entities(text)
print('Extracted fields:')
for key, val in result.items():
    if val:
        print(f'  {key}: {val}')
"
```

**Expected Output:**
```
Extracted fields:
  hcp_name: Dr. John Smith
  interaction_type: Meeting
  sentiment: positive
  topics: glucose monitor system, data review
  samples_distributed: yes
  ...
```

## Troubleshooting

### Issue: "Connection refused" on http://127.0.0.1:8001

**Solution:** Ensure backend is running on port 8001
```powershell
netstat -ano | findstr :8001
```

### Issue: "GROQ_API_KEY not found"

**Solution:** Create `.env` file in `server/` directory:
```
GROQ_API_KEY=your_actual_groq_key_here
```

### Issue: Frontend shows "Failed to fetch"

**Solution:** Check CORS headers and port numbers:
- Backend: http://127.0.0.1:8001
- Frontend: http://localhost:5173
- Check browser console for exact error

### Issue: Recommendations are generic/not context-aware

**Solution:** Verify sentiment detection is working
```powershell
# Run sentiment test
uv run python -c "
from llm import extract_entities
result = extract_entities('Dr. Smith was very interested and wants to move forward!')
print(f'Sentiment: {result.get(\"sentiment\")}')"
```

## Performance Benchmarks

- **Log endpoint response time:** < 500ms (with Groq API call)
- **Summary endpoint response time:** < 100ms (local calculation)
- **Recommendations endpoint response time:** < 100ms (local calculation)
- **Frontend build size:** ~75 KB gzipped
- **Database query time:** < 50ms for typical queries

## Success Criteria

✅ All four test scenarios complete without errors
✅ Form fields auto-populate from extraction
✅ Sentiment-based recommendations differ correctly
✅ Previous interactions load and refresh correctly
✅ Backend API endpoints return correct response structure
✅ Database persists interactions across server restarts
✅ LLM extraction captures 8+ fields consistently
✅ No JavaScript console errors in frontend
