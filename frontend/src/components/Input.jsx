import React from 'react';
import { cn } from '../lib/utils';

export const Input = React.forwardRef(({ className, label, error, ...props }, ref) => {
  return (
    <div className="space-y-2 w-full">
      {label && <label className="text-sm font-medium text-gray-400">{label}</label>}
      <input
        className={cn(
          "flex h-10 w-full rounded-md border border-gray-700 bg-gray-900/50 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent disabled:cursor-not-allowed disabled:opacity-50 transition-all duration-200",
          error && "border-red-500 focus:ring-red-500",
          className
        )}
        ref={ref}
        {...props}
      />
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
});
Input.displayName = "Input";

export const Select = React.forwardRef(({ className, label, options = [], ...props }, ref) => {
  return (
    <div className="space-y-2 w-full">
      {label && <label className="text-sm font-medium text-gray-400">{label}</label>}
      <div className="relative">
        <select
          className={cn(
            "flex h-10 w-full appearance-none rounded-md border border-gray-700 bg-gray-900/50 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent disabled:cursor-not-allowed disabled:opacity-50 transition-all duration-200",
            className
          )}
          ref={ref}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-400">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    </div>
  );
});
Select.displayName = "Select";
