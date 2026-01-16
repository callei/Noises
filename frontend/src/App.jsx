import React, { useState, useEffect } from 'react';
import { TitleBar } from './components/TitleBar';
import { MegaInput } from './components/MegaInput';
import { AudioPlayer } from './components/AudioPlayer';
import { Button } from './components/Button';
import { AlertCircle, Plus, Trash2, Tag } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

function App() {
  const [config, setConfig] = useState({
    prompt: "",
    type: "loop",
    bpm: 120,
    key: "C minor",
    length: 2,
    negativePrompt: "",
    steps: 100,
    guidance: 7.0,
    seed: "",
    temperature: 1.0,
    topK: 250
  });

  const [presets, setPresets] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [backendReady, setBackendReady] = useState(false);

  // Load presets on mount
  useEffect(() => {
    const saved = localStorage.getItem('user_presets');
    if (saved) {
        try {
            setPresets(JSON.parse(saved));
        } catch (e) {
            console.error("Failed to load presets", e);
        }
    }
  }, []);

  // Save presets when changed
  useEffect(() => {
      localStorage.setItem('user_presets', JSON.stringify(presets));
  }, [presets]);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch('http://localhost:8000/health');
        if (res.ok) {
            setBackendReady(true);
            clearInterval(interval);
        }
      } catch (e) { }
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleGenerate = async (e) => {
    if(e) e.preventDefault();
    if (!config.prompt) return;
    
    setGenerating(true);
    setError(null);
    setResult(null);

    try {
      const payload = {
        type: config.type,
        prompt: config.prompt,
        bpm: config.type === 'loop' ? Number(config.bpm) : undefined,
        key: config.key,
        length: Number(config.length),
        variations: 1
      };

      if (config.type === 'one-shot') {
        if (config.negativePrompt) payload.negative_prompt = config.negativePrompt;
        payload.steps = Number(config.steps);
        payload.guidance = Number(config.guidance);
        if (config.seed !== "") payload.seed = Number(config.seed);
      } else {
         payload.guidance = Number(config.guidance);
         payload.temperature = Number(config.temperature);
         payload.top_k = Number(config.topK);
         if (config.seed !== "") payload.seed = Number(config.seed);
      }

      const response = await fetch('http://localhost:8000/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error('Generation failed');
      const data = await response.json();
      
      setResult({
        file: data.files[0].file,
        path: data.files[0].path, 
        type: config.type
      });

    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleAddPreset = () => {
      if (!config.prompt) return;
      const newPreset = {
          id: Date.now(),
          label: config.prompt.slice(0, 20) + (config.prompt.length > 20 ? "..." : ""),
          prompt: config.prompt,
          type: config.type,
          bpm: config.bpm,
          key: config.key
      };
      setPresets(prev => [newPreset, ...prev]);
  };

  const removePreset = (id) => {
      setPresets(prev => prev.filter(p => p.id !== id));
  };

  const applyPreset = (p) => {
      setConfig(prev => ({
          ...prev,
          prompt: p.prompt,
          type: p.type || prev.type,
          bpm: p.bpm || prev.bpm,
          key: p.key || prev.key
      }));
  };

  const handleEnhanceContext = (option) => {
    // Adds specific quality modifiers based on selection
    setConfig(prev => {
        let newPrompt = prev.prompt;
        if (!newPrompt.includes(option.prompt)) {
            newPrompt += option.prompt;
        }

        let newNeg = prev.negativePrompt || "";
        if (option.negative && !newNeg.includes(option.negative)) {
            newNeg = newNeg ? `${newNeg}, ${option.negative}` : option.negative;
        }

        return { ...prev, prompt: newPrompt, negativePrompt: newNeg };
    });
  };

  return (
    <div className="flex flex-col h-screen bg-background text-gray-200 overflow-hidden font-sans relative">
        <TitleBar />
      
        {/* Background gradient */}
        <div className="absolute top-[-20%] left-[20%] w-[600px] h-[600px] bg-purple-900/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[10%] w-[500px] h-[500px] bg-primary/5 rounded-full blur-[100px] pointer-events-none" />

        <main className="flex-1 flex flex-col items-center pt-24 p-6 w-full max-w-4xl mx-auto z-10 transition-all overflow-y-auto custom-scrollbar">
          
          <div className="text-center space-y-2 mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
                <h1 className="text-4xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
                    Noises AI
                </h1>
                {!backendReady && (
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-yellow-500/10 text-yellow-500 text-xs font-medium border border-yellow-500/20">
                        <AlertCircle size={12} /> Connecting to AI Engine...
                    </div>
                )}
            </div>

            <div className="w-full mb-8 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-100">
                <MegaInput 
                    config={config} 
                    setConfig={setConfig} 
                    onGenerate={handleGenerate}
                    generating={generating}
                    backendReady={backendReady}
                    onAddContext={handleEnhanceContext}
                />
            </div>

            {/* Presets and Results Section */}
            <div className="w-full flex flex-col items-center gap-6 animate-in fade-in slide-in-from-bottom-8 duration-700 delay-200">
                
                {/* Result Player */}
                 <AnimatePresence mode='wait'>
                    {error && (
                        <motion.div 
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0 }}
                            className="w-full p-4 rounded-lg bg-red-900/20 border border-red-900/50 text-red-200 flex items-center gap-3"
                        >
                            <AlertCircle size={18} />
                            {error}
                        </motion.div>
                    )}

                    {result && (
                        <motion.div
                            key="result"
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0 }}
                            className="w-full"
                        >
                            <AudioPlayer 
                                filePath={result.path} 
                                fileName={result.file}
                                onRegenerate={handleGenerate}
                            />
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Custom Presets */}
                <div className="w-full flex flex-wrap gap-2 justify-center items-center">
                     <button
                        onClick={handleAddPreset}
                        className="px-3 py-1.5 rounded-full bg-gray-800 hover:bg-gray-700 border border-gray-700 border-dashed text-xs text-gray-400 group transition-colors flex items-center gap-1"
                        title="Save current prompt as preset"
                     >
                        <Plus size={12} className="group-hover:text-white" /> Save Preset
                    </button>
                    
                    {presets.map((p) => (
                        <div key={p.id} className="relative group">
                            <button
                                onClick={() => applyPreset(p)}
                                className="px-3 py-1.5 rounded-full bg-gray-800/50 hover:bg-gray-800 border border-gray-800 hover:border-gray-700 text-xs text-gray-300 transition-colors flex items-center gap-2"
                            >
                                <Tag size={10} className="opacity-50" />
                                <span className="max-w-[150px] truncate">{p.label}</span>
                            </button>
                            <button 
                                onClick={(e) => { e.stopPropagation(); removePreset(p.id); }}
                                className="absolute -top-1 -right-1 bg-red-900 text-red-200 rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <Trash2 size={8} />
                            </button>
                        </div>
                    ))}
                    
                    {presets.length === 0 && (
                        <span className="text-xs text-gray-600 italic">No presets saved yet. Create something awesome and save it!</span>
                    )}
                </div>
            </div>

        </main>
    </div>
  );
}

export default App;

