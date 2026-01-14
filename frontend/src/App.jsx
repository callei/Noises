import React, { useState } from 'react';

const KEYS = [
  "C major", "C minor", "C# major", "C# minor",
  "D major", "D minor", "Eb major", "Eb minor",
  "E major", "E minor", "F major", "F minor",
  "F# major", "F# minor", "G major", "G minor",
  "Ab major", "Ab minor", "A major", "A minor",
  "Bb major", "Bb minor", "B major", "B minor"
];

function App() {
  const [prompt, setPrompt] = useState("");
  const [type, setType] = useState("loop");
  const [bpm, setBpm] = useState(120);
  const [key, setKey] = useState("C minor");
  const [length, setLength] = useState(2);
  
  // advanced controls
  const [negativePrompt, setNegativePrompt] = useState("");
  const [steps, setSteps] = useState(100);
  const [guidance, setGuidance] = useState(7.0);
  const [seed, setSeed] = useState("");
  const [temperature, setTemperature] = useState(1.0);
  const [topK, setTopK] = useState(250);

  const [generating, setGenerating] = useState(false);
  const [status, setStatus] = useState(null);
  const [backendReady, setBackendReady] = useState(false);

  React.useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await fetch('http://localhost:8000/health');
        if (res.ok) {
          setBackendReady(true);
        }
      } catch (e) {
        // quiet fail
      }
    };
    
    const interval = setInterval(() => {
      if (!backendReady) {
        checkBackend();
      } else {
        clearInterval(interval);
      }
    }, 1000);
    
    return () => clearInterval(interval);
  }, [backendReady]);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setGenerating(true);
    setStatus({ type: 'generating', message: 'Generating...' });

    try {
      const payload = {
        type,
        prompt,
        bpm: type === 'loop' ? Number(bpm) : undefined,
        key,
        length: Number(length),
        variations: 1
      };

      if (type === 'one-shot') {
        if (negativePrompt) payload.negative_prompt = negativePrompt;
        payload.steps = Number(steps);
        payload.guidance = Number(guidance);
        if (seed !== "") payload.seed = Number(seed);
      }
      
      if (type === 'loop') {
         payload.guidance = Number(guidance);
         payload.temperature = Number(temperature);
         payload.top_k = Number(topK);
         if (seed !== "") payload.seed = Number(seed);
      }

      const response = await fetch('http://localhost:8000/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error('Generation failed');
      }

      const data = await response.json();
      setStatus({ 
        type: 'success', 
        message: `Saved: ${data.files[0].file}`, 
        path: data.path 
      });
    } catch (error) {
      console.error(error);
      setStatus({ type: 'error', message: `Error: ${error.message}` });
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="container">
      <h1>AI Music Generator</h1>
      
      <form onSubmit={handleGenerate}>
        <div className="form-group">
          <label>Prompt</label>
          <input 
            type="text" 
            value={prompt} 
            onChange={(e) => setPrompt(e.target.value)} 
            placeholder="e.g. 1 bar shaker loop, minimal techno"
            required 
          />
        </div>

        <div className="row">
          <div className="form-group">
            <label>Type</label>
            <select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="loop">Loop (MusicGen)</option>
              <option value="one-shot">One-shot (Stable Audio)</option>
            </select>
          </div>

          <div className="form-group">
            <label>Key</label>
            <select value={key} onChange={(e) => setKey(e.target.value)}>
              <option value="">None</option>
              {KEYS.map(k => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>
        </div>

        <div className="row">
          {type === 'loop' && (
            <div className="form-group">
              <label>BPM</label>
              <input 
                type="number" 
                value={bpm} 
                onChange={(e) => setBpm(e.target.value)}
                min="60" max="200"
              />
            </div>
          )}
          
          <div className="form-group">
            <label>{type === 'loop' ? 'Length (bars)' : 'Length (seconds)'}</label>
            <input 
              type="number" 
              value={length} 
              onChange={(e) => setLength(e.target.value)}
              step="0.1"
              min="0.1"
            />
          </div>
        </div>

        {type === 'one-shot' && (
          <div className="advanced-options" style={{ marginTop: '20px', padding: '15px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
            <h3 style={{ marginTop: 0, marginBottom: '15px', fontSize: '1.1em' }}>Advanced Control (One-Shot)</h3>
            
            {/* Stable Audio Open doesn't support negative prompt in basic pipeline */}
            {/* <div className="form-group">
              <label>Negative Prompt</label>
              <input 
                type="text" 
                value={negativePrompt} 
                onChange={(e) => setNegativePrompt(e.target.value)} 
                placeholder="What to avoid (e.g. noise, reverb)" 
              />
            </div> */}

            <div className="row">
              <div className="form-group">
                <label title="Higher = slower but better quality (Rec 100-200)">Steps ({steps})</label>
                <input 
                  type="range" 
                  value={steps} 
                  onChange={(e) => setSteps(e.target.value)}
                  min="50" max="250" step="10"
                />
              </div>

              <div className="form-group">
                <label title="Lower = more creative, Higher = strictly follows prompt">Guidance ({guidance})</label>
                <input 
                  type="number" 
                  value={guidance} 
                  onChange={(e) => setGuidance(e.target.value)}
                  min="1.0" max="20.0" step="0.5"
                />
              </div>

              <div className="form-group">
                <label>Seed (Optional)</label>
                <input 
                  type="number" 
                  value={seed} 
                  onChange={(e) => setSeed(e.target.value)}
                  placeholder="Random"
                />
              </div>
            </div>
          </div>
        )}

        {type === 'loop' && (
          <div className="advanced-options" style={{ marginTop: '20px', padding: '15px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
            <h3 style={{ marginTop: 0, marginBottom: '15px', fontSize: '1.1em' }}>Advanced Control (MusicGen)</h3>

            <div className="row">
               <div className="form-group">
                <label title="Lower = more creative, Higher = strictly follows prompt">Guidance ({guidance})</label>
                <input 
                  type="number" 
                  value={guidance} 
                  onChange={(e) => setGuidance(e.target.value)}
                  min="1.0" max="15.0" step="0.5"
                />
              </div>

              <div className="form-group">
                <label title="Lower = deterministic, Higher = chaotic">Temp ({temperature})</label>
                <input 
                  type="range" 
                  value={temperature} 
                  onChange={(e) => setTemperature(e.target.value)}
                  min="0.1" max="2.0" step="0.1"
                />
              </div>

               <div className="form-group">
                <label title="Top K Sampling">Top K ({topK})</label>
                <input 
                  type="number" 
                  value={topK} 
                  onChange={(e) => setTopK(e.target.value)}
                  min="1" max="500"
                />
              </div>

              <div className="form-group">
                <label>Seed (Optional)</label>
                <input 
                  type="number" 
                  value={seed} 
                  onChange={(e) => setSeed(e.target.value)}
                  placeholder="Random"
                />
              </div>
            </div>
          </div>
        )}

        <button type="submit" disabled={generating || !backendReady} style={{ marginTop: '20px' }}>
          {!backendReady ? 'Loading Models...' : generating ? 'Generating...' : 'Generate Audio'}
        </button>
      </form>

      {status && (
        <div className={`status ${status.type}`}>
          <strong>{status.type === 'error' ? 'Error' : status.type === 'success' ? 'Success' : 'Processing'}</strong>
          <div>{status.message}</div>
          {status.path && <div style={{fontSize: '0.8em', opacity: 0.8}}>{status.path}</div>}
        </div>
      )}
    </div>
  );
}

export default App;

