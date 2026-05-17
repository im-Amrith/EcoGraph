import React, { useState } from 'react';
import { Play, Database, Server, Cpu, Activity, Clock, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function App() {
  const [question, setQuestion] = useState('');
  const [isRunning, setIsRunning] = useState(false);

  // States for each pipeline
  const [llmState, setLlmState] = useState({ data: null, isLoading: false, isError: false });
  const [ragState, setRagState] = useState({ data: null, isLoading: false, isError: false });
  const [graphState, setGraphState] = useState({ data: null, isLoading: false, isError: false });

  const handleRun = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;

    setIsRunning(true);
    
    // Reset states
    setLlmState({ data: null, isLoading: true, isError: false });
    setRagState({ data: null, isLoading: true, isError: false });
    setGraphState({ data: null, isLoading: true, isError: false });

    const payload = { question };

    const fetchPipeline = async (url, setter) => {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error('API Error');
        const data = await response.json();
        setter({ data, isLoading: false, isError: false });
      } catch (error) {
        setter({ data: null, isLoading: false, isError: true });
      }
    };

    await Promise.allSettled([
      fetchPipeline('https://im-amrith-ecograph.hf.space/api/llm', setLlmState),
      fetchPipeline('https://im-amrith-ecograph.hf.space/api/vector-rag', setRagState),
      fetchPipeline('https://im-amrith-ecograph.hf.space/api/chat', setGraphState)
    ]);

    setIsRunning(false);
  };

  const chartData = [
    { name: 'Base LLM', score: llmState.data?.accuracy_score || 0, color: '#52525b' },
    { name: 'Basic RAG', score: ragState.data?.accuracy_score || 0, color: '#71717a' },
    { name: 'GraphRAG', score: graphState.data?.accuracy_score || 0, color: '#f97316' }
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans flex flex-col selection:bg-orange-500/30">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-xl px-6 py-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="bg-orange-500/10 p-2 rounded-lg border border-orange-500/20 shadow-[0_0_15px_rgba(249,115,22,0.1)]">
            <Activity className="text-orange-500 w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-zinc-100">
            Pipeline <span className="text-orange-500">Comparison</span>
          </h1>
        </div>
        <div className="flex items-center gap-2 text-sm text-zinc-500 font-medium">
          GraphRAG vs Basic RAG vs Base LLM
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 flex flex-col gap-8">
        
        {/* Search Section */}
        <div className="flex flex-col items-center mt-8 mb-4">
          <h2 className="text-3xl font-bold mb-6 text-center tracking-tight">
            Evaluate LLM Performance Across <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-orange-600">Architectures</span>
          </h2>
          <form onSubmit={handleRun} className="w-full max-w-3xl relative flex items-center">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Enter your query to test all three pipelines..."
              className="w-full bg-zinc-900 border border-zinc-700/50 rounded-2xl py-4 pl-6 pr-36 focus:outline-none focus:ring-2 focus:ring-orange-500/50 text-zinc-200 placeholder-zinc-500 transition-all shadow-xl"
              disabled={isRunning}
            />
            <button 
              type="submit" 
              disabled={isRunning || !question.trim()}
              className="absolute right-2 bg-orange-500 hover:bg-orange-400 text-zinc-950 rounded-xl px-6 py-2.5 font-bold flex items-center gap-2 transition-all disabled:opacity-50 shadow-[0_0_20px_rgba(249,115,22,0.3)] hover:shadow-[0_0_25px_rgba(249,115,22,0.5)]"
            >
              <Play className="w-4 h-4 fill-zinc-950" />
              Run
            </button>
          </form>
        </div>

        {/* Execution Arena - 3 Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Card 1: Base LLM */}
          <PipelineCard 
            title="Base LLM" 
            desc="Direct prompt injection. No retrieval." 
            icon={Cpu}
            state={llmState}
          />
          
          {/* Card 2: Basic RAG */}
          <PipelineCard 
            title="Basic RAG" 
            desc="Vector embeddings + semantic search." 
            icon={Database}
            state={ragState}
          />

          {/* Card 3: GraphRAG */}
          <PipelineCard 
            title="GraphRAG" 
            desc="Entity extraction + multi-hop graph reasoning." 
            icon={Server}
            state={graphState}
            isHero={true}
            showContext={true}
          />
        </div>

        {/* Comparison Dashboard */}
        {(llmState.data || ragState.data || graphState.data) && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-4"
          >
            <div className="lg:col-span-2 bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md">
              <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-6 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4" /> Accuracy & Relevance Score
              </h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                    <XAxis dataKey="name" stroke="#71717a" tick={{ fill: '#a1a1aa' }} axisLine={false} tickLine={false} />
                    <YAxis stroke="#71717a" tick={{ fill: '#a1a1aa' }} axisLine={false} tickLine={false} />
                    <Tooltip 
                      cursor={{ fill: '#27272a' }}
                      contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '8px' }}
                      itemStyle={{ color: '#f4f4f5' }}
                    />
                    <Bar dataKey="score" radius={[4, 4, 0, 0]} maxBarSize={60}>
                      {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="flex flex-col gap-4">
              <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md flex-1">
                <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                  <Clock className="w-4 h-4" /> Latency Comparison
                </h3>
                <div className="space-y-4">
                  <div className="flex justify-between items-center border-b border-zinc-800/50 pb-2">
                    <span className="text-zinc-400 text-sm">Base LLM</span>
                    <span className="text-zinc-200 font-mono">{llmState.data?.latency_ms ? `${llmState.data.latency_ms}ms` : '-'}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-zinc-800/50 pb-2">
                    <span className="text-zinc-400 text-sm">Basic RAG</span>
                    <span className="text-zinc-200 font-mono">{ragState.data?.latency_ms ? `${ragState.data.latency_ms}ms` : '-'}</span>
                  </div>
                  <div className="flex justify-between items-center pb-2">
                    <span className="text-orange-400 font-medium text-sm">GraphRAG</span>
                    <span className="text-orange-400 font-mono font-bold">{graphState.data?.latency_ms ? `${graphState.data.latency_ms}ms` : '-'}</span>
                  </div>
                </div>
              </div>
              
              <div className="bg-gradient-to-br from-zinc-900 to-zinc-950 border border-orange-500/20 rounded-2xl p-6 flex flex-col justify-center relative overflow-hidden group">
                <div className="absolute top-0 right-0 w-32 h-32 bg-orange-500/5 rounded-full blur-3xl -mr-10 -mt-10 transition-all group-hover:bg-orange-500/10"></div>
                <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-1">Graph Context Retained</h3>
                <p className="text-3xl font-bold text-zinc-100 mt-2 flex items-baseline gap-2">
                  {graphState.data?.context ? '100%' : '0%'}
                  <span className="text-sm font-medium text-orange-500 uppercase">Fidelity</span>
                </p>
                {graphState.data?.entity_id && (
                  <p className="text-xs text-zinc-500 mt-2 truncate">
                    Target: {graphState.data.entity_id} ({graphState.data.entity_type})
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </main>
    </div>
  );
}

function PipelineCard({ title, desc, icon: Icon, state, isHero, showContext }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className={`relative flex flex-col bg-zinc-900/60 rounded-2xl border backdrop-blur-sm overflow-hidden h-[400px] transition-all ${isHero ? 'border-orange-500/30 shadow-[0_0_30px_rgba(249,115,22,0.05)]' : 'border-zinc-800'}`}>
      {/* Card Header */}
      <div className={`p-5 border-b flex items-start gap-4 ${isHero ? 'border-orange-500/20 bg-orange-500/5' : 'border-zinc-800/80 bg-zinc-900/80'}`}>
        <div className={`p-2.5 rounded-lg border flex-shrink-0 ${isHero ? 'bg-orange-500/10 border-orange-500/30 text-orange-400' : 'bg-zinc-800 border-zinc-700 text-zinc-400'}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className={`font-bold text-lg truncate ${isHero ? 'text-orange-50' : 'text-zinc-100'}`}>{title}</h3>
          <p className="text-xs text-zinc-500 mt-1 line-clamp-2">{desc}</p>
        </div>
      </div>

      {/* Card Content (Results area) */}
      <div className="flex-1 p-5 overflow-y-auto relative custom-scrollbar flex flex-col gap-4">
        {state.isLoading && (
          <div className="absolute inset-0 p-5 flex flex-col space-y-4">
            <div className="h-4 bg-zinc-800/50 rounded w-3/4 animate-pulse"></div>
            <div className="h-4 bg-zinc-800/50 rounded w-full animate-pulse"></div>
            <div className="h-4 bg-zinc-800/50 rounded w-5/6 animate-pulse"></div>
            <div className="h-4 bg-zinc-800/50 rounded w-full animate-pulse"></div>
            <div className="h-4 bg-zinc-800/50 rounded w-1/2 animate-pulse"></div>
            
            <div className="mt-auto pt-8 flex items-center gap-2 justify-center text-zinc-600 text-sm">
              <div className="w-1.5 h-1.5 bg-orange-500 rounded-full animate-ping"></div>
              Processing Request...
            </div>
          </div>
        )}

        {state.isError && (
          <div className="h-full flex items-center justify-center text-red-400/80 text-sm text-center">
            Failed to connect to pipeline.
          </div>
        )}

        {!state.isLoading && !state.isError && !state.data && (
          <div className="h-full flex items-center justify-center text-zinc-600 text-sm text-center px-4">
            Awaiting execution...
          </div>
        )}

        {state.data && !state.isLoading && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col gap-4"
          >
            <div className="text-zinc-300 text-sm leading-relaxed whitespace-pre-wrap">
              {state.data.answer}
            </div>

            {showContext && state.data.context && (
              <div className="mt-4 border border-zinc-800 rounded-xl overflow-hidden bg-zinc-950/50">
                <button 
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="w-full flex items-center justify-between p-3 bg-zinc-900/80 hover:bg-zinc-800 transition-colors text-xs font-semibold text-zinc-400 uppercase tracking-wider"
                >
                  Raw Graph Context
                  {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="border-t border-zinc-800"
                    >
                      <div className="p-4 bg-zinc-950 text-xs font-mono text-zinc-500 whitespace-pre-wrap break-words">
                        <div className="mb-2 text-orange-500/80">Entity ID: {state.data.entity_id}</div>
                        <div className="mb-4 text-orange-500/80">Entity Type: {state.data.entity_type}</div>
                        {state.data.context}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}