import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, Download, Volume2, RefreshCw, VolumeX, FolderOpen, GripVertical } from 'lucide-react';
import { Button } from './Button';
import { readFile } from '@tauri-apps/plugin-fs';
import { open } from '@tauri-apps/plugin-shell';

export function AudioPlayer({ filePath, fileName, onRegenerate }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const [isMuted, setIsMuted] = useState(false);
  const audioRef = useRef(null);
  const [src, setSrc] = useState(null);

  useEffect(() => {
    async function loadAudio() {
        if (!filePath) return;
        try {
            // Read file as binary
            const content = await readFile(filePath);
            const blob = new Blob([content], { type: 'audio/wav' }); // Assuming WAV from backend
            const url = URL.createObjectURL(blob);
            setSrc(url);
            
            // Cleanup previous URL
            return () => URL.revokeObjectURL(url);
        } catch (err) {
            console.error("Failed to load audio file:", err);
        }
    }
    loadAudio();
  }, [filePath]);

  useEffect(() => {
      if (audioRef.current) {
          audioRef.current.volume = isMuted ? 0 : volume;
      }
  }, [volume, isMuted]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch(e => console.error("Playback failed", e));
    }
    setIsPlaying(!isPlaying);
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      const p = (audioRef.current.currentTime / audioRef.current.duration) * 100;
      setProgress(p);
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setProgress(0);
  };
  
  const handleSeek = (e) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const percentage = x / rect.width;
      if (audioRef.current) {
          audioRef.current.currentTime = percentage * audioRef.current.duration;
      }
  };

  const handleOpenFolder = async () => {
      try {
          // Robust directory extraction
          const cleanPath = filePath.replace(/\\/g, '/');
          const lastSlash = cleanPath.lastIndexOf('/');
          const parentDir = lastSlash !== -1 ? cleanPath.substring(0, lastSlash) : cleanPath;
          
          await open(parentDir); 
      } catch (e) {
          // Fallback: try opening the file itself (OS decides app)
          console.error("Failed to open folder, trying file...", e);
          try {
              await open(filePath);
          } catch (e2) {
             console.error("Failed to open file", e2);
          }
      }
  };

  const handleDragStart = (e) => {
      e.preventDefault();
      // Improved Drag for Windows/DAWs
      // text/uri-list is widely supported
      const fileUrl = `file:///${filePath.replace(/\\/g, '/')}`;
      
      e.dataTransfer.effectAllowed = 'copy';
      e.dataTransfer.setData('text/plain', filePath);
      e.dataTransfer.setData('text/uri-list', fileUrl);
      // 'DownloadURL' is Chrome-specific but good backup
      e.dataTransfer.setData('DownloadURL', `audio/wav:${fileName}:${fileUrl}`);
  };

  return (
    <div className="w-full bg-panel rounded-xl border border-gray-700/50 p-4 transition-all hover:shadow-[0_0_25px_rgba(168,85,247,0.15)] hover:border-purple-500/30 shadow-lg group-hover:scale-[1.01] duration-300">
        <audio
            ref={audioRef}
            src={src}
            onTimeUpdate={handleTimeUpdate}
            onEnded={handleEnded}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            loop
        />
        
        {/* Header: Info + Tools */}
        <div className="flex items-center justify-between mb-4">
            <div 
                className="flex items-center gap-3 overflow-hidden cursor-grab active:cursor-grabbing group"
                draggable="true"
                onDragStart={handleDragStart}
                title="Drag to desktop/DAW"
            >
                <div className="h-10 w-10 flex items-center justify-center rounded-full bg-primary/20 text-primary group-hover:bg-primary/30 transition-colors">
                    <GripVertical size={20} className="opacity-50 group-hover:opacity-100" />
                </div>
                <div className="flex flex-col min-w-0">
                    <span className="text-sm font-semibold truncate text-white max-w-[200px]">{fileName}</span>
                    <span className="text-xs text-gray-400">Drag to DAW</span>
                </div>
            </div>
            
            <div className="flex gap-1">
                 <Button size="sm" variant="ghost" onClick={handleOpenFolder} title="Show in Folder">
                    <FolderOpen size={16} />
                 </Button>
                 {onRegenerate && (
                     <Button size="sm" variant="ghost" onClick={onRegenerate} title="Regenerate">
                        <RefreshCw size={16} />
                     </Button>
                 )}
            </div>
        </div>

        {/* Controls: Play + Seek + Volume (Aligned Single Row) */}
        <div className="flex items-center gap-3">
            <Button size="icon" className="rounded-full h-10 w-10 shrink-0 bg-primary hover:bg-primary-hover shadow-lg shadow-primary/30 border-none" onClick={togglePlay}>
                {isPlaying ? <Pause size={20} className="fill-white" /> : <Play size={20} className="fill-white ml-1" />}
            </Button>
            
            {/* Seek Bar */}
            <div className="flex-1 h-8 flex items-center group cursor-pointer" onClick={handleSeek}>
                <div className="h-1.5 w-full bg-gray-700/50 rounded-full overflow-hidden relative">
                    <div 
                        className="h-full bg-primary transition-all duration-100 linear group-hover:bg-primary-hover"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>
            
            {/* Volume */}
            <div className="flex items-center gap-2 group/vol bg-gray-900/40 p-1.5 rounded-lg border border-transparent hover:border-gray-700/50 transition-all">
                <button onClick={() => setIsMuted(!isMuted)} className="text-gray-400 hover:text-white">
                    {isMuted || volume === 0 ? <VolumeX size={16} /> : <Volume2 size={16} />}
                </button>
                <input 
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={isMuted ? 0 : volume}
                    onChange={(e) => {
                        setVolume(parseFloat(e.target.value));
                        setIsMuted(false);
                    }}
                    className="w-16 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:bg-gray-400 [&::-webkit-slider-thumb]:rounded-full hover:[&::-webkit-slider-thumb]:bg-white"
                />
            </div>
        </div>
    </div>
  );
}
