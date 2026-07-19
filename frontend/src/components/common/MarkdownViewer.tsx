import React from 'react';
import ReactMarkdown from 'react-markdown';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface MarkdownViewerProps {
  content: string;
  className?: string;
}

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({ content, className }) => {
  return (
    <div className={twMerge(clsx('prose prose-invert max-w-none text-textPrimary', className))}>
      <ReactMarkdown
        components={{
          h1: ({node, ...props}) => <h1 className="text-2xl font-bold text-white mt-6 mb-4" {...props} />,
          h2: ({node, ...props}) => <h2 className="text-xl font-semibold text-white mt-5 mb-3 border-b border-border pb-2" {...props} />,
          h3: ({node, ...props}) => <h3 className="text-lg font-medium text-white mt-4 mb-2" {...props} />,
          p: ({node, ...props}) => <p className="leading-relaxed mb-4" {...props} />,
          ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-4 space-y-1 text-textSecondary" {...props} />,
          ol: ({node, ...props}) => <ol className="list-decimal pl-5 mb-4 space-y-1 text-textSecondary" {...props} />,
          li: ({node, ...props}) => <li {...props} />,
          code: ({node, ...props}) => <code className="bg-surfaceHover px-1.5 py-0.5 rounded text-sm text-primary font-mono" {...props} />,
          pre: ({node, ...props}) => <pre className="bg-surfaceHover p-4 rounded-md overflow-x-auto border border-border mb-4 font-mono text-sm" {...props} />,
          blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-primary pl-4 py-1 italic text-textSecondary bg-primary/5 rounded-r-md mb-4" {...props} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
