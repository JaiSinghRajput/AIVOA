import { useEffect } from 'react'
import {
  clearInsights,
  createHcp,
  fetchSummary,
  loadHcps,
  loadInteractions,
  selectCrm,
  sendAssistantMessage,
  setText,
  setSelectedInteractionId,
  setSelectedHcpId,
  setInteractionType,
  setDate,
  setTime,
  setAttendees,
  setTopics,
  setSentiment,
  setOutcomes,
  setFollowUp,
  setMaterials,
  setSamples,
  type Interaction,
} from './features/crm/crmSlice'
import { useAppDispatch, useAppSelector } from './store/hooks'

function renderCapturedItems(items: string[], label: string) {
  if (!items.length) {
    return (
      <div>
        <label className="text-sm font-medium text-slate-300">{label}</label>
        <div className="mt-2 rounded bg-slate-800 p-2 text-sm text-slate-500">—</div>
      </div>
    )
  }

  if (items.length === 1 && /^(yes|no)$/i.test(items[0].trim())) {
    return (
      <div>
        <label className="text-sm font-medium text-slate-300">{label}</label>
        <div className="mt-2 inline-flex rounded-md bg-slate-800 px-3 py-2 text-sm text-slate-100">
          {items[0].charAt(0).toUpperCase() + items[0].slice(1)}
        </div>
      </div>
    )
  }

  return (
    <div>
      <label className="text-sm font-medium text-slate-300">{label}</label>
      <ul className="mt-2 space-y-1">
        {items.map((item, index) => (
          <li key={index} className="rounded bg-slate-800 p-2 text-sm text-slate-200">
            • {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function App() {
  const dispatch = useAppDispatch()
  const state = useAppSelector(selectCrm)

  const {
    text,
    result,
    summary,
    recommendations,
    assistantMessage,
    hcpQuery,
    hcps,
    selectedHcpId,
    interactions,
    selectedInteractionId,
    loading,
    error,
    interactionType,
    date,
    time,
    attendees,
    topics,
    materials,
    samples,
    outcomes,
    followUp,
    sentiment,
  } = state

  const lastLoggedMessage = result?.interaction?.notes ?? ''
  const selectedHcpName = hcps.find(h => h.id === selectedHcpId)?.name || `HCP #${selectedHcpId}`

  useEffect(() => {
    void dispatch(loadInteractions(null))
    void dispatch(loadHcps())
  }, [dispatch])

  const handleLogText = async () => {
    const prompt = text.trim()
    if (!prompt) return

    dispatch(clearInsights())
    const action = await dispatch(sendAssistantMessage({ text: prompt, hcpId: selectedHcpId, interactionId: selectedInteractionId }))
    if (sendAssistantMessage.fulfilled.match(action)) {
      const promptLower = prompt.toLowerCase()
      const wantsSummary = /\b(summary|overview|recap)\b/.test(promptLower)

      if (action.payload.interaction) {
        await dispatch(loadInteractions(selectedHcpId))
        
        // If this was an update to the currently selected interaction, refresh the form
        if (selectedInteractionId === action.payload.interaction.id) {
          await handleSelectInteraction(action.payload.interaction)
        }
      }

      if (wantsSummary && action.payload.interaction) {
        await dispatch(fetchSummary(action.payload.interaction.id))
      }

      dispatch(setText(''))
    }
  }

  const handleCreateHcp = async () => {
    const name = (hcpQuery || '').trim()
    if (!name) return
    const action = await dispatch(createHcp({ name }))
    if (createHcp.fulfilled.match(action)) {
      await dispatch(loadInteractions(action.payload.id))
    }
  }

  const handleSelectInteraction = async (interaction: Interaction) => {
    // Set the selected interaction ID
    dispatch(setSelectedInteractionId(interaction.id))
    
    // Clear the textarea for new input (the notes are shown in conversation history)
    dispatch(setText(''))
    
    // Always set HCP first
    if (interaction.hcp_id) {
      dispatch(setSelectedHcpId(interaction.hcp_id))
    }
    
    // Populate the form with all the interaction details - always dispatch even if empty to reset
    dispatch(setInteractionType(interaction.interaction_type || 'Meeting'))
    if (interaction.datetime) {
      dispatch(setDate(interaction.datetime.slice(0, 10)))
      dispatch(setTime(interaction.datetime.slice(11, 16)))
    } else {
      dispatch(setDate(new Date().toISOString().slice(0, 10)))
      dispatch(setTime(new Date().toISOString().slice(11, 16)))
    }
    dispatch(setAttendees(interaction.attendees || ''))
    dispatch(setTopics(interaction.topics || null))
    dispatch(setSentiment(interaction.sentiment || 'neutral'))
    dispatch(setOutcomes(interaction.outcomes || null))
    dispatch(setFollowUp(interaction.follow_up || null))
    dispatch(setMaterials(interaction.materials_shared ? interaction.materials_shared.split(',').map(m => m.trim()).filter(Boolean) : []))
    dispatch(setSamples(interaction.samples_distributed ? interaction.samples_distributed.split(',').map(s => s.trim()).filter(Boolean) : []))
    
    dispatch(clearInsights())
  }

  const handleNewInteraction = () => {
    dispatch(setSelectedInteractionId(null))
    dispatch(setText(''))
    dispatch(clearInsights())
  }

  return (
    <main className="h-full w-full overflow-hidden bg-slate-950 text-slate-100 p-4 md:p-6">
      <div className="grid h-full w-full min-h-0 min-w-0 grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)] lg:gap-6">
        {/* Left: Display form (auto-populated from chat) */}
        <section className="flex h-full min-h-0 min-w-0 flex-col rounded-xl border border-slate-800 bg-slate-900/70 p-6 shadow-2xl">
          <div className="flex-1 overflow-y-auto pr-1">
            <h1 className="text-2xl font-bold">Interaction Details</h1>
            <p className="mt-1 text-sm text-slate-400">Auto-populated from AI Assistant chat</p>

          {/* HCP Name */}
          <div className="mt-6">
            <label className="text-sm font-medium text-slate-300">HCP Name</label>
            <div className="mt-2 flex items-center justify-between rounded-md bg-slate-800 p-3 text-slate-100">
              <span>{hcpQuery || (selectedHcpId ? selectedHcpName : '—')}</span>
              {(selectedHcpId || hcpQuery) && (
                <button onClick={handleCreateHcp} className="rounded bg-indigo-600 px-2 py-1 text-xs hover:bg-indigo-500">
                  Create
                </button>
              )}
            </div>
          </div>

          {/* Interaction Type, Date, Time */}
          <div className="mt-4 grid grid-cols-3 gap-3">
            <div>
              <label className="text-sm font-medium text-slate-300">Type</label>
              <div className="mt-1 rounded bg-slate-800 p-2 text-sm text-slate-100">{interactionType || '—'}</div>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-300">Date</label>
              <div className="mt-1 rounded bg-slate-800 p-2 text-sm text-slate-100">{date || '—'}</div>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-300">Time</label>
              <div className="mt-1 rounded bg-slate-800 p-2 text-sm text-slate-100">{time || '—'}</div>
            </div>
          </div>

          {/* Attendees */}
          <div className="mt-4">
            <label className="text-sm font-medium text-slate-300">Attendees</label>
            <div className="mt-1 rounded bg-slate-800 p-3 text-slate-100">{attendees && attendees.trim() ? attendees : '—'}</div>
          </div>

          {/* Topics */}
          <div className="mt-4">
            <label className="text-sm font-medium text-slate-300">Topics Discussed</label>
            <div className="mt-1 rounded bg-slate-800 p-3 text-slate-100">{topics && topics.trim() ? topics : '—'}</div>
          </div>

          {/* Materials and Samples */}
          <div className="mt-4 grid grid-cols-2 gap-4">
            {renderCapturedItems(materials, 'Materials Shared')}
            {renderCapturedItems(samples, 'Samples Distributed')}
          </div>

          {/* Sentiment */}
          <div className="mt-4">
            <label className="text-sm font-medium text-slate-300">HCP Sentiment</label>
            <div className={`mt-1 rounded p-2 text-center text-sm font-medium ${sentiment === 'positive' ? 'bg-green-900 text-green-100' : sentiment === 'negative' ? 'bg-red-900 text-red-100' : 'bg-slate-800 text-slate-100'}`}>
              {sentiment ? sentiment.charAt(0).toUpperCase() + sentiment.slice(1) : '—'}
            </div>
          </div>

          {/* Outcomes */}
          <div className="mt-4">
            <label className="text-sm font-medium text-slate-300">Outcomes</label>
            <div className="mt-1 rounded bg-slate-800 p-3 text-slate-100">{outcomes || '—'}</div>
          </div>

          {/* Follow-up Actions */}
          <div className="mt-4">
            <label className="text-sm font-medium text-slate-300">Follow-up Actions</label>
            <div className="mt-1 rounded bg-slate-800 p-3 text-slate-100">{followUp || '—'}</div>
          </div>

          {error && <p className="mt-4 text-sm text-rose-300">⚠️ {error}</p>}
          {loading && <p className="mt-4 text-sm text-slate-400">⏳ Processing...</p>}
          </div>
        </section>

        {/* Right: Chat Interface - Primary Interaction */}
        <aside className="flex h-full min-h-0 min-w-0 flex-col rounded-xl border border-slate-800 bg-slate-900/70 p-6 shadow-2xl">
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">🤖</span>
                <h3 className="font-bold text-slate-100">AI Assistant</h3>
              </div>
              <p className="text-xs text-slate-400">Log interaction details via natural chat. I'll auto-populate the form and provide insights.</p>
            </div>

            {/* Chat Messages */}
            <div className="mb-4 flex-1 space-y-3 overflow-y-auto pr-1">
              {selectedInteractionId && !result && (
                <div className="text-xs text-slate-400 italic">
                  <p className="mb-2">📝 {selectedHcpName} - Conversation History</p>
                  {(() => {
                    const selectedInteraction = interactions.find(i => i.id === selectedInteractionId)
                    if (!selectedInteraction || !selectedInteraction.notes) {
                      return <p>No conversation history yet.</p>
                    }
                    // Simple display of notes - can be enhanced with better formatting
                    return (
                      <div className="space-y-2 text-slate-300">
                        <p className="whitespace-pre-wrap warp-break-words">{selectedInteraction.notes}</p>
                      </div>
                    )
                  })()}
                </div>
              )}
              {result && (
                <>
                  <div className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-blue-600 px-4 py-3 text-sm text-white shadow-lg">
                      <p className="text-[11px] uppercase tracking-wide text-blue-100">You</p>
                      <p className="mt-1 whitespace-pre-wrap">{result.request_text || lastLoggedMessage}</p>
                    </div>
                  </div>
                  <div className="flex justify-start">
                    <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-emerald-800 bg-emerald-950/70 px-4 py-3 text-sm text-emerald-50 shadow-lg">
                      <p className="text-[11px] uppercase tracking-wide text-emerald-200">AI Assistant</p>
                      <p className="mt-1">{assistantMessage || result.assistant_message || 'Done.'}</p>
                    </div>
                  </div>
                </>
              )}

              {result?.search_results && result.search_results.length > 0 && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-cyan-800 bg-cyan-950/70 px-4 py-3 text-sm text-slate-100 shadow-lg">
                    <p className="text-[11px] uppercase tracking-wide text-cyan-200">AI Assistant</p>
                    <p className="mt-1 font-medium text-cyan-100">Search results</p>
                    <ul className="mt-2 space-y-1">
                      {result.search_results.map((hcp) => (
                        <li key={hcp.id}>
                          {hcp.name}
                          {hcp.specialty ? ` · ${hcp.specialty}` : ''}
                          {hcp.location ? ` · ${hcp.location}` : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {summary && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-purple-800 bg-purple-950/70 px-4 py-3 text-sm text-slate-100 shadow-lg">
                    <p className="text-[11px] uppercase tracking-wide text-purple-200">AI Assistant</p>
                    <p className="mt-1 whitespace-pre-wrap">{summary}</p>
                  </div>
                </div>
              )}

              {recommendations && recommendations.length > 0 && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-amber-800 bg-amber-950/70 px-4 py-3 text-sm text-slate-100 shadow-lg">
                    <p className="text-[11px] uppercase tracking-wide text-amber-200">AI Assistant</p>
                    <p className="mt-1 font-medium text-amber-100">{result?.intent === 'followup' ? 'Scheduled Followup' : 'Recommended follow-ups'}</p>
                    <ul className="mt-2 space-y-1">
                      {recommendations.map((rec, idx) => (
                        <li key={idx}>• {rec}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {loading && <p className="text-slate-400 text-sm italic">⏳ Processing your request...</p>}
            </div>
          </div>

          {/* Chat Input */}
          <div className="border-t border-slate-700 pt-4">
            {selectedInteractionId && (
              <div className="mb-3 flex items-center justify-between bg-slate-800 rounded p-2 text-xs text-slate-300">
                <span>✏️ Editing {selectedHcpName}</span>
                <button
                  onClick={handleNewInteraction}
                  className="rounded px-2 py-1 text-slate-200 hover:bg-slate-700 transition-colors"
                >
                  New
                </button>
              </div>
            )}
            <textarea
              value={text}
              onChange={(e) => dispatch(setText(e.target.value))}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                  void handleLogText()
                }
              }}
              placeholder="Describe interaction... (e.g., 'Met Dr. Smith, discussed X, positive sentiment')"
              className="w-full min-h-20 rounded-md bg-slate-800 p-3 text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
            <div className="mt-3 flex justify-end gap-2">
              <button
                onClick={() => void handleLogText()}
                disabled={!text.trim() || loading}
                className="rounded-md bg-blue-600 px-6 py-2 font-medium hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? '⏳ Logging...' : '📤 Log'}
              </button>
            </div>
          </div>

          {error && <p className="mt-2 text-xs text-rose-300">⚠️ {error}</p>}

          {/* Past Interactions */}
          <div className="mt-6 border-t border-slate-700 pt-4">
            <h4 className="text-sm font-semibold text-slate-200 mb-2">📚 Past Interactions</h4>
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {interactions.slice(0, 5).map((interaction) => (
                <div
                  key={interaction.id}
                  onClick={() => void handleSelectInteraction(interaction)}
                  className={`p-2 rounded text-xs cursor-pointer transition-colors ${
                    selectedInteractionId === interaction.id
                      ? 'bg-slate-700 border border-blue-600'
                      : 'bg-slate-800 hover:bg-slate-700'
                  }`}
                >
                  <div className="flex justify-between">
                    <span className="font-medium">{interaction.topics || 'Interaction'}</span>
                    <span className={`text-xs px-2 py-1 rounded ${interaction.sentiment === 'positive' ? 'bg-green-900 text-green-100' : interaction.sentiment === 'negative' ? 'bg-red-900 text-red-100' : 'bg-slate-600'}`}>
                      {interaction.sentiment}
                    </span>
                  </div>
                  <p className="text-slate-400 mt-1">{interaction.notes?.slice(0, 50)}...</p>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </main>
  )
}
