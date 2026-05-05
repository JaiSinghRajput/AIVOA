import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { RootState } from '../../store/store'

type Sentiment = 'positive' | 'neutral' | 'negative' | string

export interface Hcp {
  id: number
  name: string
  specialty?: string | null
  location?: string | null
}

export interface Interaction {
  id: number
  hcp_id?: number | null
  interaction_type?: string | null
  datetime?: string | null
  attendees?: string | null
  topics?: string | null
  materials_shared?: string | null
  samples_distributed?: string | null
  sentiment?: Sentiment | null
  outcomes?: string | null
  follow_up?: string | null
  notes?: string | null
}

interface LogResponse {
  intent?: 'log' | 'summary' | 'followup' | 'search' | 'update' | 'generic'
  request_text?: string
  assistant_message?: string
  interaction?: Interaction
  extracted?: Partial<Interaction> & { hcp_name?: string | null }
  summary?: string
  recommendations?: string[]
  search_results?: Hcp[]
}

interface SummaryResponse {
  summary: string
}

interface FollowupResponse {
  recommendations: string[]
}

interface CreateHcpPayload {
  name: string
}

interface LogInteractionPayload {
  text: string
  hcpId?: number | null
  interactionId?: number | null
}

interface CrmState {
  text: string
  hcpQuery: string
  hcps: Hcp[]
  selectedHcpId: number | null
  interactions: Interaction[]
  selectedInteractionId: number | null
  result: LogResponse | null
  assistantMessage: string | null
  summary: string | null
  recommendations: string[] | null
  loading: boolean
  error: string | null
  // Form fields
  interactionType: string
  date: string
  time: string
  attendees: string
  sentiment: Sentiment
  topics: string | null
  materials: string[]
  samples: string[]
  outcomes: string | null
  followUp: string | null
}

const API_BASE = 'http://127.0.0.1:8000'

const initialState: CrmState = {
  text: '',
  hcpQuery: '',
  hcps: [],
  selectedHcpId: null,
  interactions: [],
  selectedInteractionId: null,
  result: null,
  assistantMessage: null,
  summary: null,
  recommendations: null,
  loading: false,
  error: null,
  interactionType: 'Meeting',
  date: new Date().toISOString().slice(0, 10),
  time: new Date().toISOString().slice(11, 16),
  attendees: '',
  sentiment: 'neutral',
  topics: null,
  materials: [],
  samples: [],
  outcomes: null,
  followUp: null,
}

async function parseJsonResponse<T>(res: Response): Promise<T> {
  const payload = await res.json()
  if (!res.ok) {
    const detail = typeof payload?.detail === 'string' ? payload.detail : 'Request failed'
    throw new Error(detail)
  }
  return payload as T
}

export const searchHcps = createAsyncThunk<Hcp[], string>('crm/searchHcps', async (query: string) => {
  if (!query.trim()) {
    return []
  }
  const res = await fetch(`${API_BASE}/hcp/search?q=${encodeURIComponent(query)}`)
  return parseJsonResponse<Hcp[]>(res)
})

export const createHcp = createAsyncThunk<Hcp, CreateHcpPayload>('crm/createHcp', async ({ name }) => {
  const res = await fetch(`${API_BASE}/hcp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  return parseJsonResponse<Hcp>(res)
})

export const loadInteractions = createAsyncThunk<Interaction[], number | null | undefined>(
  'crm/loadInteractions',
  async (hcpId) => {
    const url =
      typeof hcpId === 'number' ? `${API_BASE}/interactions?hcp_id=${hcpId}` : `${API_BASE}/interactions`
    const res = await fetch(url)
    return parseJsonResponse<Interaction[]>(res)
  },
)

export const loadHcps = createAsyncThunk<Hcp[], void>('crm/loadHcps', async () => {
  const res = await fetch(`${API_BASE}/hcp`)
  return parseJsonResponse<Hcp[]>(res)
})

export const sendAssistantMessage = createAsyncThunk<LogResponse, LogInteractionPayload>(
  'crm/sendAssistantMessage',
  async ({ text, hcpId, interactionId }) => {
    const res = await fetch(`${API_BASE}/tools/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, hcp_id: hcpId ?? null, interaction_id: interactionId ?? null }),
    })
    return parseJsonResponse<LogResponse>(res)
  },
)

export const fetchSummary = createAsyncThunk<string, number>('crm/fetchSummary', async (interactionId: number) => {
  const res = await fetch(`${API_BASE}/interactions/${interactionId}/summary`)
  const data = await parseJsonResponse<SummaryResponse>(res)
  return data.summary
})

export const fetchRecommendations = createAsyncThunk<string[], number>(
  'crm/fetchRecommendations',
  async (interactionId: number) => {
    const res = await fetch(`${API_BASE}/interactions/${interactionId}/followups`)
    const data = await parseJsonResponse<FollowupResponse>(res)
    return data.recommendations
  },
)

