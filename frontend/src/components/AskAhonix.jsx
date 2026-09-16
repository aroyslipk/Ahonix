import React, { useEffect, useRef, useState } from "react";
import { X, ArrowUp, Loader2, AlertTriangle, ShieldCheck, Database, Compass } from "lucide-react";
import { useUI } from "@/context/UIContext";
import { API } from "@/lib/api";
import { renderMarkdown } from "@/lib/markdown";
import { Logo } from "@/components/Logo";

const MAX_QUESTION_LENGTH = 5000;

const QUICK_PROMPTS = [
  "What is the single biggest money leak across my store this month?",
  "Break down why my true profit deviates from gross revenue.",
  "Which products require immediate restock based on current velocity?",
  "Which marketing campaign is generating positive net contribution?",
  "Where are return rates destroying my unit economics?",
  "Which international market presents the lowest-risk expansion?",
];

export function AskAhonix() {
  const { askOpen, setAskOpen, askSeed, setAskSeed } = useUI();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const sessionRef = useRef(null);
  const scrollRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    if (askOpen && askSeed) {
      const q = typeof askSeed === "string" ? askSeed : askSeed.title;
      setInput(q);
      setAskSeed(null);
    }
  }, [askOpen, askSeed, setAskSeed]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (question) => {
    const q = (question ?? input).trim();
    if (!q || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "" }]);
    setStreaming(true);

    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, session_id: sessionRef.current }),
      });
      if (res.status === 429) {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: "⚠️ You're sending questions too quickly. Please wait a moment and try again.",
          };
          return copy;
        });
        return;
      }
      if (res.status === 422) {
        const err = await res.json().catch(() => null);
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: `⚠️ ${err?.detail || "Invalid question. Please check your input."}`,
          };
          return copy;
        });
        return;
      }
      if (res.status === 401) {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: "⚠️ Your session has expired. Please refresh the page and sign in again.",
          };
          return copy;
        });
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        const errorMsg = err?.detail || (res.status === 503 ? "Ask AHONIX is currently unconfigured or unavailable." : "I couldn't reach the analyst right now. Please try again.");
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: `⚠️ ${errorMsg}`,
          };
          return copy;
        });
        return;
      }
      if (!res.body) throw new Error("stream failed");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const payload = JSON.parse(line.slice(5).trim());
          if (payload.delta) {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = {
                role: "assistant",
                content: copy[copy.length - 1].content + payload.delta,
              };
              return copy;
            });
          } else if (payload.session_id) {
            sessionRef.current = payload.session_id;
          } else if (payload.error) {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { role: "assistant", content: "⚠️ " + payload.error };
              return copy;
            });
          }
        }
      }
    } catch (e) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = {
          role: "assistant",
          content: "⚠️ I couldn't reach the analyst right now. Please try again.",
        };
        return copy;
      });
    } finally {
      setStreaming(false);
    }
  };

  if (!askOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="ask-ahonix-drawer">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setAskOpen(false)} />
      <div className="relative flex h-full w-full max-w-2xl flex-col border-l border-[#16221B] bg-[#070C0A] shadow-2xl animate-fade-up">
        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b border-[#16221B] px-4 py-3.5 sm:px-6 sm:py-4">
          <div className="flex items-center gap-2.5 sm:gap-3">
            <Logo size={22} showText={false} />
            <div>
              <div className="flex items-center gap-2">
                <p className="font-display text-sm sm:text-base font-bold text-[#F8FAFC]">Ask AHONIX</p>
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[9px] sm:text-[10px] font-semibold text-emerald-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  Verified Analyst
                </span>
              </div>
              <p className="text-[11px] sm:text-xs text-[#64748B]">Autonomous commerce intelligence grounded in your merchant data</p>
            </div>
          </div>
          <button
            onClick={() => setAskOpen(false)}
            className="rounded-lg p-2 text-[#94A3B8] transition-colors hover:bg-[#16221B] hover:text-[#F8FAFC]"
            data-testid="ask-close-btn"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Area */}
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">
          {messages.length === 0 && (
            <div>
              {/* Institutional Analyst Briefing */}
              <div className="mb-6 rounded-xl border border-[#16221B] bg-[#0B110E] p-5">
                <div className="flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
                    <Database size={17} />
                  </span>
                  <div>
                    <h3 className="text-sm font-bold text-[#F8FAFC]">Diagnostic Reasoning Active</h3>
                    <p className="mt-1 text-xs leading-relaxed text-[#94A3B8]">
                      AHONIX continuously correlates your revenue streams, unit cost structures, marketing returns, and operational frictions. Query any financial or operational metric for rigorous, evidence-grounded recommendations.
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-[#64748B]">
                      <span className="flex items-center gap-1 rounded border border-[#16221B] bg-[#070C0A] px-2 py-0.5">
                        <ShieldCheck size={11} className="text-emerald-400" /> Shopify Orders Grounded
                      </span>
                      <span className="flex items-center gap-1 rounded border border-[#16221B] bg-[#070C0A] px-2 py-0.5">
                        <ShieldCheck size={11} className="text-emerald-400" /> Unit COGS Verified
                      </span>
                      <span className="flex items-center gap-1 rounded border border-[#16221B] bg-[#070C0A] px-2 py-0.5">
                        <ShieldCheck size={11} className="text-emerald-400" /> Ad Spend Deducted
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">Strategic Inquiries</p>
                <span className="text-[11px] text-[#475569]">Click to inspect</span>
              </div>
              <div className="space-y-2">
                {QUICK_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => send(p)}
                    className="flex w-full items-center justify-between rounded-xl border border-[#16221B] bg-[#0B110E] px-4 py-3 text-left text-xs font-medium text-[#CBD5E1] transition-all duration-150 hover:border-emerald-500/30 hover:bg-[#0E1713] hover:text-[#F8FAFC]"
                    data-testid="ask-quick-prompt"
                  >
                    <span>{p}</span>
                    <Compass size={13} className="ml-2 shrink-0 text-[#64748B]" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-sm border border-emerald-500/20 bg-[#0B1A13] px-4 py-3 text-sm leading-relaxed text-[#E2FBEF]">
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={i} className="rounded-xl border border-[#16221B] bg-[#0B110E] p-5 shadow-sm" data-testid="ask-answer">
                <div className="mb-3 flex items-center justify-between border-b border-[#16221B] pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-[#CBD5E1]">
                      AHONIX Analyst Synthesis
                    </span>
                  </div>
                  <span className="text-[10px] text-[#64748B]">Zero Fabrication Policy</span>
                </div>
                {m.content ? (
                  <div className="markdown text-sm leading-relaxed text-[#CBD5E1]" dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }} />
                ) : (
                  <div className="flex items-center gap-2.5 py-3 text-sm text-[#94A3B8]">
                    <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                    <span>Correlating merchant telemetry and synthesizing evidence…</span>
                  </div>
                )}
              </div>
            )
          )}
          <div ref={endRef} />
        </div>

        {/* Input Bar */}
        <div className="border-t border-[#16221B] bg-[#070C0A] p-4 pb-6 sm:p-5">
          <div className="flex items-end gap-2.5 rounded-xl border border-[#16221B] bg-[#0B110E] p-2.5 transition-colors focus-within:border-emerald-500/40">
            <textarea
              value={input}
              onChange={(e) => {
                if (e.target.value.length <= MAX_QUESTION_LENGTH) {
                  setInput(e.target.value);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={1}
              placeholder="Ask about profit reconciliation, margin leaks, inventory turn, ad ROAS..."
              className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-[#F8FAFC] outline-none placeholder:text-[#475569]"
              data-testid="ask-ahonix-input"
              maxLength={MAX_QUESTION_LENGTH}
            />
            <button
              onClick={() => send()}
              disabled={streaming || !input.trim() || input.length > MAX_QUESTION_LENGTH}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500 text-emerald-950 transition-transform active:scale-95 disabled:opacity-30"
              data-testid="ask-ahonix-submit"
            >
              {streaming ? <Loader2 size={16} className="animate-spin" /> : <ArrowUp size={16} strokeWidth={2.5} />}
            </button>
          </div>
          {input.length > MAX_QUESTION_LENGTH * 0.9 && (
            <div className="mt-1.5 flex items-center gap-1 text-[10px] text-amber-400">
              <AlertTriangle size={10} />
              {input.length}/{MAX_QUESTION_LENGTH} characters
            </div>
          )}
          <p className="mt-2.5 text-center text-[10px] text-[#475569]">
            AHONIX uses verified formulas and real store telemetry. Estimates are clearly marked.
          </p>
        </div>
      </div>
    </div>
  );
}

