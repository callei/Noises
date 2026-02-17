import React, { useState } from 'react';
import { Settings2, Sliders, Wand2, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './Button';
import { Input, Select } from './Input';
import { cn } from '../lib/utils';

export function MegaInput({ config, setConfig, onGenerate, generating, backendReady, onAddContext }) {
  const [expanded, setExpanded] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showContext, setShowContext] = useState(false);

  const toggleExpand = () => setExpanded(!expanded);
  const toggleAdvanced = () => setShowAdvanced(!showAdvanced);

  const KEYS = [
    "C major", "C minor", "C# major", "C# minor",
    "D major", "D minor", "Eb major", "Eb minor",
    "E major", "E minor", "F major", "F minor",
    "F# major", "F# minor", "G major", "G minor",
    "Ab major", "Ab minor", "A major", "A minor",
    "Bb major", "Bb minor", "B major", "B minor"
  ];

  const CONTEXT_OPTIONS = [
    { label: "Clean / High Fidelity", prompt: ", clean high quality audio, professionally produced", negative: "noise, distortion, artifacts, low quality" },
    { label: "Lo-Fi / Vintage", prompt: ", vintage vinyl texture, lo-fi aesthetic, warm saturation", negative: "clean, digital, sharp" },
    { label: "Dark / Cinematic", prompt: ", dark atmosphere, cinematic, roomy reverb", negative: "bright, happy, upbeat" },
    { label: "Distorted / Aggressive", prompt: ", heavy distortion, aggressive compression, saturation", negative: "clean, soft, gentle" },
    { label: "Instrument Only", prompt: ", pure instrumental, no vocals", negative: "vocals, singing, voice" },
    { label: "Ambient / Spacious", prompt: ", ambient, spacious, ethereal, long reverb", negative: "dry, tight, percussive" },
    { label: "Energetic / Upbeat", prompt: ", energetic, fast tempo, dynamic, uplifting", negative: "slow, calm, mellow" }
  ];

  const handleContextClick = (opt) => {
      onAddContext(opt);
      setShowContext(false);
  };

  return (
    <div className="relative z-20 w-full animate-in fade-in zoom-in-95 duration-500">
      <div className="relative group">
        {/* Glow effect - Fixed corners and uniformity */}
        <div className="absolute -inset-0.5 bg-purple-500/40 rounded-2xl blur-xl opacity-75 group-focus-within:opacity-100 transition duration-500 group-hover:opacity-90"></div>
        
        <div className={cn(
            "relative bg-panel rounded-xl shadow-2xl transition-all duration-300 overflow-visible",
            (expanded || showAdvanced) ? "scale-[1.01]" : ""
        )}>
            
            {/* Top Bar with Type Selector */}
            <div className="flex items-center justify-between px-4 pt-3 pb-1">
                 <div className="flex gap-1 bg-gray-900/50 p-1 rounded-lg">
                    <button 
                        onClick={() => setConfig({...config, type: 'loop', length: 4, steps: 200, guidance: 7.0, prompt: ""})}
                        className={cn(
                            "text-xs px-3 py-1.5 rounded-md font-medium transition-all flex items-center gap-2",
                            config.type === 'loop' ? "bg-primary text-white shadow-lg" : "text-gray-400 hover:text-gray-200"
                        )}
                    >
                        <span>Loop</span>
                        <span className="text-[10px] opacity-60 font-mono hidden sm:inline">(Stable Audio)</span>
                    </button>
                    <button 
                         onClick={() => setConfig({...config, type: 'one-shot', length: 30, steps: 60, guidance: 15.0, prompt: ""})}
                         className={cn(
                            "text-xs px-3 py-1.5 rounded-md font-medium transition-all flex items-center gap-2",
                            config.type === 'one-shot' ? "bg-primary text-white shadow-lg" : "text-gray-400 hover:text-gray-200"
                        )}
                    >
                        <span>Full Song</span>
                        <span className="text-[10px] opacity-60 font-mono hidden sm:inline">(ACE-Step)</span>
                    </button>
                 </div>

                 <div className="flex gap-2 relative">
                     <div className="relative">
                        <button 
                            onClick={() => setShowContext(!showContext)}
                            title="Enhance Prompt"
                            className={cn("text-gray-400 hover:text-primary transition-colors p-2 rounded-full hover:bg-gray-800", showContext && "text-primary bg-gray-800")}
                        >
                            <Wand2 size={16} />
                        </button>
                        
                        {/* Context Menu Popup */}
                        <AnimatePresence>
                             {showContext && (
                                 <motion.div 
                                    initial={{ opacity: 0, scale: 0.95, y: 10 }}
                                    animate={{ opacity: 1, scale: 1, y: 0 }}
                                    exit={{ opacity: 0, scale: 0.95, y: 10 }}
                                    className="absolute right-0 top-full mt-2 w-56 bg-panel border border-gray-700/50 rounded-lg shadow-xl z-50 overflow-hidden"
                                 >
                                     <div className="p-2 space-y-1">
                                         <div className="flex justify-between items-center px-2 py-1 text-xs text-gray-400 uppercase font-semibold">
                                             <span>Enhance</span>
                                             <button onClick={() => setShowContext(false)}><X size={12} /></button>
                                         </div>
                                         {CONTEXT_OPTIONS.map((opt) => (
                                             <button
                                                key={opt.label}
                                                onClick={() => handleContextClick(opt)}
                                                className="w-full text-left px-3 py-2 text-sm text-gray-200 hover:bg-gray-700 rounded-md transition-colors"
                                             >
                                                 {opt.label}
                                             </button>
                                         ))}
                                     </div>
                                 </motion.div>
                             )}
                        </AnimatePresence>
                     </div>

                     <button 
                        onClick={toggleExpand}
                        className={cn("text-gray-400 hover:text-white transition-colors p-2 rounded-full hover:bg-gray-800", expanded && "text-white")}
                     >
                         <Settings2 size={16} />
                     </button>
                      <button 
                        onClick={toggleAdvanced}
                        className={cn("text-gray-400 hover:text-white transition-colors p-2 rounded-full hover:bg-gray-800", showAdvanced && "text-white")}
                     >
                         <Sliders size={16} />
                     </button>
                 </div>
            </div>

            {/* Main Text Area - No Border */}
            <textarea 
                className="w-full bg-transparent border-none text-lg p-5 focus:ring-0 focus:outline-none resize-none placeholder:text-gray-600 min-h-[120px]"
                placeholder={config.type === 'loop' ? "Describe your loop (e.g., shaker, kick, bass, synth)..." : "Describe your full song (genres, mood, vocals)..."}
                value={config.prompt}
                onChange={(e) => setConfig({ ...config, prompt: e.target.value })}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        onGenerate(e);
                    }
                }}
            />

            {/* Expansion: Main Settings (Same Background Color) */}
            <AnimatePresence>
                {expanded && (
                    <motion.div 
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden bg-panel"
                    >
                        <div className="p-4 pt-0 grid grid-cols-3 gap-4">
                            <Select 
                                label="Key"
                                value={config.key}
                                onChange={(e) => setConfig({ ...config, key: e.target.value })}
                                options={KEYS.map(k => ({ label: k, value: k }))}
                                className="bg-[#252525] border-transparent focus:bg-[#333]"
                            />
                            
                            {config.type === 'loop' ? (
                                <Input 
                                    label="BPM"
                                    type="number"
                                    value={config.bpm}
                                    onChange={(e) => setConfig({ ...config, bpm: e.target.value })}
                                    className="bg-[#252525] border-transparent focus:bg-[#333]"
                                />
                            ) : (
                                <Input 
                                    label="Guidance"
                                    type="number"
                                    value={config.guidance}
                                    step="0.5"
                                    onChange={(e) => setConfig({ ...config, guidance: e.target.value })}
                                    className="bg-[#252525] border-transparent focus:bg-[#333]"
                                />
                            )}
                            
                            <Input 
                                label={config.type === 'loop' ? "Duration (s)" : "Duration (s)"}
                                type="number"
                                value={config.length}
                                onChange={(e) => setConfig({ ...config, length: e.target.value })}
                                min={config.type === 'loop' ? 1 : 10}
                                max={config.type === 'loop' ? 10 : 240}
                                className="bg-[#252525] border-transparent focus:bg-[#333]"
                            />
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

             {/* Expansion: Advanced Settings (Same Background Color) */}
             <AnimatePresence>
                {showAdvanced && (
                    <motion.div 
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden bg-panel"
                    >
                         <div className="p-4 pt-0 grid grid-cols-2 gap-4">
                            <Input 
                                label="Steps"
                                type="number"
                                value={config.steps}
                                onChange={(e) => setConfig({ ...config, steps: e.target.value })}
                                className="bg-[#252525] border-transparent focus:bg-[#333]"
                            />

                            <Input 
                                label="Seed"
                                placeholder="Random"
                                value={config.seed}
                                onChange={(e) => setConfig({ ...config, seed: e.target.value })}
                                className="bg-[#252525] border-transparent focus:bg-[#333]"
                            />
                            
                            {config.type === 'loop' && (
                                <div className="col-span-2">
                                    <Input 
                                        label="Negative Prompt (optional - what to avoid)"
                                        placeholder="e.g., vocals, drums, distortion"
                                        value={config.negativePrompt}
                                        onChange={(e) => setConfig({ ...config, negativePrompt: e.target.value })}
                                        className="bg-[#252525] border-transparent focus:bg-[#333]"
                                    />
                                </div>
                            )}

                            {config.type === 'one-shot' && (
                                <div className="col-span-2">
                                    <label className="block text-xs text-gray-400 mb-1.5 font-medium">Lyrics (optional)</label>
                                    <textarea
                                        placeholder="Add lyrics here"
                                        value={config.lyrics}
                                        onChange={(e) => setConfig({ ...config, lyrics: e.target.value })}
                                        rows={3}
                                        className="w-full bg-[#252525] border-transparent focus:bg-[#333] rounded-lg text-sm p-2.5 resize-none placeholder:text-gray-600 focus:outline-none focus:ring-1 focus:ring-primary/50"
                                    />
                                </div>
                            )}
                            
                            {config.type === 'one-shot' && (
                                <>
                                    <div>
                                        <label className="block text-xs text-gray-400 mb-1.5 font-medium">Scheduler Type</label>
                                        <select
                                            value={config.schedulerType}
                                            onChange={(e) => setConfig({ ...config, schedulerType: e.target.value })}
                                            className="w-full bg-[#252525] border-transparent focus:bg-[#333] rounded-lg text-sm p-2.5 focus:outline-none focus:ring-1 focus:ring-primary/50"
                                        >
                                            <option value="euler">Euler (Recommended)</option>
                                            <option value="dpm">DPM</option>
                                            <option value="ddim">DDIM</option>
                                        </select>
                                    </div>

                                    <div>
                                        <label className="block text-xs text-gray-400 mb-1.5 font-medium">CFG Type</label>
                                        <select
                                            value={config.cfgType}
                                            onChange={(e) => setConfig({ ...config, cfgType: e.target.value })}
                                            className="w-full bg-[#252525] border-transparent focus:bg-[#333] rounded-lg text-sm p-2.5 focus:outline-none focus:ring-1 focus:ring-primary/50"
                                        >
                                            <option value="apg">APG - Adaptive (Recommended)</option>
                                            <option value="standard">Standard</option>
                                        </select>
                                    </div>
                                </>
                            )}
                         </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Generate Button Area - Same Background Color - Fixed Radius */}
            <div className="p-2 flex justify-end bg-panel rounded-b-xl">
                <Button 
                    onClick={onGenerate} 
                    disabled={generating || !backendReady}
                    isLoading={generating}
                    size="lg"
                    className="rounded-lg px-8 w-full md:w-auto font-bold tracking-wide"
                >
                    {!generating && <Wand2 size={18} className="mr-2" />}
                    Generate
                </Button>
            </div>
        </div>
      </div>
    </div>
  );
}
