import React from 'react';
import { cn } from '../lib/utils';
import { motion } from 'framer-motion';

export const Button = React.forwardRef(({ className, variant = 'primary', size = 'default', isLoading, children, ...props }, ref) => {
  const variants = {
    primary: 'bg-primary hover:bg-primary-hover text-white shadow-lg shadow-primary/20',
    secondary: 'bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700',
    ghost: 'bg-transparent hover:bg-gray-800 text-gray-400 hover:text-white',
    destructive: 'bg-red-900/50 hover:bg-red-900 text-red-200 border border-red-900',
  };

  const sizes = {
    default: 'h-10 px-4 py-2',
    sm: 'h-8 px-3 text-xs',
    lg: 'h-12 px-8 text-lg',
    icon: 'h-10 w-10 p-2 flex items-center justify-center',
  };

  return (
    <motion.button
      ref={ref}
      whileTap={{ scale: 0.98 }}
      className={cn(
        'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-50',
        variants[variant],
        sizes[size],
        className
      )}
      disabled={isLoading || props.disabled}
      {...props}
    >
      {isLoading ? (
        <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      ) : null}
      {children}
    </motion.button>
  );
});
Button.displayName = "Button";
