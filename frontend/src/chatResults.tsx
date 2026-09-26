import { createContext, useContext, useState, type ReactNode } from 'react'
import type { PageResults } from './api'

/** Chat search results currently shown on the Products page. `id` changes on every new result set. */
export interface ShownResults extends PageResults {
  id: number
}

interface ChatResultsState {
  results: ShownResults | null
  show: (results: PageResults) => void
  clear: () => void
}

const ChatResultsContext = createContext<ChatResultsState | null>(null)

export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<ShownResults | null>(null)
  const value: ChatResultsState = {
    results,
    show: (r) => setResults({ ...r, id: Date.now() }),
    clear: () => setResults(null),
  }
  return <ChatResultsContext.Provider value={value}>{children}</ChatResultsContext.Provider>
}

export function useChatResults() {
  const ctx = useContext(ChatResultsContext)
  if (!ctx) throw new Error('useChatResults must be used inside <ChatResultsProvider>')
  return ctx
}