const crmSlice = createSlice({
  name: 'crm',
  initialState,
  reducers: {
    setText(state, action: PayloadAction<string>) {
      state.text = action.payload
    },
    setHcpQuery(state, action: PayloadAction<string>) {
      state.hcpQuery = action.payload
    },
    setSelectedHcpId(state, action: PayloadAction<number | null>) {
      state.selectedHcpId = action.payload
    },
    setSelectedInteractionId(state, action: PayloadAction<number | null>) {
      state.selectedInteractionId = action.payload
    },
    clearInsights(state) {
      state.result = null
      state.assistantMessage = null
      state.summary = null
      state.recommendations = null
      state.error = null
    },
    // Form setters
    setInteractionType(state, action: PayloadAction<string>) {
      state.interactionType = action.payload
    },
    setDate(state, action: PayloadAction<string>) {
      state.date = action.payload
    },
    setTime(state, action: PayloadAction<string>) {
      state.time = action.payload
    },
    setAttendees(state, action: PayloadAction<string>) {
      state.attendees = action.payload
    },
    setTopics(state, action: PayloadAction<string | null>) {
      state.topics = action.payload
    },
    setMaterials(state, action: PayloadAction<string[]>) {
      state.materials = action.payload
    },
    setSamples(state, action: PayloadAction<string[]>) {
      state.samples = action.payload
    },
    setOutcomes(state, action: PayloadAction<string | null>) {
      state.outcomes = action.payload
    },
    setFollowUp(state, action: PayloadAction<string | null>) {
      state.followUp = action.payload
    },
    setSentiment(state, action: PayloadAction<Sentiment>) {
      state.sentiment = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(searchHcps.fulfilled, (state, action) => {
        state.hcps = action.payload
      })
      .addCase(createHcp.fulfilled, (state, action) => {
        state.hcps = [action.payload, ...state.hcps.filter((h) => h.id !== action.payload.id)]
        state.selectedHcpId = action.payload.id
      })
      .addCase(loadInteractions.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(loadInteractions.fulfilled, (state, action) => {
        state.loading = false
        state.interactions = action.payload
        // Extract unique HCPs from interactions
        const hcpMap = new Map<number, Hcp>()
        for (const interaction of action.payload) {
          if (interaction.hcp_id) {
            // Create a minimal HCP object from interaction data
            const hcpKey = `hcp_${interaction.hcp_id}`
            if (!hcpMap.has(interaction.hcp_id)) {
              hcpMap.set(interaction.hcp_id, {
                id: interaction.hcp_id,
                name: hcpKey, // Fallback name
              })
            }
          }
        }
        state.hcps = Array.from(hcpMap.values())
      })
      .addCase(loadInteractions.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message ?? 'Failed to load interactions'
      })
      .addCase(loadHcps.fulfilled, (state, action) => {
        state.hcps = action.payload
      })
      .addCase(sendAssistantMessage.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(sendAssistantMessage.fulfilled, (state, action) => {
        state.loading = false
        state.result = action.payload
        state.assistantMessage = action.payload.assistant_message ?? null
        const extracted = action.payload.extracted ?? {}
        const inter = action.payload.interaction
        const wasExistingInteraction = state.selectedInteractionId === inter?.id

        if (inter) {
          state.selectedInteractionId = inter.id
          
          // If updating an existing interaction, update it in the list instead of adding
          const existingIndex = state.interactions.findIndex(i => i.id === inter.id)
          if (existingIndex >= 0) {
            state.interactions[existingIndex] = inter
          } else {
            // New interaction - add to front
            state.interactions = [inter, ...state.interactions]
          }

          // Auto-populate form fields from interaction and extracted data
          // But don't fill the textarea if this was a continuation of an existing interaction
          if (!wasExistingInteraction) {
            state.text = inter.notes ?? state.text
          } else {
            // Clear textarea after adding to existing interaction
            state.text = ''
          }
          
          state.interactionType = inter.interaction_type ?? state.interactionType
          state.date = inter.datetime?.slice(0, 10) ?? state.date
          state.time = inter.datetime?.slice(11, 16) ?? state.time
          state.attendees = inter.attendees ?? state.attendees
          state.topics = inter.topics ?? state.topics
          state.sentiment = inter.sentiment ?? state.sentiment
          state.outcomes = inter.outcomes ?? state.outcomes
          state.followUp = inter.follow_up ?? state.followUp

          if (inter.materials_shared) {
            state.materials = [inter.materials_shared]
          }
          if (inter.samples_distributed) {
            state.samples = [inter.samples_distributed]
          }
          if (inter.hcp_id) {
            state.selectedHcpId = inter.hcp_id
          }

          state.hcpQuery = extracted.hcp_name ?? state.hcpQuery
        }

        if (action.payload.summary) {
          state.summary = action.payload.summary
        }
        if (action.payload.recommendations) {
          state.recommendations = action.payload.recommendations
        }
      })
      .addCase(sendAssistantMessage.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message ?? 'Failed to log interaction'
      })
      .addCase(fetchSummary.fulfilled, (state, action) => {
        state.summary = action.payload
        state.loading = false
      })
      .addCase(fetchRecommendations.fulfilled, (state, action) => {
        state.recommendations = action.payload
        state.loading = false
      })
  },
})

export const {
  setText,
  setHcpQuery,
  setSelectedHcpId,
  setSelectedInteractionId,
  clearInsights,
  setInteractionType,
  setDate,
  setTime,
  setAttendees,
  setTopics,
  setMaterials,
  setSamples,
  setOutcomes,
  setFollowUp,
  setSentiment,
} = crmSlice.actions

export const selectCrm = (state: RootState) => state.crm

export default crmSlice.reducer
