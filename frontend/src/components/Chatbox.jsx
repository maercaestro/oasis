import { useState, useRef, useEffect } from 'react'

function Chatbox({ schedule, tanks, vessels, compact = false }) {
  const [messages, setMessages] = useState([
    { role: 'system', content: 'Welcome to OASIS! I can help you interpret and optimize your refinery schedule.' }
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)
  
  // Auto-scroll to bottom of messages when new ones are added
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  const handleSendMessage = async (e) => {
    e.preventDefault()
    if (!inputValue.trim()) return
    
    // Add user message
    const userMessage = { role: 'user', content: inputValue }
    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)
    
    // In a real implementation, here we would call the backend API
    // For now, simulate a response with timeout
    setTimeout(() => {
      const assistantMessage = {
        role: 'assistant',
        content: generatePlaceholderResponse(inputValue, { schedule, tanks, vessels })
      }
      
      setMessages(prev => [...prev, assistantMessage])
      setIsLoading(false)
    }, 1000)
  }
  
  return (
    <div className="flex flex-col h-full">
      {!compact ? (
        // Full version of the chat UI
        <>
          {/* Header */}
          <div className="bg-blue-950 text-white p-4">
            <h2 className="text-xl font-bold">OASIS Assistant</h2>
            <p className="text-sm text-blue-200">Ask questions about your refinery scheduling</p>
          </div>
          
          {/* Messages area */}
          <div className="flex-grow overflow-y-auto p-4 bg-slate-50">
            {messages.map((message, index) => (
              <div 
                key={index} 
                className={`mb-4 flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div 
                  className={`max-w-3/4 rounded-2xl px-4 py-2 ${
                    message.role === 'user' 
                      ? 'bg-blue-600 text-white' 
                      : 'bg-white border border-slate-200'
                  }`}
                >
                  {message.content}
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className="flex justify-start mb-4">
                <div className="bg-white border border-slate-200 rounded-2xl px-4 py-2">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
          
          {/* Input area */}
          <div className="bg-white border-t border-slate-200 p-4">
            <form onSubmit={handleSendMessage} className="flex">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Ask about your refinery schedule..."
                className="flex-grow px-4 py-2 border border-slate-300 rounded-l-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isLoading}
              />
              <button
                type="submit"
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-r-lg disabled:bg-blue-400"
                disabled={isLoading || !inputValue.trim()}
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                </svg>
              </button>
            </form>
          </div>
        </>
      ) : (
        // Compact version (single line with input)
        <div className="flex items-center p-2 h-full">
          <div className="flex-grow">
            <form onSubmit={handleSendMessage} className="flex">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Ask OASIS Assistant about your schedule..."
                className="flex-grow px-4 py-2 border border-slate-300 rounded-l-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="submit"
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-r-lg"
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

// Helper function to generate placeholder responses
// In a real implementation, this would be replaced with calls to your backend LLM API
function generatePlaceholderResponse(question, { schedule, tanks, vessels }) {
  const questionLower = question.toLowerCase()
  
  if (questionLower.includes('schedule') || questionLower.includes('plan')) {
    const daysCount = schedule?.length || 0
    return `I see you have a ${daysCount}-day schedule. This schedule includes daily processing rates and inventory tracking. The visualization on the left shows how your crude processing changes over time.`
  }
  
  if (questionLower.includes('tank') || questionLower.includes('inventory')) {
    const tankCount = Object.keys(tanks || {}).length
    return `There are ${tankCount} tanks in your current configuration. You can edit their content and capacity using the Tank Data editor on the left.`
  }
  
  if (questionLower.includes('vessel') || questionLower.includes('ship')) {
    const vesselCount = vessels?.length || 0
    return `You have ${vesselCount} vessels scheduled to arrive at your refinery. The earliest arrival is ${
      vessels && vessels.length > 0 
        ? `on day ${Math.min(...vessels.map(v => v.arrival_day))}` 
        : 'not yet scheduled'
    }.`
  }
  
  if (questionLower.includes('optimize') || questionLower.includes('improve')) {
    return "I can help you optimize your schedule! To run the optimization, use the 'Optimize Schedule' button on the dashboard. You can choose between maximizing throughput or margin."
  }
  
  return "I'm your OASIS Assistant. I can help you understand your refinery schedule, analyze vessel arrivals, or optimize your operations. What specifically would you like to know about your refinery data?"
}

export default Chatbox