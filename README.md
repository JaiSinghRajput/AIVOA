## Product Name

AI-First CRM – HCP Interaction Module

## Objective

Build an AI-powered CRM module for pharmaceutical/medical sales representatives to log, manage, and optimize interactions with Healthcare Professionals (HCPs) using both structured input and conversational AI.

---

## Problem Statement

Field reps spend significant time manually logging doctor interactions, leading to:

* Incomplete or inaccurate data
* Low CRM adoption
* Lack of actionable insights

---

## Solution Overview

Provide a dual-interface system:

1. Structured Form Input
2. AI Conversational Logging (LLM-powered)

The system uses a LangGraph-based AI agent to interpret, structure, store, and enhance interaction data.

---

## Key Features

### 1. Log Interaction Screen

#### A. Form-Based Logging

Fields:

* HCP Name
* Interaction Type
* Date & Time
* Attendees
* Topics Discussed
* Materials Shared
* Samples Distributed
* Sentiment
* Outcomes
* Follow-up Actions

#### B. AI Chat Logging

User enters natural language input.
Example:
"Met Dr. Sharma, discussed insulin product, he was interested but concerned about price"

System:

* Extract entities
* Populate form automatically
* Suggest follow-ups

---

## AI Agent (LangGraph) Design

### Agent Responsibilities

* Interpret user intent
* Route to appropriate tools
* Extract structured data
* Maintain conversation context
* Ensure data consistency

---

## Tools (Minimum 5)

### 1. Log Interaction Tool

Input: raw text / form data
Process:

* LLM extracts entities (HCP, sentiment, products, etc.)
* Converts to structured JSON
  Output:
* Stored interaction record

### 2. Edit Interaction Tool

Allows updates to existing interaction records.
Example:
"Change sentiment to positive"

---

### 3. HCP Lookup Tool

Search and retrieve doctor details.
Supports autocomplete and validation.

---

### 4. Follow-up Recommendation Tool

Uses LLM to suggest next actions based on interaction.

---

### 5. Interaction Summary Tool

Fetches and summarizes past interactions with an HCP.

---

## User Flow

1. User opens Log Interaction Screen
2. Chooses:

   * Fill form manually OR
   * Use AI chat
3. AI agent processes input
4. Data is structured and stored
5. Suggestions are shown

---

## Technical Architecture

### Frontend

* React
* Redux for state management

### Backend

* FastAPI

### AI Layer

* LangGraph Agent
* Groq LLM (gemma2-9b-it)

### Database

* PostgreSQL / MySQL

---

## Data Model (Simplified)

### HCP Table

* id
* name
* specialty
* location

### Interaction Table

* id
* hcp_id
* interaction_type
* datetime
* notes
* sentiment
* follow_up

---

## Non-Functional Requirements

* Low latency (<2s response time for AI suggestions)
* Scalable architecture
* Secure data handling

---

## Success Metrics

* Reduction in manual entry time
* Increase in CRM usage
* Accuracy of AI extraction

---

## Deliverables

* Working web app github repo with client and server folders
---

## Future Enhancements

* Voice-to-text logging
* Predictive sales insights
* Integration with email/calendar
