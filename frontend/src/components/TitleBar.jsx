import React, { useEffect, useState } from 'react';
import { Minus, Square, X, Maximize2 } from 'lucide-react';
import { getCurrentWindow } from '@tauri-apps/api/window';

export function TitleBar() {
  const [appWindow, setAppWindow] = useState(null);

  useEffect(() => {
    // Dynamically import to avoid SSR/build issues if running outside tauri for some reason (though this is a tauri app)
    const loadWindow = async () => {
        try {
            const win = getCurrentWindow();
            setAppWindow(win);
        } catch (e) {
            console.error("Could not get current window", e);
        }
    };
    loadWindow();
  }, []);

  const minimize = () => appWindow?.minimize();
  const toggleMaximize = async () => {
    if (!appWindow) return;
    const isMaximized = await appWindow.isMaximized();
    if (isMaximized) {
      appWindow.unmaximize();
    } else {
      appWindow.maximize();
    }
  };
  const close = () => appWindow?.close();

  return (
    <div className="fixed top-0 left-0 right-0 h-8 flex items-center justify-between bg-transparent z-50 select-none">
      <div data-tauri-drag-region className="flex-1 h-full flex items-center px-3 gap-2 text-xs font-medium text-gray-500">
        {/* Placeholder for icon or title if needed, or keeping it clean */}
      </div>
      <div className="flex items-center h-full z-50">
        <button 
          onClick={minimize}
          className="h-full w-10 flex items-center justify-center text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
        >
          <Minus size={16} />
        </button>
        <button 
          onClick={toggleMaximize}
           className="h-full w-10 flex items-center justify-center text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
        >
          <Square size={14} />
        </button>
        <button 
          onClick={close}
           className="h-full w-10 flex items-center justify-center text-gray-400 hover:bg-red-500 hover:text-white transition-colors"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
