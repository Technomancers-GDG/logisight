import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";

const QUICK_ACTIONS = [
  "How's my current route looking?",
  "What disruptions are ahead?",
  "Summarize my trip status",
];

const STORAGE_KEY = "driver-chat-messages";
const COOLDOWN_MS = 1500;
const MAX_AGE_MS = 86400000;

function loadMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const msgs = JSON.parse(raw);
    const cutoff = Date.now() - MAX_AGE_MS;
    return Array.isArray(msgs) ? msgs.filter(m => (m.timestamp || 0) > cutoff) : [];
  } catch {
    return [];
  }
}

export function DriverAIChat({ onBack }) {
  const [messages, setMessages] = useState(loadMessages);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [cooldown, setCooldown] = useState(false);
  const bottomRef = useRef(null);
  const abortRef = useRef(null);
  const lastSentRef = useRef(0);
  const genRef = useRef(0);
  const messagesRef = useRef(messages);

  useEffect(() => { messagesRef.current = messages; }, [messages]);

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(messages)); } catch { /* ignore */ }
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const updateLastMessage = useCallback((updater) => {
    setMessages(prev => {
      if (prev.length === 0) return prev;
      const copy = [...prev];
      copy[copy.length - 1] = updater(copy[copy.length - 1]);
      return copy;
    });
  }, []);

  async function sendMessage(text) {
    const query = text.trim();
    if (!query || isLoading || cooldown) return;

    if (abortRef.current) abortRef.current.abort();

    const now = Date.now();
    if (now - lastSentRef.current < COOLDOWN_MS) return;
    lastSentRef.current = now;
    setCooldown(true);
    setTimeout(() => setCooldown(false), COOLDOWN_MS);

    setIsLoading(true);
    setInput("");

    const userMsg = { role: "user", content: query, timestamp: Date.now() };
    const placeholder = { role: "model", content: "", suggestions: null, error: false, timestamp: Date.now() };
    setMessages(prev => [...prev, userMsg, placeholder]);

    const history = [...messagesRef.current, userMsg].map(m => ({
      role: String(m.role ?? "user"),
      content: String(m.content ?? ""),
    }));
    const controller = new AbortController();
    abortRef.current = controller;
    const gen = ++genRef.current;
    let accumulated = "";

    try {
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, history, stream: true }),
        signal: controller.signal,
      });
      if (!response.ok) {
        let detail = `Request failed: ${response.status}`;
        try {
          const errBody = await response.json();
          if (Array.isArray(errBody.detail)) {
            detail = errBody.detail.map(d => d.msg || JSON.stringify(d)).join("; ");
          } else if (errBody.detail) {
            detail = String(errBody.detail);
          }
        } catch {}
        throw new Error(detail);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim() || !line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "chunk") {
              accumulated += event.content;
              updateLastMessage(prev => ({ ...prev, content: accumulated }));
            } else if (event.type === "meta") {
              updateLastMessage(prev => ({ ...prev, suggestions: event.suggestions || null }));
            }
          } catch (e) { /* skip malformed SSE line */ }
        }
      }

      updateLastMessage(prev => ({ ...prev, content: accumulated }));
    } catch (err) {
      if (err.name === "AbortError" || gen !== genRef.current) return;
      updateLastMessage(prev => ({
        ...prev,
        content: accumulated || "Sorry, I couldn't reach the AI assistant. Please try again.",
        error: true,
      }));
    } finally {
      if (gen === genRef.current) {
        setIsLoading(false);
        abortRef.current = null;
      }
    }
  }

  function handleSend() { sendMessage(input); }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function executeQuickAction(text) { sendMessage(text); }

  function retryLast() {
    const lastUser = [...messagesRef.current].reverse().find(m => m.role === "user");
    if (lastUser) sendMessage(lastUser.content);
  }

  function clearChat() {
    setMessages([]);
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
  }

  const showWelcome = messages.length === 0 && !isLoading;

  return (
    <div className="driver-chat">
      <div className="driver-chat-header">
        {onBack && (
          <button type="button" className="driver-chat-back" onClick={onBack}>
            ← Back
          </button>
        )}
        <div className="driver-chat-header-info">
          <span className="driver-chat-header-icon">✨</span>
          <span className="driver-chat-header-title">Ops Assistant</span>
        </div>
        {messages.length > 0 && (
          <button type="button" className="driver-chat-clear" onClick={clearChat} title="Clear conversation history">
            Clear
          </button>
        )}
      </div>

      <div className="driver-chat-body">
        {showWelcome && (
          <div className="driver-chat-welcome">
            <div className="driver-chat-welcome-icon">✨</div>
            <h3>AI Ops Assistant</h3>
            <p>Ask me about your route, disruptions, or overall trip status.</p>
            <div className="driver-chat-quick-actions">
              {QUICK_ACTIONS.map(action => (
                <button key={action} type="button" className="driver-chat-quick-btn" onClick={() => executeQuickAction(action)}>
                  {action}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={msg.timestamp + i} className={`driver-chat-msg driver-chat-msg--${msg.role}`}>
            <div className="driver-chat-bubble-wrap">
              <div className="driver-chat-bubble">
                {msg.content ? (
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                ) : isLoading && i === messages.length - 1 && msg.role === "model" ? (
                  <span className="driver-chat-thinking">
                    Thinking
                    <span className="driver-chat-dots">
                      <span>.</span><span>.</span><span>.</span>
                    </span>
                  </span>
                ) : null}
              </div>

              {!isLoading && msg.role === "model" && msg.suggestions?.length > 0 && (
                <div className="driver-chat-suggestions">
                  {msg.suggestions.map((s, j) => (
                    <button key={j} type="button" className="driver-chat-chip" onClick={() => executeQuickAction(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              )}

              {msg.error && !isLoading && (
                <button type="button" className="driver-chat-retry" onClick={retryLast}>
                  ↻ Retry
                </button>
              )}
            </div>
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      <div className="driver-chat-input-bar">
        <input
          className="driver-chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question..."
          disabled={isLoading}
        />
        <button
          type="button"
          className={`driver-chat-send${cooldown ? " driver-chat-send--cooldown" : ""}`}
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
