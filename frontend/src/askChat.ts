/** Lets any page open the chat widget and send a question (e.g. the "Ask about this item" button). */
const EVENT = 'cc:ask-chat'

export function askChat(question: string) {
  window.dispatchEvent(new CustomEvent<string>(EVENT, { detail: question }))
}

export function onAskChat(handler: (question: string) => void) {
  const listener = (e: Event) => handler((e as CustomEvent<string>).detail)
  window.addEventListener(EVENT, listener)
  return () => window.removeEventListener(EVENT, listener)
}
