import { useState, useRef, useEffect } from 'react'

function Chatbox({ schedule, tanks, vessels, compact = false }) {
  const [messages, setMessages] = useState([
    { role: 'system', content: 'Welcome to OASIS! I can help you interpret and optimize your refinery schedule.' }
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef(null)

  // Auto-scroll to bottom of messages when new ones are added
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Also scroll when streaming updates occur
  useEffect(() => {
    if (isStreaming) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [isStreaming])

  const handleSendMessage = async (e) => {
    e.preventDefault()
    if (!inputValue.trim()) return

    // Add user message
    const userMessage = { role: 'user', content: inputValue }
    setMessages(prev => [...prev, userMessage])
    const currentMessage = inputValue
    setInputValue('')
    setIsLoading(true)
    setIsStreaming(true)

    try {
      // Create a placeholder assistant message that we'll update
      const placeholderMessage = {
        role: 'assistant',
        content: '',
        function_calls: 0,
        functions_used: [],
        isStreaming: true
      }

      let messageIndex
      setMessages(prev => {
        const newMessages = [...prev, placeholderMessage]
        messageIndex = newMessages.length - 1
        return newMessages
      })

      // Use EventSource for streaming
      const response = await fetch('http://localhost:5001/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: currentMessage,
          conversation_history: messages
        })
      })

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      let buffer = ''
      let currentResponse = ''
      let functionsUsed = []
      let functionCount = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // Keep incomplete line in buffer
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              switch (data.type) {
                case 'function_start':
                  functionsUsed = data.functions
                  functionCount = data.functions.length
                  setMessages(prev => {
                    const newMessages = [...prev]
                    newMessages[messageIndex] = {
                      ...newMessages[messageIndex],
                      content: data.message,
                      functions_used: functionsUsed,
                      function_calls: functionCount
                    }
                    return newMessages
                  })
                  break
                case 'function_progress':
                  setMessages(prev => {
                    const newMessages = [...prev]
                    newMessages[messageIndex] = {
                      ...newMessages[messageIndex],
                      content: data.message
                    }
                    return newMessages
                  })
                  break
                case 'function_complete':
                  setMessages(prev => {
                    const newMessages = [...prev]
                    newMessages[messageIndex] = {
                      ...newMessages[messageIndex],
                      content: data.message
                    }
                    return newMessages
                  })
                  break
                case 'content':
                  currentResponse = data.accumulated
                  setMessages(prev => {
                    const newMessages = [...prev]
                    newMessages[messageIndex] = {
                      ...newMessages[messageIndex],
                      content: currentResponse,
                      isStreaming: true
                    }
                    return newMessages
                  })
                  break
                case 'complete':
                  setMessages(prev => {
                    const newMessages = [...prev]
                    newMessages[messageIndex] = {
                      ...newMessages[messageIndex],
                      content: data.full_response,
                      function_calls: data.function_calls,
                      functions_used: data.functions_used,
                      isStreaming: false
                    }
                    return newMessages
                  })
                  break
                case 'error':
                  setMessages(prev => {
                    const newMessages = [...prev]
                    newMessages[messageIndex] = {
                      ...newMessages[messageIndex],
                      content: data.message || 'An error occurred while processing your request.',
                      isStreaming: false
                    }
                    return newMessages
                  })
                  break
              }
            } catch (parseError) {
              console.error('Error parsing streaming data:', parseError)
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat API error:', error)
      // Fallback error message
      const assistantMessage = {
        role: 'assistant',
        content: 'I\'m sorry, I\'m having trouble connecting to the system right now. Please check that the backend server is running and try again.',
        isStreaming: false
      }
      setMessages(prev => [...prev, assistantMessage])
    } finally {
      setIsLoading(false)
      setIsStreaming(false)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0 max-h-full"> {/* Remove overflow from root */}
      {!compact ? (
        // Full version of the chat UI with teal-brown theme
        <>
          {/* Header */}
          <div className="bg-gradient-to-r from-[#254E58] to-[#112D32] text-white p-4 border-b border-[#88BDBC]/30 flex-shrink-0">
            <h2 className="text-xl font-bold text-[#88BDBC]">OASIS Assistant</h2>
            <p className="text-sm text-[#88BDBC]/80">Ask questions about your refinery scheduling</p>
          </div>
          {/* Messages area - primary scrollable container */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden bg-[#112D32]/20 backdrop-blur-sm min-h-0 max-h-full">
            <div className="p-4 space-y-4 min-h-full">
              {messages.map((message, index) => (
                <div 
                  key={index} 
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div 
                    className={`max-w-[75%] rounded-2xl px-4 py-2 ${
                      message.role === 'user' 
                        ? 'bg-gradient-to-r from-[#88BDBC] to-[#254E58] text-white shadow-lg' 
                        : 'bg-white/90 backdrop-blur-sm border border-[#88BDBC]/30 text-[#112D32] shadow-md'
                    }`}
                  >
                    <div className="whitespace-pre-wrap break-words">{message.content}</div>
                    {message.isStreaming && (
                      <div className="inline-flex items-center ml-2">
                        <div className="w-1 h-1 rounded-full bg-[#88BDBC] animate-pulse"></div>
                        <div className="w-1 h-1 rounded-full bg-[#88BDBC] animate-pulse ml-1" style={{ animationDelay: '0.2s' }}></div>
                        <div className="w-1 h-1 rounded-full bg-[#88BDBC] animate-pulse ml-1" style={{ animationDelay: '0.4s' }}></div>
                      </div>
                    )}
                    {message.functions_used && message.functions_used.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-[#88BDBC]/20">
                        <div className="text-xs text-[#254E58]/70 font-medium">
                          Functions used: {message.functions_used.join(', ')}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-white/90 backdrop-blur-sm border border-[#88BDBC]/30 rounded-2xl px-4 py-2 shadow-md">
                    <div className="flex space-x-2">
                      <div className="w-2 h-2 rounded-full bg-[#88BDBC] animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-2 h-2 rounded-full bg-[#88BDBC] animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-2 h-2 rounded-full bg-[#88BDBC] animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
          {/* Input area - compact, multi-line */}
          <div className="bg-[#254E58]/30 backdrop-blur-md border-t border-[#88BDBC]/30 p-3 flex-shrink-0">
            <form onSubmit={handleSendMessage} className="flex items-end gap-2">
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSendMessage(e)
                  }
                }}
                placeholder="Ask about your refinery schedule... (Enter to send, Shift+Enter for new line)"
                className="flex-grow px-3 py-2 bg-white/90 backdrop-blur-sm border border-[#88BDBC]/30 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50 text-[#112D32] placeholder-[#254E58]/60 resize-none"
                style={{ minHeight: '40px', maxHeight: '80px' }}
                rows="2"
                disabled={isLoading || isStreaming}
              />
              <button
                type="submit"
                className="bg-gradient-to-r from-[#88BDBC] to-[#254E58] hover:from-[#254E58] hover:to-[#88BDBC] text-white px-3 py-2 rounded-lg disabled:opacity-50 transition-all duration-200 shadow-lg flex-shrink-0"
                disabled={isLoading || isStreaming || !inputValue.trim()}
                style={{ minHeight: '40px' }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                </svg>
              </button>
            </form>
          </div>
        </>
      ) : (
        // Compact version (single line with input) - teal-brown theme
        <div className="flex items-center p-2 h-full">
          <div className="flex-grow">
            <form onSubmit={handleSendMessage} className="flex">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Ask OASIS Assistant about your schedule..."
                className="flex-grow px-4 py-2 bg-white/90 backdrop-blur-sm border border-[#88BDBC]/30 rounded-l-lg focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50 text-[#112D32] placeholder-[#254E58]/60"
              />
              <button
                type="submit"
                className="bg-gradient-to-r from-[#88BDBC] to-[#254E58] hover:from-[#254E58] hover:to-[#88BDBC] text-white px-4 py-2 rounded-r-lg transition-all duration-200 shadow-lg"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                </svg>
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default Chatbox